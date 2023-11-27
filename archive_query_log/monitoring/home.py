from datetime import datetime
from typing import NamedTuple, Type

from elasticsearch_dsl.query import Exists, Query, Term
from expiringdict import ExpiringDict
from flask import render_template, Response, make_response

from archive_query_log.config import Config
from archive_query_log.orm import Archive, Provider, Source, Capture, \
    BaseDocument, Serp, Result, UrlQueryParser, UrlPageParser, \
    UrlOffsetParser, WarcQueryParser, WarcSnippetsParser
from archive_query_log.utils.time import utc_now


class Statistics(NamedTuple):
    name: str
    description: str
    total: str
    disk_size: str | None
    last_modified: datetime | None


class Progress(NamedTuple):
    input_name: str
    output_name: str
    description: str
    total: int
    current: int


DocumentType = Type[BaseDocument]

_statistics_cache: dict[
    tuple[DocumentType, str],
    Statistics,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=15,
)


def _convert_bytes(bytes_count: int) -> str:
    step_unit = 1000.0
    bytes_count_decimal: float = bytes_count
    for unit in ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB", "RB"]:
        if bytes_count_decimal < step_unit:
            return f"{bytes_count_decimal:3.1f} {unit}"
        bytes_count_decimal /= step_unit
    return f"{bytes_count_decimal:3.1f} QB"


def _get_statistics(
        config: Config,
        name: str,
        description: str,
        document: DocumentType,
        filter_query: Query | None = None,
) -> Statistics:
    key = (document, repr(filter_query))
    if key in _statistics_cache:
        return _statistics_cache[key]

    document.index().refresh(using=config.es.client)
    stats = document.index().stats(using=config.es.client)
    search = document.search(using=config.es.client)
    if filter_query is not None:
        search = search.filter(filter_query)
    total = search.count()
    last_modified_response = (
        search
        .query(Exists(field="last_modified"))
        .sort("-last_modified")
        .extra(size=1)
        .execute()
    )
    if last_modified_response.hits.total.value == 0:
        last_modified = None
    else:
        last_modified = last_modified_response.hits[0].last_modified

    statistics = Statistics(
        name=name,
        description=description,
        total=total,
        disk_size=(
            _convert_bytes(stats["_all"]["total"]["store"]["size_in_bytes"])
            if filter_query is None else None
        ),
        last_modified=last_modified,
    )
    _statistics_cache[key] = statistics
    return statistics


_progress_cache: dict[
    tuple[DocumentType, str, str],
    Progress,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=15,
)


def _get_processed_progress(
        config: Config,
        input_name: str,
        output_name: str,
        description: str,
        document: DocumentType,
        status_field: str,
        filter_query: Query | None = None,
) -> Progress:
    key = (document, repr(filter_query), status_field)
    if key in _progress_cache:
        return _progress_cache[key]

    document.index().refresh(using=config.es.client)
    search = document.search(using=config.es.client)
    if filter_query is not None:
        search = search.filter(filter_query)
    total = search.count()
    search_processed = search.filter(Term(**{status_field: False}))
    total_processed = search_processed.count()
    progress = Progress(
        input_name=input_name,
        output_name=output_name,
        description=description,
        total=total,
        current=total_processed,
    )
    _progress_cache[key] = progress
    return progress


