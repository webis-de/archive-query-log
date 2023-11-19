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

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_QUERY_PARSER
from archive_query_log.orm import Capture, Serp, InnerCapture, InnerParser, \
    UrlQueryParser
from archive_query_log.orm import UrlQueryParserType, \
    InnerProviderId
from archive_query_log.parsers.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_url_query_parser(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: UrlQueryParserType,
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
        NAMESPACE_URL_QUERY_PARSER,
        ":".join(parser_id_components),
    ))
    parser = UrlQueryParser(
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


def _parse_url_query(parser: UrlQueryParser, url: str) -> str | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(url):
        return None

    # Parse query.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No query parameter given.")
        query = parse_url_query_parameter(parser.parameter, url)
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        query = parse_url_fragment_parameter(parser.parameter, url)
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        query = parse_url_path_segment(parser.segment, url)
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")

    if query is None:
        return None

    # Clean up query.
    if parser.remove_pattern is not None:
        query = parser.remove_pattern.sub("", query)
    if parser.space_pattern is not None:
        query = parser.space_pattern.sub(" ", query)
    query = query.strip()
    query = " ".join(query.split())
    return query


@cache
def _url_query_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlQueryParser]:
    parsers: Iterable[UrlQueryParser] = (
        UrlQueryParser.search(using=config.es.client)
        .filter(Term(provider__id=provider_id))
        .sort("-priority")
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_query_action(
        config: Config,
        capture: Capture,
        start_time: datetime,
) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (capture.url_query_parser is not None and
            capture.url_query_parser.last_parsed is not None and
            capture.url_query_parser.last_parsed > capture.last_modified):
        return

    for parser in _url_query_parsers(config, capture.provider.id):
        # Try to parse the query.
        url_query = _parse_url_query(parser, capture.url)
        if url_query is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        url_query_parser = InnerParser(
            id=parser.id,
            last_parsed=start_time,
        )
        serp = Serp(
            meta={"id": capture.id},
            archive=capture.archive,
            provider=capture.provider,
            capture=InnerCapture(
                id=capture.id,
                url=capture.url,
                timestamp=capture.timestamp,
                status_code=capture.status_code,
                digest=capture.digest,
                mimetype=capture.mimetype,
            ),
            url_query=url_query,
            url_query_parser=url_query_parser,
            last_modified=start_time,
        )
        yield serp.to_dict(include_meta=True)
        yield update_action(
            capture,
            url_query_parser=url_query_parser,
        )
        return
    yield update_action(
        capture,
        url_query_parser=InnerParser(last_parsed=start_time),
    )
    return


def parse_serps_url_query(config: Config) -> None:
    Capture.index().refresh(using=config.es.client)
    start_time = utc_now()
    changed_captures_search: Search = (
        Capture.search(using=config.es.client)
        .filter(
            ~Exists(field="last_modified") |
            ~Exists(field="url_query_parser.last_parsed") |
            Script(
                script="!doc['last_modified'].isEmpty() && "
                       "!doc['url_query_parser.last_parsed']"
                       ".isEmpty() && "
                       "!doc['last_modified'].value.isBefore("
                       "doc['url_query_parser.last_parsed'].value"
                       ")",
            )
        )
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_captures = (
        changed_captures_search.extra(track_total_hits=True)
        .execute().hits.total.value)
    if num_changed_captures > 0:
        changed_captures: Iterable[Capture] = changed_captures_search.scan()
        changed_captures = safe_iter_scan(changed_captures)
        # noinspection PyTypeChecker
        changed_captures = tqdm(
            changed_captures, total=num_changed_captures,
            desc="Parsing URL query", unit="capture")
        actions = chain.from_iterable(
            _parse_serp_url_query_action(
                config=config,
                capture=capture,
                start_time=start_time,
            )
            for capture in changed_captures
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed captures.")
