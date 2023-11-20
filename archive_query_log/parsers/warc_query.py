from datetime import datetime
from functools import cache
from itertools import chain
from typing import Iterable, Iterator
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script, Term
from tqdm.auto import tqdm
from warc_s3 import WarcS3Store

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_WARC_QUERY_PARSER
from archive_query_log.orm import Serp, InnerParser, InnerProviderId, \
    WarcQueryParserType, WarcQueryParser, WarcLocation
from archive_query_log.parsers.util import clean_text
from archive_query_log.parsers.warc import open_warc
from archive_query_log.parsers.xml import parse_xml_tree, safe_xpath
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_warc_query_parser(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: WarcQueryParserType,
        xpath: str | None,
        remove_pattern_regex: str | None,
        space_pattern_regex: str | None,
) -> None:
    if parser_type == "xpath":
        if xpath is None:
            raise ValueError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        provider_id,
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
    )
    parser_id = str(uuid5(
        NAMESPACE_WARC_QUERY_PARSER,
        ":".join(parser_id_components),
    ))
    parser = WarcQueryParser(
        meta={"id": parser_id},
        provider=InnerProviderId(id=provider_id),
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        xpath=xpath,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
        last_modified=utc_now(),
    )
    parser.save(using=config.es.client)


def _parse_warc_query(
        parser: WarcQueryParser,
        capture_url: str,
        warc_store: WarcS3Store,
        warc_location: WarcLocation,
) -> str | None:
    # Check if URL matches pattern.
    if (parser.url_pattern is not None and
            not parser.url_pattern.match(capture_url)):
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
        WarcQueryParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_warc_query_action(
        config: Config,
        serp: Serp,
        start_time: datetime,
) -> Iterator[dict]:
    # Re-check if it can be parsed.
    if serp.warc_location is None:
        return

    # Re-check if parsing is necessary.
    if (serp.warc_query_parser is not None and
            serp.warc_query_parser.last_parsed is not None and
            serp.warc_query_parser.last_parsed > serp.last_modified):
        return

    for parser in _warc_query_parsers(config, serp.provider.id):
        # Try to parse the query.
        warc_query = _parse_warc_query(
            parser, serp.capture.url, config.s3.warc_store, serp.warc_location)
        if warc_query is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        warc_query_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        yield update_action(
            serp,
            warc_query=warc_query,
            warc_query_parser=warc_query_parser,
        )
        return
    yield update_action(
        serp,
        warc_query_parser=InnerParser(last_parsed=start_time),
    )
    return


def parse_serps_warc_query(config: Config) -> None:
    Serp.index().refresh(using=config.es.client)
    start_time = utc_now()
    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            Exists(field="warc_location") &
            (
                    ~Exists(field="last_modified") |
                    ~Exists(field="warc_query_parser.last_parsed") |
                    Script(
                        script="!doc['last_modified'].isEmpty() && "
                               "!doc['warc_query_parser.last_parsed']"
                               ".isEmpty() && "
                               "!doc['last_modified'].value.isBefore("
                               "doc['warc_query_parser.last_parsed'].value"
                               ")",
                    )
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = changed_serps_search.scan()
        changed_serps = safe_iter_scan(changed_serps)
        # noinspection PyTypeChecker
        changed_serps = tqdm(
            changed_serps, total=num_changed_serps,
            desc="Parsing WARC query", unit="SERP")
        actions = chain.from_iterable(
            _parse_serp_warc_query_action(
                config=config,
                serp=serp,
                start_time=start_time,
            )
            for serp in changed_serps
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed SERPs.")