def home(config: Config) -> str | Response:
    statistics_list: list[Statistics] = [
        _get_statistics(
            config=config,
            name="Archives",
            description="Web archiving services that offer CDX "
                        "and Memento APIs.",
            document=Archive,
        ),
        _get_statistics(
            config=config,
            name="Providers",
            description="Search providers, i.e., websites that offer "
                        "a search functionality.",
            document=Provider,
        ),
        _get_statistics(
            config=config,
            name="Sources",
            description="The cross product of all archives and "
                        "the provider's domains and URL prefixes.",
            document=Source,
        ),
        _get_statistics(
            config=config,
            name="Captures",
            description="Captures matching from the archives "
                        "that match domain and URL prefixes.",
            document=Capture,
        ),
        _get_statistics(
            config=config,
            name="SERPs",
            description="Search engine result pages that have been "
                        "identified among the captures.",
            document=Serp,
        ),
        _get_statistics(
            config=config,
            name="+ URL query",
            description="SERPs for which the query has been parsed "
                        "from the URL.",
            document=Serp,
            filter_query=Exists(field="url_query"),
        ),
        _get_statistics(
            config=config,
            name="+ URL page",
            description="SERPs for which the page has been parsed "
                        "from the URL.",
            document=Serp,
            filter_query=Exists(field="url_page"),
        ),
        _get_statistics(
            config=config,
            name="+ URL offset",
            description="SERPs for which the offset has been parsed "
                        "from the URL.",
            document=Serp,
            filter_query=Exists(field="url_offset"),
        ),
        _get_statistics(
            config=config,
            name="+ WARC",
            description="SERPs for which the WARC has been downloaded.",
            document=Serp,
            filter_query=Exists(field="warc_location"),
        ),
        _get_statistics(
            config=config,
            name="+ WARC query",
            description="SERPs for which the query has been parsed "
                        "from the WARC.",
            document=Serp,
            filter_query=Exists(field="warc_query"),
        ),
        _get_statistics(
            config=config,
            name="+ WARC snippets",
            description="SERPs for which the snippets have been parsed "
                        "from the WARC.",
            document=Serp,
            filter_query=Exists(field="warc_snippets_parser.id"),
        ),
        _get_statistics(
            config=config,
            name="Results",
            description="Search result from the SERPs.",
            document=Result,
        ),
        _get_statistics(
            config=config,
            name="URL query parsers",
            description="Parser to get the query from a SERP's URL.",
            document=UrlQueryParser,
        ),
        _get_statistics(
            config=config,
            name="URL page parsers",
            description="Parser to get the page from a SERP's URL.",
            document=UrlPageParser,
        ),
        _get_statistics(
            config=config,
            name="URL offset parsers",
            description="Parser to get the offset from a SERP's URL.",
            document=UrlOffsetParser,
        ),
        _get_statistics(
            config=config,
            name="WARC query parsers",
            description="Parser to get the query from a SERP's WARC contents.",
            document=WarcQueryParser,
        ),
        _get_statistics(
            config=config,
            name="WARC snippets parsers",
            description="Parser to get the snippets from a SERP's "
                        "WARC contents.",
            document=WarcSnippetsParser,
        ),
    ]

    progress_list: list[Progress] = [
        _get_processed_progress(
            config=config,
            input_name="Archives",
            output_name="Sources",
            description="Build sources for all archives.",
            document=Archive,
            filter_query=~Exists(field="exclusion_reason"),
            status_field="should_build_sources",
        ),
        _get_processed_progress(
            config=config,
            input_name="Providers",
            output_name="Sources",
            description="Build sources for all search providers.",
            document=Provider,
            filter_query=~Exists(field="exclusion_reason"),
            status_field="should_build_sources",
        ),
        _get_processed_progress(
            config=config,
            input_name="Sources",
            output_name="Captures",
            description="Fetch CDX captures for all domains and "
                        "prefixes in the sources.",
            document=Source,
            status_field="should_fetch_captures",
        ),
        _get_processed_progress(
            config=config,
            input_name="Captures",
            output_name="SERPs",
            description="Parse queries from capture URLs.",
            document=Capture,
            status_field="url_query_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse page from SERP URLs.",
            document=Serp,
            status_field="url_page_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse offset from SERP URLs.",
            document=Serp,
            status_field="url_offset_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Download WARCs.",
            document=Serp,
            filter_query=Term(capture__status_code=200),
            status_field="warc_downloader.should_download",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse query from WARC contents.",
            document=Serp,
            filter_query=Exists(field="warc_location"),
            status_field="warc_query_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse snippets from WARC contents.",
            document=Serp,
            filter_query=Exists(field="warc_location"),
            status_field="warc_snippets_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="Results",
            output_name="Results",
            description="Download WARCs.",
            document=Result,
            filter_query=Exists(field="snippet.url"),
            status_field="warc_downloader.should_download",
        ),
    ]

    etag = str(hash((
        tuple(statistics_list),
        tuple(progress_list),
    )))

    response = make_response(
        render_template(
            "home.html",
            statistics_list=statistics_list,
            progress_list=progress_list,
            year=utc_now().year,
        )
    )
    response.headers.add("ETag", etag)
    return response
