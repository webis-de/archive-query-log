from functools import cache
from itertools import chain
from typing import Iterable, Iterator
from uuid import uuid5

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_PAGE_PARSER
from archive_query_log.orm import InnerProviderId, UrlPageParserType
from archive_query_log.orm import Serp, InnerParser, UrlPageParser
from archive_query_log.parsers.url import parse_url_query_parameter, \
    parse_url_fragment_parameter, parse_url_path_segment
from archive_query_log.parsers.util import clean_int
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def add_url_page_parser(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: UrlPageParserType,
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
    parser_id = str(uuid5(
        NAMESPACE_URL_PAGE_PARSER,
        ":".join(parser_id_components),
    ))
    parser = UrlPageParser(
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
    parser.save(using=config.es.client)


def _parse_url_page(parser: UrlPageParser, capture_url: str) -> int | None:
    # Check if URL matches pattern.
    if (parser.url_pattern is not None and
            not parser.url_pattern.match(capture_url)):
        return None

    # Parse page.
    if parser.parser_type == "query_parameter":
        if parser.parameter is None:
            raise ValueError("No page parameter given.")
        page_string = parse_url_query_parameter(parser.parameter, capture_url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=parser.remove_pattern,
        )
    elif parser.parser_type == "fragment_parameter":
        if parser.parameter is None:
            raise ValueError("No fragment parameter given.")
        page_string = parse_url_fragment_parameter(
            parser.parameter, capture_url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=parser.remove_pattern,
        )
    elif parser.parser_type == "path_segment":
        if parser.segment is None:
            raise ValueError("No path segment given.")
        page_string = parse_url_path_segment(parser.segment, capture_url)
        if page_string is None:
            return None
        return clean_int(
            text=page_string,
            remove_pattern=parser.remove_pattern,
        )
    else:
        raise ValueError(f"Unknown parser type: {parser.parser_type}")


@cache
def _url_page_parsers(
        config: Config,
        provider_id: str,
) -> list[UrlPageParser]:
    parsers: Iterable[UrlPageParser] = (
        UrlPageParser.search(using=config.es.client)
        .filter(
            ~Exists(field="provider.id") |
            Term(provider__id=provider_id)
        )
        .query(RankFeature(field="priority", saturation={}))
        .scan()
    )
    parsers = safe_iter_scan(parsers)
    return list(parsers)


def _parse_serp_url_page_action(
        config: Config,
        serp: Serp,
) -> Iterator[dict]:
    # Re-check if parsing is necessary.
    if (serp.url_page_parser is not None and
            serp.url_page_parser.should_parse is not None and
            not serp.url_page_parser.should_parse):
        return

    for parser in _url_page_parsers(config, serp.provider.id):
        # Try to parse the query.
        url_page = _parse_url_page(parser, serp.capture.url)
        if url_page is None:
            # Parsing was not successful, e.g., URL pattern did not match.
            continue
        yield update_action(
            serp,
            url_page=url_page,
            url_page_parser=InnerParser(
                id=parser.id,
                should_parse=False,
                last_parsed=utc_now(),
            ),
        )
        return
    yield update_action(
        serp,
        url_page_parser=InnerParser(
            should_parse=False,
            last_parsed=utc_now(),
        ),
    )
    return


def parse_serps_url_page(config: Config) -> None:
    Serp.index().refresh(using=config.es.client)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client)
        .filter(~Term(url_page_parser__should_parse=False))
        .query(
            RankFeature(field="archive.priority", saturation={}) |
            RankFeature(field="provider.priority", saturation={}) |
            FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps > 0:
        changed_serps: Iterable[Serp] = (
            changed_serps_search
            .params(preserve_order=True)
            .scan()
        )
        changed_serps = safe_iter_scan(changed_serps)
        # noinspection PyTypeChecker
        changed_serps = tqdm(
            changed_serps, total=num_changed_serps,
            desc="Parsing URL page", unit="SERP")
        actions = chain.from_iterable(
            _parse_serp_url_page_action(config, serp)
            for serp in changed_serps
        )
        config.es.bulk(actions)
    else:
        echo("No new/changed SERPs.")
