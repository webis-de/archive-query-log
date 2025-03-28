from functools import cache
from itertools import chain, islice
from typing import Iterable, Iterator
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_QUERY_PARSER
from archive_query_log.orm import (
    Serp,
    InnerParser,
    InnerProviderId,
    WarcQueryParserType,
    WarcQueryParser,
    WarcLocation,
)
from archive_query_log.parsers.util import clean_text
from archive_query_log.parsers.warc import open_warc
from archive_query_log.parsers.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_warc_query_parser(
    config: Config,
    provider_id: str | None,
    url_pattern_regex: str | None,
    priority: float | None,
    parser_type: WarcQueryParserType,
    xpath: str | None,
    remove_pattern_regex: str | None,
    space_pattern_regex: str | None,
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
            NAMESPACE_WARC_QUERY_PARSER,
            ":".join(parser_id_components),
        )
    )
    parser = WarcQueryParser(
        id=parser_id,
        last_modified=utc_now(),
        provider=InnerProviderId(id=provider_id) if provider_id else None,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        xpath=xpath,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
    )
    parser.save(using=config.es.client, index=config.es.index_warc_query_parsers)


def _parse_warc_query(
    parser: WarcQueryParser,
    capture_url: str,
    warc_store: WarcS3Store,
    warc_location: WarcLocation,
) -> str | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(capture_url):
        return None

    # Parse query.
    if parser.parser_type == "xpath":
        if parser.xpath is None:
            raise ValueError("No XPath given.")
        with open_warc(warc_store, warc_location) as record:
            tree = parse_xml_tree(record)
        if tree is None:
            return None

        queries = safe_xpath(tree, parser.xpath, str)
        for query in queries:
            query_cleaned = clean_text(
                text=query,
                remove_pattern=parser.remove_pattern,
                space_pattern=parser.space_pattern,
            )
            if query_cleaned is not None:
                return query_cleaned
        return None
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")


@cache
def _warc_query_parsers(
    config: Config,
    provider_id: str,
) -> list[WarcQueryParser]:
    parsers: Iterable[WarcQueryParser] = (
        WarcQueryParser.search(
            using=config.es.client, index=config.es.index_warc_query_parsers
        )
        .filter(~Exists(field="provider.id") | Term(provider__id=provider_id))
        .query(RankFeature(field="priority", saturation={}))
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_warc_query_action(
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
        serp.warc_query_parser is not None
        and serp.warc_query_parser.should_parse is not None
        and not serp.warc_query_parser.should_parse
    ):
        return

    for parser in _warc_query_parsers(config, serp.provider.id):
        # Try to parse the query.
        warc_query = _parse_warc_query(
            parser, serp.capture.url, config.s3.warc_store, serp.warc_location
        )
        if warc_query is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        yield update_action(
            serp,
            warc_query=warc_query,
            warc_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield update_action(
        serp,
        warc_query_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_warc_query(config: Config, prefetch_limit: int | None = None) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location") & ~Term(warc_query_parser__should_parse=False)
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
            desc="Parsing WARC query",
            unit="SERP",
        )
        actions = chain.from_iterable(
            _parse_serp_warc_query_action(config, serp) for serp in changed_serps
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed SERPs.")
