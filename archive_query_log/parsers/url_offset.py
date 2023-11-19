from datetime import datetime
from functools import cache
from itertools import chain
from typing import Iterable, Iterator
from uuid import uuid5
from warnings import warn

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Exists, FunctionScore, Script, Term
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_OFFSET_PARSER
from archive_query_log.orm import InnerProviderId, UrlOffsetParserType
from archive_query_log.orm import Serp, InnerParser, \
    UrlOffsetParser
from archive_query_log.parsers.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_url_offset_parser(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: UrlOffsetParserType,
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
        NAMESPACE_URL_OFFSET_PARSER,
        ":".join(parser_id_components),
    ))
    parser = UrlOffsetParser(
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
    parser.save(using=config.es.client)


def _parse_url_offset(parser: UrlOffsetParser, url: str) -> int | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse offset.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No offset parameter given.")
        offset_string = parse_url_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        offset_string = parse_url_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        offset_string = parse_url_path_segment(parser.segment, url)
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")

    if offset_string is None:
        return None

    # Clean up offset string.
    if parser.remove_pattern is not None:
        offset_string = parser.remove_pattern.sub("", offset_string)
    offset_string = offset_string.strip()
    try:
        offset = int(offset_string)
    except ValueError:
        warn(RuntimeWarning(
            f"Could not parse offset '{offset_string}' in URL: {url}"))
        return None
    return offset


@cache
def _url_offset_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlOffsetParser]:
    parsers: Iterable[UrlOffsetParser] = (
        UrlOffsetParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_offset_action(
        config: Config,
        serp: Serp,
        start_time: datetime,
) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (serp.url_offset_parser is not None and
            serp.url_offset_parser.last_parsed is not None and
            serp.url_offset_parser.last_parsed > serp.last_modified):
        return

    for parser in _url_offset_parsers(config, serp.provider.id):
        # Try to parse the query.
        url_offset = _parse_url_offset(parser, serp.capture.url)
        if url_offset is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        url_offset_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        yield update_action(
            serp,
            url_offset=url_offset,
            url_offset_parser=url_offset_parser,
        )
        return
    yield update_action(
        serp,
        url_offset_parser=InnerParser(last_parsed=start_time),
    )
    return


def parse_serps_url_offset(config: Config) -> None:
    Serp.index().refresh(using=config.es.client)
    start_time = utc_now()
    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="url_offset_parser.last_parsed") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['url_offset_parser.last_parsed']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['url_offset_parser.last_parsed'].value"
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
            desc="Parsing URL offset", unit="SERP")
        actions = chain.from_iterable(
            _parse_serp_url_offset_action(
                config=config,
                serp=serp,
                start_time=start_time,
            )
            for serp in changed_serps
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed SERPs.")
