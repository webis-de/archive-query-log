from functools import cache
from itertools import chain
from typing import Iterable, Iterator
from urllib.parse import urljoin
from uuid import uuid5, UUID

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from lxml.etree import _Element, tostring  # nosec: B410
from pydantic import BaseModel, HttpUrl
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import (
    NAMESPACE_WARC_SPECIAL_CONTENTS_RESULT_BLOCKS_PARSER,
    NAMESPACE_SPECIAL_CONTENTS_RESULT_BLOCK,
)
from archive_query_log.orm import (
    Serp,
    InnerParser,
    InnerProviderId,
    WarcSpecialContentsResultBlocksParserType,
    WarcSpecialContentsResultBlocksParser,
    WarcLocation,
    SpecialContentsResultBlock,
    InnerSerp,
    SpecialContentsResultBlockId,
)
from archive_query_log.parsers.warc import open_warc
from archive_query_log.parsers.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.time import utc_now


def add_warc_special_contents_result_blocks_parser(
    config: Config,
    provider_id: UUID | None,
    url_pattern_regex: str | None,
    priority: float | None,
    parser_type: WarcSpecialContentsResultBlocksParserType,
    xpath: str | None,
    url_xpath: str | None,
    text_xpath: str | None,
    dry_run: bool = False,
) -> None:
    if priority is not None and priority <= 0:
        raise ValueError("Priority must be strictly positive.")
    if parser_type == "xpath":
        if xpath is None:
            raise ValueError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        str(provider_id) if provider_id is not None else "",
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
    )
    parser_id = uuid5(
        NAMESPACE_WARC_SPECIAL_CONTENTS_RESULT_BLOCKS_PARSER,
        ":".join(parser_id_components),
    )
    parser = WarcSpecialContentsResultBlocksParser(
        id=parser_id,
        last_modified=utc_now(),
        provider=InnerProviderId(id=provider_id) if provider_id else None,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        xpath=xpath,
        url_xpath=url_xpath,
        text_xpath=text_xpath,
    )
    if not dry_run:
        parser.save(
            using=config.es.client,
            index=config.es.index_warc_special_contents_result_blocks_parsers,
        )
    else:
        print(parser)


class SpecialContentsResultBlockData(BaseModel):
    id: UUID
    rank: int
    content: str
    url: HttpUrl | None = None
    text: str | None = None


def _parse_warc_special_contents_result_blocks(
    parser: WarcSpecialContentsResultBlocksParser,
    serp_id: UUID,
    capture_url: HttpUrl,
    warc_store: WarcS3Store,
    warc_location: WarcLocation,
) -> list[SpecialContentsResultBlockData] | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(
        capture_url.encoded_string()
    ):
        return None

    # Parse special contents result blocks.
    if parser.parser_type == "xpath":
        if parser.xpath is None:
            raise ValueError("No XPath given.")
        with open_warc(warc_store, warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        elements = safe_xpath(tree, parser.xpath, _Element)
        if len(elements) == 0:
            return None

        special_contents_result_blocks = []
        element: _Element
        for i, element in enumerate(elements):
            url: str | None = None
            if parser.url_xpath is not None:
                urls = safe_xpath(element, parser.url_xpath, str)
                if len(urls) > 0:
                    url = urls[0].strip()
                    url = urljoin(capture_url.encoded_string(), url)
            text: str | None = None
            if parser.text_xpath is not None:
                texts = safe_xpath(element, parser.text_xpath, str)
                if len(texts) > 0:
                    text = texts[0].strip()

            content: str = tostring(
                element,
                encoding=str,
                method="xml",
                pretty_print=False,
                with_tail=True,
            )
            special_contents_result_block_id_components = (
                str(serp_id),
                str(parser.id),
                str(hash(content)),
                str(i),
            )
            special_contents_result_block_id = uuid5(
                NAMESPACE_SPECIAL_CONTENTS_RESULT_BLOCK,
                ":".join(special_contents_result_block_id_components),
            )
            special_contents_result_blocks.append(
                SpecialContentsResultBlockData(
                    id=special_contents_result_block_id,
                    rank=i,
                    content=content,
                    url=HttpUrl(url) if url is not None else None,
                    text=text,
                )
            )
        return special_contents_result_blocks
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")


@cache
def _warc_special_contents_result_blocks_parsers(
    config: Config,
    provider_id: str,
) -> list[WarcSpecialContentsResultBlocksParser]:
    parsers: Iterable[WarcSpecialContentsResultBlocksParser] = (
        WarcSpecialContentsResultBlocksParser.search(
            using=config.es.client,
            index=config.es.index_warc_special_contents_result_blocks_parsers,
        )
        .filter(~Exists(field="provider.id") | Term(provider__id=provider_id))
        .query(RankFeature(field="priority", saturation={}))
        .scan()
    )
    return list(parsers)


def _parse_serp_warc_special_contents_result_blocks_action(
    config: Config,
    serp: Serp,
) -> Iterator[dict]:
    # Re-check if it can be parsed.
    if (
        serp.warc_location is None
        or serp.warc_location.file is None
        or serp.warc_location.offset is None
        or serp.warc_location.length is None
    ):
        return

    # Re-check if parsing is necessary.
    if (
        serp.warc_special_contents_result_blocks_parser is not None
        and serp.warc_special_contents_result_blocks_parser.should_parse is not None
        and not serp.warc_special_contents_result_blocks_parser.should_parse
    ):
        return

    for parser in _warc_special_contents_result_blocks_parsers(
        config, serp.provider.id
    ):
        # Try to parse the special contents result blocks.
        warc_special_contents_result_blocks = (
            _parse_warc_special_contents_result_blocks(
                parser=parser,
                serp_id=serp.id,
                capture_url=serp.capture.url,
                warc_store=config.s3.warc_store,
                warc_location=serp.warc_location,
            )
        )
        if warc_special_contents_result_blocks is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        for special_contents_result_block in warc_special_contents_result_blocks:
            special_contents_result_block = SpecialContentsResultBlock(
                id=special_contents_result_block.id,
                last_modified=utc_now(),
                archive=serp.archive,
                provider=serp.provider,
                serp_capture=serp.capture,
                serp=InnerSerp(
                    id=serp.id,
                ),
                rank=special_contents_result_block.rank,
                content=special_contents_result_block.content,
                url=special_contents_result_block.url,
                text=special_contents_result_block.text,
                parser=InnerParser(
                    id=parser.id,
                    should_parse=False,
                    last_parsed=utc_now(),
                ),
            )
            special_contents_result_block.meta.index = (
                config.es.index_web_search_result_blocks
            )
            yield special_contents_result_block.create_action()
        yield serp.update_action(
            warc_special_contents_result_blocks=[
                SpecialContentsResultBlockId(
                    id=special_contents_result_block.id,
                    rank=special_contents_result_block.rank,
                )
                for special_contents_result_block in warc_special_contents_result_blocks
            ],
            warc_special_contents_result_blocks_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        warc_special_contents_result_blocks_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_special_contents_result_blocks(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location")
            & ~Term(warc_special_contents_result_blocks_parser__should_parse=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = changed_serps_search.params(size=size).execute()

        changed_serps = tqdm(
            changed_serps,
            total=num_changed_serps,
            desc="Parsing WARC special contents result blocks",
            unit="SERP",
        )
        actions = chain.from_iterable(
            _parse_serp_warc_special_contents_result_blocks_action(config, serp)
            for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")
