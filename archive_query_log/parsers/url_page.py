from datetime import datetime
from functools import cache
from typing import Iterable
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script, Term
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_PAGE_PARSER
from archive_query_log.orm import InnerProviderId, UrlPageParserType
from archive_query_log.orm import Serp, InnerParser, \
    UrlPageParser
from archive_query_log.parsers.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now


def add_url_page_parser(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: UrlPageParserType,
        parameter: str | None,
        segment: int | None,
        remove_pattern_regex: str | None,
        space_pattern_regex: str | None,
) -> None:
    if parser_type == "query_parameter":
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment_parameter":
        if parameter is None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path_segment":
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        provider_id,
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
        parser_type,
        parameter if parameter is not None else "",
        str(segment) if segment is not None else "",
        remove_pattern_regex if remove_pattern_regex is not None else "",
        space_pattern_regex if space_pattern_regex is not None else "",
    )
    parser_id = str(uuid5(
        NAMESPACE_URL_PAGE_PARSER,
        ":".join(parser_id_components),
    ))
    provider = UrlPageParser(
        meta={"id": parser_id},
        provider=InnerProviderId(id=provider_id),
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
        last_modified=utc_now(),
    )
    provider.save(using=config.es.client)


def _parse_url_page(parser: UrlPageParser, url: str) -> int | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse page.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No page parameter given.")
        page_string = parse_url_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        page_string = parse_url_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        page_string = parse_url_path_segment(parser.segment, url)
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")

    if page_string is None:
        return None

    # Clean up page string.
    if parser.remove_pattern is not None:
        page_string = parser.remove_pattern.sub("", page_string)
    page_string = page_string.strip()
    page = int(page_string)
    return page


@cache
def _url_page_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlPageParser]:
    parsers: Iterable[UrlPageParser] = (
        UrlPageParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_page(
        config: Config,
        serp: Serp,
        start_time: datetime,
) -> None:
    # Re-check if parsing is necessary.
    if (serp.url_page_parser is not None and
            serp.url_page_parser.last_parsed is not None and
            serp.url_page_parser.last_parsed > serp.last_modified):
        return

    for parser in _url_page_parsers(config, serp.provider.id):
        # Try to parse the query.
        url_page = _parse_url_page(parser, serp.capture.url)
        if url_page is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        url_page_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        serp.update(
            using=config.es.client,
            retry_on_conflict=3,
            url_page=url_page,
            url_page_parser=url_page_parser.to_dict(),
        )
        return
    serp.update(
        using=config.es.client,
        retry_on_conflict=3,
        url_page_parser=InnerParser(
            last_parsed=start_time,
        ).to_dict(),
    )
    return


def parse_serps_url_page(config: Config) -> None:
    start_time = utc_now()

    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="url_page_parser.last_parsed") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['url_page_parser.last_parsed']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['url_page_parser.last_parsed'].value"
                       ")",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_serps = (
        changed_serps_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = changed_serps_search.scan()
        changed_serps = safe_iter_scan(changed_serps)
        # noinspection PyTypeChecker
        changed_serps = tqdm(
            changed_serps, total=num_changed_serps,
            desc="Parsing URL page", unit="SERP")
        for serp in changed_serps:
            _parse_serp_url_page(
                config=config,
                serp=serp,
                start_time=start_time,
            )
        Serp.index().refresh(using=config.es.client)
    else:
        echo("No new/changed SERPs.")