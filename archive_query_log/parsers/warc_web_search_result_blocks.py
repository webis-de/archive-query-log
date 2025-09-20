from abc import ABC, abstractmethod
from functools import cached_property
from itertools import chain
from typing import Iterable, Iterator, Pattern, Annotated, Sequence
from urllib.parse import urljoin
from uuid import uuid5, UUID

from annotated_types import Gt
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from lxml.etree import _Element, tostring  # nosec: B410
from pydantic import HttpUrl, BaseModel
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import (
    NAMESPACE_WARC_WEB_SEARCH_RESULT_BLOCKS_PARSER,
    NAMESPACE_WEB_SEARCH_RESULT_BLOCK,
)
from archive_query_log.orm import (
    Serp,
    InnerParser,
    WebSearchResultBlock,
    InnerSerp,
    WebSearchResultBlockId,
)
from archive_query_log.parsers.warc import open_warc
from archive_query_log.parsers.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.time import utc_now


class WebSearchResultBlockData(BaseModel):
    id: UUID
    rank: int
    content: str
    url: HttpUrl | None = None
    title: str | None = None
    text: str | None = None


class WarcWebSearchResultBlocksParser(BaseModel, ABC):
    provider_id: UUID | None = None
    url_pattern: Pattern | None = None
    priority: Annotated[float, Gt(0)] | None = None

    @cached_property
    def id(self) -> UUID:
        parser_id_components = (
            str(self.provider_id) if self.provider_id is not None else "",
            str(self.url_pattern) if self.url_pattern is not None else "",
            str(self.priority) if self.priority is not None else "",
        )
        return uuid5(
            NAMESPACE_WARC_WEB_SEARCH_RESULT_BLOCKS_PARSER,
            ":".join(parser_id_components),
        )

    @cached_property
    def inner_parser(self) -> InnerParser:
        return InnerParser(
            id=self.id,
            should_parse=True,
            last_parsed=None,
        )

    def is_applicable(self, serp: Serp) -> bool:
        # Check if provider matches.
        if self.provider_id is not None and self.provider_id != serp.provider.id:
            return False

        # Check if URL matches pattern.
        if self.url_pattern is not None and not self.url_pattern.match(
            serp.capture.url.encoded_string()
        ):
            return False
        return True

    @abstractmethod
    def parse(
        self, serp: Serp, warc_store: WarcS3Store
    ) -> list[WebSearchResultBlockData] | None: ...


class XpathWarcWebSearchResultBlocksParser(WarcWebSearchResultBlocksParser):
    xpath: str
    url_xpath: str | None = None
    title_xpath: str | None = None
    text_xpath: str | None = None

    def parse(
        self, serp: Serp, warc_store: WarcS3Store
    ) -> list[WebSearchResultBlockData] | None:
        if serp.warc_location is None:
            return None

        with open_warc(warc_store, serp.warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        elements = safe_xpath(tree, self.xpath, _Element)
        if len(elements) == 0:
            return None

        web_search_result_blocks = []
        element: _Element
        for i, element in enumerate(elements):
            url: str | None = None
            if self.url_xpath is not None:
                urls = safe_xpath(element, self.url_xpath, str)
                if len(urls) > 0:
                    url = urls[0].strip()
                    url = urljoin(serp.capture.url.encoded_string(), url)
            title: str | None = None
            if self.title_xpath is not None:
                titles = safe_xpath(element, self.title_xpath, str)
                if len(titles) > 0:
                    title = titles[0].strip()
            text: str | None = None
            if self.text_xpath is not None:
                texts = safe_xpath(element, self.text_xpath, str)
                if len(texts) > 0:
                    text = texts[0].strip()

            content: str = tostring(
                element,
                encoding=str,
                method="xml",
                pretty_print=False,
                with_tail=True,
            )
            web_search_result_block_id_components = (
                str(serp.id),
                str(self.id),
                str(hash(content)),
                str(i),
            )
            web_search_result_block_id = uuid5(
                NAMESPACE_WEB_SEARCH_RESULT_BLOCK,
                ":".join(web_search_result_block_id_components),
            )
            web_search_result_blocks.append(
                WebSearchResultBlockData(
                    id=web_search_result_block_id,
                    rank=i,
                    content=content,
                    url=HttpUrl(url) if url is not None else None,
                    title=title,
                    text=text,
                )
            )
        return web_search_result_blocks


# TODO: Add actual parsers.
WARC_WEB_SEARCH_RESULT_BLOCKS_PARSERS: Sequence[WarcWebSearchResultBlocksParser] = (
    NotImplemented
)


def _parse_serp_warc_web_search_result_blocks_action(
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
        serp.warc_web_search_result_blocks_parser is not None
        and serp.warc_web_search_result_blocks_parser.should_parse is not None
        and not serp.warc_web_search_result_blocks_parser.should_parse
    ):
        return

    for parser in WARC_WEB_SEARCH_RESULT_BLOCKS_PARSERS:
        if not parser.is_applicable(serp):
            continue
        warc_web_search_result_blocks = parser.parse(serp, config.s3.warc_store)
        if warc_web_search_result_blocks is None:
            # Parsing was not successful.
            continue
        for web_search_result_block in warc_web_search_result_blocks:
            web_search_result_block = WebSearchResultBlock(
                id=web_search_result_block.id,
                last_modified=utc_now(),
                archive=serp.archive,
                provider=serp.provider,
                serp_capture=serp.capture,
                serp=InnerSerp(
                    id=serp.id,
                ),
                rank=web_search_result_block.rank,
                content=web_search_result_block.content,
                url=web_search_result_block.url,
                title=web_search_result_block.title,
                text=web_search_result_block.text,
                parser=InnerParser(
                    id=parser.id,
                    should_parse=False,
                    last_parsed=utc_now(),
                ),
            )
            web_search_result_block.meta.index = (
                config.es.index_web_search_result_blocks
            )
            yield web_search_result_block.create_action()
        yield serp.update_action(
            warc_web_search_result_blocks=[
                WebSearchResultBlockId(
                    id=web_search_result_block.id,
                    rank=web_search_result_block.rank,
                )
                for web_search_result_block in warc_web_search_result_blocks
            ],
            warc_web_search_result_blocks_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield serp.update_action(
        warc_web_search_result_blocks_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_web_search_result_blocks(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location")
            & ~Term(warc_web_search_result_blocks_parser__should_parse=False)
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
            desc="Parsing WARC web search result blocks",
            unit="SERP",
        )
        actions = chain.from_iterable(
            _parse_serp_warc_web_search_result_blocks_action(config, serp)
            for serp in changed_serps
        )
        config.es.bulk(
            actions=actions,
            dry_run=dry_run,
        )
    else:
        print("No new/changed SERPs.")
