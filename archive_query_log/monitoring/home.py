from datetime import datetime
from typing import NamedTuple, Type

from elasticsearch_dsl.query import Script, Exists
from expiringdict import ExpiringDict
from flask import render_template, Response, make_response

from archive_query_log.config import Config
from archive_query_log.orm import Archive, Provider, Source, Capture, \
    BaseDocument, Serp, Result, UrlQueryParser, UrlPageParser, UrlOffsetParser
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
    tuple[DocumentType, tuple[str, ...]],
    Statistics,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=30,
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
        required_fields: tuple[str, ...] = (),
) -> Statistics:
    key = (document, required_fields)
    if key in _statistics_cache:
        return _statistics_cache[key]

    document.index().refresh(using=config.es.client)
    stats = document.index().stats(using=config.es.client)
    search = document.search(using=config.es.client)
    if len(required_fields) > 0:
        query = Exists(field=required_fields[0])
        for required_field in required_fields[1:]:
            query &= Exists(field=required_field)
        search = search.filter(query)
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
            if len(required_fields) == 0 else ""
        ),
        last_modified=last_modified,
    )
    _statistics_cache[key] = statistics
    return statistics


_progress_cache: dict[
    tuple[DocumentType, tuple[str, ...], str],
    Progress,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=30,
)


def _get_processed_progress(
        config: Config,
        input_name: str,
        output_name: str,
        description: str,
        document: DocumentType,
        timestamp_field: str,
        required_fields: tuple[str, ...] = (),
) -> Progress:
    key = (document, required_fields, timestamp_field)
    if key in _progress_cache:
        return _progress_cache[key]

    document.index().refresh(using=config.es.client)
    search = document.search(using=config.es.client)
    if len(required_fields) > 0:
        query = Exists(field=required_fields[0])
        for required_field in required_fields[1:]:
            query &= Exists(field=required_field)
        search = search.filter(query)
    total = search.count()
    search_processed = search.filter(
        Exists(field="last_modified") &
        Exists(field=timestamp_field) &
        Script(
            script=f"doc['last_modified'].value.isBefore("
                   f"doc['{timestamp_field}'].value)",
        )
    )
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
            required_fields=("url_query",),
        ),
        _get_statistics(
            config=config,
            name="+ URL page",
            description="SERPs for which the page has been parsed "
                        "from the URL.",
            document=Serp,
            required_fields=("url_page",),
        ),
        _get_statistics(
            config=config,
            name="+ URL offset",
            description="SERPs for which the offset has been parsed "
                        "from the URL.",
            document=Serp,
            required_fields=("url_offset",),
        ),
        _get_statistics(
            config=config,
            name="+ WARC",
            description="SERPs for which the WARC has been downloaded.",
            document=Serp,
            required_fields=("warc_location",),
        ),
        _get_statistics(
            config=config,
            name="+ WARC query",
            description="SERPs for which the query has been parsed "
                        "from the WARC.",
            document=Serp,
            required_fields=("warc_query",),
        ),
        _get_statistics(
            config=config,
            name="+ WARC snippets",
            description="SERPs for which the snippets have been parsed "
                        "from the WARC.",
            document=Serp,
            required_fields=("warc_snippets",),
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
            description="Parser to get the query from a SERP URL.",
            document=UrlQueryParser,
        ),
        _get_statistics(
            config=config,
            name="URL page parsers",
            description="Parser to get the page from a SERP URL.",
            document=UrlPageParser,
        ),
        _get_statistics(
            config=config,
            name="URL offset parsers",
            description="Parser to get the offset from a SERP URL.",
            document=UrlOffsetParser,
        ),
    ]

    progress_list: list[Progress] = [
        _get_processed_progress(
            config=config,
            input_name="Archives",
            output_name="Sources",
            description="Build sources for all archives.",
            document=Archive,
            timestamp_field="last_built_sources",
        ),
        _get_processed_progress(
            config=config,
            input_name="Providers",
            output_name="Sources",
            description="Build sources for all search providers.",
            document=Provider,
            timestamp_field="last_built_sources",
        ),
        _get_processed_progress(
            config=config,
            input_name="Sources",
            output_name="Captures",
            description="Fetch CDX captures for all domains and "
                        "prefixes in the sources.",
            document=Source,
            timestamp_field="last_fetched_captures",
        ),
        _get_processed_progress(
            config=config,
            input_name="Captures",
            output_name="SERPs",
            description="Parse queries from capture URLs.",
            document=Capture,
            timestamp_field="url_query_parser.last_parsed",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse page from SERP URLs.",
            document=Serp,
            timestamp_field="url_page_parser.last_parsed",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse offset from SERP URLs.",
            document=Serp,
            timestamp_field="url_offset_parser.last_parsed",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Download WARCs.",
            document=Serp,
            timestamp_field="warc_downloader.last_downloaded",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse query from WARC contents.",
            document=Serp,
            timestamp_field="warc_query_parser.last_parsed",
            required_fields=("warc_location",),
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse snippets from WARC contents.",
            document=Serp,
            timestamp_field="warc_snippets_parser.last_parsed",
            required_fields=("warc_location",),
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
