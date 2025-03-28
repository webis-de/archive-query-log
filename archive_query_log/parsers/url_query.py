from functools import cache
from itertools import chain, islice
from typing import Iterable, Iterator
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_QUERY_PARSER
from archive_query_log.orm import (
    Capture,
    Serp,
    InnerCapture,
    InnerParser,
    UrlQueryParser,
)
from archive_query_log.orm import UrlQueryParserType, InnerProviderId
from archive_query_log.parsers.url import (
    parse_url_query_parameter,
    parse_url_fragment_parameter,
    parse_url_path_segment,
)
from archive_query_log.parsers.util import clean_text
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_url_query_parser(
    config: Config,
    provider_id: str | None,
    url_pattern_regex: str | None,
    priority: float | None,
    parser_type: UrlQueryParserType,
    parameter: str | None,
    segment: int | None,
    remove_pattern_regex: str | None,
    space_pattern_regex: str | None,
) -> None:
    if priority is not None and priority <= 0:
        raise ValueError("Priority must be strictly positive.")
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
        provider_id if provider_id is not None else "",
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
    )
    parser_id = str(
        uuid5(
            NAMESPACE_URL_QUERY_PARSER,
            ":".join(parser_id_components),
        )
    )
    parser = UrlQueryParser(
        id=parser_id,
        last_modified=utc_now(),
        provider=InnerProviderId(id=provider_id) if provider_id else None,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
    )
    parser.save(using=config.es.client, index=config.es.index_url_query_parsers)


def _parse_url_query(parser: UrlQueryParser, capture_url: str) -> str | None:
    # Check if URL matches pattern.
    if parser.url_pattern is not None and not parser.url_pattern.match(capture_url):
        return None

    # Parse query.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No query parameter given.")
        query = parse_url_query_parameter(parser.parameter, capture_url)
        if query is None:
            return None
        return clean_text(
            text=query,
            remove_pattern=parser.remove_pattern,
            space_pattern=parser.space_pattern,
        )
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        query = parse_url_fragment_parameter(parser.parameter, capture_url)
        if query is None:
            return None
        return clean_text(
            text=query,
            remove_pattern=parser.remove_pattern,
            space_pattern=parser.space_pattern,
        )
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        query = parse_url_path_segment(parser.segment, capture_url)
        if query is None:
            return None
        return clean_text(
            text=query,
            remove_pattern=parser.remove_pattern,
            space_pattern=parser.space_pattern,
        )
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")


@cache
def _url_query_parsers(
    config: Config,
    provider_id: str,
) -> list[UrlQueryParser]:
    parsers: Iterable[UrlQueryParser] = (
        UrlQueryParser.search(
            using=config.es.client, index=config.es.index_url_query_parsers
        )
        .filter(~Exists(field="provider.id") | Term(provider__id=provider_id))
        .query(RankFeature(field="priority", saturation={}))
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_query_action(
    config: Config,
    capture: Capture,
) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (
        capture.url_query_parser is not None
        and capture.url_query_parser.should_parse is not None
        and not capture.url_query_parser.should_parse
    ):
        return

    for parser in _url_query_parsers(config, capture.provider.id):
        # Try to parse the query.
        url_query = _parse_url_query(parser, capture.url)
        if url_query is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        serp = Serp(
            id=capture.id,
            last_modified=utc_now(),
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
            url_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
            url_page_parser=InnerParser(
                should_parse=True,
            ),
            url_offset_parser=InnerParser(
                should_parse=True,
            ),
            warc_query_parser=InnerParser(
                should_parse=True,
            ),
            warc_snippets_parser=InnerParser(
                should_parse=True,
            ),
        )
        serp.meta.index = config.es.index_serps
        yield serp.to_dict(include_meta=True)
        yield update_action(
            capture,
            url_query_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield update_action(
        capture,
        url_query_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_query(config: Config, prefetch_limit: int | None = None) -> None:
    config.es.client.indices.refresh(index=config.es.index_captures)
    changed_captures_search: Search = (
        Capture.search(using=config.es.client, index=config.es.index_captures)
        .filter(~Term(url_query_parser__should_parse=False))
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_captures = changed_captures_search.count()
    if num_changed_captures > 0:
        changed_captures: Iterable[Capture] = changed_captures_search.params(
            preserve_order=True
        ).scan()
        changed_captures = safe_iter_scan(changed_captures)

        if prefetch_limit is not None:
            num_changed_captures = min(num_changed_captures, prefetch_limit)
            changed_captures = tqdm(changed_captures, total=num_changed_captures, desc="Pre-fetching captures", unit="capture")
            changed_captures = iter(list(islice(changed_captures, prefetch_limit)))

        # noinspection PyTypeChecker
        changed_captures = tqdm(
            changed_captures,
            total=num_changed_captures,
            desc="Parsing URL query",
            unit="capture",
        )
        actions = chain.from_iterable(
            _parse_serp_url_query_action(config, capture)
            for capture in changed_captures
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed captures.")
