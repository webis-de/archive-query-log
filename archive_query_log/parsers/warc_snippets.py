from functools import cache
from itertools import chain, islice
from typing import Iterable, Iterator
from urllib.parse import urljoin
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists

# noinspection PyProtectedMember
from lxml.etree import _Element, tostring  # nosec: B410
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import (
    NAMESPACE_WARC_SNIPPETS_PARSER,
    NAMESPACE_RESULT,
)
from archive_query_log.orm import (
    Serp,
    InnerParser,
    InnerProviderId,
    WarcSnippetsParserType,
    WarcSnippetsParser,
    WarcLocation,
    Snippet,
    Result,
    InnerSerp,
    SnippetId,
    InnerDownloader,
)
from archive_query_log.parsers.warc import open_warc
from archive_query_log.parsers.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_warc_snippets_parser(
    config: Config,
    provider_id: str | None,
    url_pattern_regex: str | None,
    priority: float | None,
    parser_type: WarcSnippetsParserType,
    xpath: str | None,
    url_xpath: str | None,
    title_xpath: str | None,
    text_xpath: str | None,
) -> None:
    if priority is not None and priority <= 0:
        raise ValueError("Priority must be strictly positive.")
    if parser_type == "xpath":
        if xpath is None:
            raise ValueError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        provider_id if provider_id is not None else "",
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
    )
    parser_id = str(
        uuid5(
            NAMESPACE_WARC_SNIPPETS_PARSER,
            ":".join(parser_id_components),
        )
    )
    parser = WarcSnippetsParser(
        id=parser_id,
        last_modified=utc_now(),
        provider=InnerProviderId(id=provider_id) if provider_id else None,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        xpath=xpath,
        url_xpath=url_xpath,
        title_xpath=title_xpath,
        text_xpath=text_xpath,
    )
    parser.save(using=config.es.client, index=config.es.index_warc_snippets_parsers)


def _parse_warc_snippets(
    parser: WarcSnippetsParser,
    serp_id: str,
    capture_url: str,
    warc_store: WarcS3Store,
    warc_location: WarcLocation,
) -> list[Snippet] | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(capture_url):
        return None

    # Parse snippets.
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

        snippets = []
        element: _Element
        for i, element in enumerate(elements):
            url: str | None = None
            if parser.url_xpath is not None:
                urls = safe_xpath(element, parser.url_xpath, str)
                if len(urls) > 0:
                    url = urls[0].strip()
                    url = urljoin(capture_url, url)
            title: str | None = None
            if parser.title_xpath is not None:
                titles = safe_xpath(element, parser.title_xpath, str)
                if len(titles) > 0:
                    title = titles[0].strip()
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
            snippet_id_components = (
                serp_id,
                parser.id,
                str(hash(content)),
                str(i),
            )
            snippet_id = str(
                uuid5(
                    NAMESPACE_RESULT,
                    ":".join(snippet_id_components),
                )
            )
            snippets.append(
                Snippet(
                    id=snippet_id,
                    rank=i,
                    content=content,
                    url=url,
                    title=title,
                    text=text,
                )
            )
        return snippets
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")


@cache
def _warc_snippets_parsers(
    config: Config,
    provider_id: str,
) -> list[WarcSnippetsParser]:
    parsers: Iterable[WarcSnippetsParser] = (
        WarcSnippetsParser.search(
            using=config.es.client, index=config.es.index_warc_snippets_parsers
        )
        .filter(~Exists(field="provider.id") | Term(provider__id=provider_id))
        .query(RankFeature(field="priority", saturation={}))
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_warc_snippets_action(
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
        serp.warc_snippets_parser is not None
        and serp.warc_snippets_parser.should_parse is not None
        and not serp.warc_snippets_parser.should_parse
    ):
        return

    for parser in _warc_snippets_parsers(config, serp.provider.id):
        # Try to parse the snippets.
        warc_snippets = _parse_warc_snippets(
            parser=parser,
            serp_id=serp.id,
            capture_url=serp.capture.url,
            warc_store=config.s3.warc_store,
            warc_location=serp.warc_location,
        )
        if warc_snippets is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        for snippet in warc_snippets:
            result = Result(
                id=snippet.id,
                last_modified=utc_now(),
                archive=serp.archive,
                provider=serp.provider,
                capture=serp.capture,
                serp=InnerSerp(
                    id=serp.id,
                ).to_dict(),
                snippet=snippet,
                snippet_parser=InnerParser(
                    id=parser.id,
                    should_parse=False,
                    last_parsed=utc_now(),
                ).to_dict(),
                warc_before_serp_downloader=InnerDownloader(
                    should_download=True,
                ).to_dict(),
                warc_after_serp_downloader=InnerDownloader(
                    should_download=True,
                ).to_dict(),
            )
            result.meta.index = config.es.index_results
            yield result.to_dict(include_meta=True)
        yield update_action(
            serp,
            warc_snippets=[
                SnippetId(
                    id=snippet.id,
                    rank=snippet.rank,
                )
                for snippet in warc_snippets
            ],
            warc_snippets_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield update_action(
        serp,
        warc_snippets_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_snippets(config: Config, prefetch_limit: int | None = None) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location")
            & ~Term(warc_snippets_parser__should_parse=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = changed_serps_search.params(
            preserve_order=True
        ).scan()
        changed_serps = safe_iter_scan(changed_serps)

        if prefetch_limit is not None:
            num_changed_serps = min(num_changed_serps, prefetch_limit)
            changed_serps = tqdm(changed_serps, total=num_changed_serps, desc="Pre-fetching SERPs", unit="SERP")
            changed_serps = iter(list(islice(changed_serps, prefetch_limit)))

        # noinspection PyTypeChecker
        changed_serps = tqdm(
            changed_serps,
            total=num_changed_serps,
            desc="Parsing WARC snippets",
            unit="SERP",
        )
        actions = chain.from_iterable(
            _parse_serp_warc_snippets_action(config, serp) for serp in changed_serps
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed SERPs.")
