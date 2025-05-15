from datetime import datetime
from typing import Iterable, NamedTuple, Type, TYPE_CHECKING, Any
from pathlib import Path

from boto3 import Session
from elasticsearch_dsl.query import Exists, Query, Term, Nested
from expiringdict import ExpiringDict
from flask import render_template, Response, make_response
from tqdm import tqdm

from archive_query_log.config import Config
from archive_query_log.orm import (
    Archive,
    Provider,
    Source,
    Capture,
    BaseDocument,
    Serp,
    Result,
    UrlQueryParser,
    UrlPageParser,
    UrlOffsetParser,
    WarcQueryParser,
    WarcSnippetsParser,
)
from archive_query_log.utils.time import utc_now

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = Any

_CACHE_SECONDS_STATISTICS = 60 * 30  # 10 minutes
_CACHE_SECONDS_WARC_CACHE_STATISTICS = 60 * 60 * 1  # 1 hour
_CACHE_SECONDS_PROGRESS = 60 * 10  # 10 minutes


class Statistics(NamedTuple):
    name: str
    description: str
    total: int
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
    tuple[DocumentType, str, str | None, str | None, str, str],
    Statistics,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=_CACHE_SECONDS_STATISTICS,
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
    index: str,
    document: DocumentType,
    filter_field: str | None = None,
    status_field: str | None = None,
    last_modified_field: str = "last_modified",
) -> Statistics:
    key = (document, index, filter_field, status_field, last_modified_field, name)
    if key in _statistics_cache:
        return _statistics_cache[key]
    print(f"Get statistics: {name}")

    search = document.search(using=config.es.client, index=index)
    search = search.filter(Exists(field=last_modified_field))
    if filter_field is not None:
        if "." in filter_field:
            search = search.filter(Nested(
                path=filter_field.split(".")[0],
                query=Exists(field=filter_field),
            ))
        else:
            search = search.filter(Exists(field=filter_field))
    if status_field is not None:
        search = search.filter(Term(**{status_field: False}))

    total = search.count()
    last_modified_response = (
        search.sort(f"-{last_modified_field}").extra(size=1).execute()
    )
    if last_modified_response.hits.total.value == 0:
        last_modified = None
    else:
        last_modified = last_modified_response.hits[0]
        for part in last_modified_field.split("."):
            last_modified = last_modified[part]

    stats = config.es.client.indices.stats(index=index)
    disk_size = (
        _convert_bytes(stats["_all"]["total"]["store"]["size_in_bytes"])
        if last_modified_field == "last_modified"
        else None
    )

    statistics = Statistics(
        name=name,
        description=description,
        total=total,
        disk_size=disk_size,
        last_modified=last_modified,
    )
    _statistics_cache[key] = statistics
    return statistics


_warc_cache_statistics_cache: dict[
    tuple[Path, bool],
    Statistics,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=_CACHE_SECONDS_STATISTICS,
)


def _get_warc_cache_statistics(
    name: str,
    description: str,
    cache_path: Path,
    temporary: bool = False,
) -> Statistics:
    """Retrieve WARC cache statistics."""
    key = (cache_path, temporary)
    if key in _warc_cache_statistics_cache:
        return _warc_cache_statistics_cache[key]
    print(f"Get statistics: {name}")

    file_paths: Iterable[Path]
    if temporary:
        file_paths = cache_path.glob(".*.warc.gz")

    else:
        file_paths = cache_path.glob("[!.]*.warc.gz")

    disk_size_bytes: int = 0
    last_modified: float = 0
    warc_count: int = 0

    for file_path in tqdm(
        file_paths, desc="Compute WARC cache statistics", unit="file"
    ):
        try:
            stat = file_path.stat(follow_symlinks=False)
            disk_size_bytes += stat.st_size
            last_modified = max(
                last_modified,
                stat.st_mtime,
            )
            warc_count += 1
        except FileNotFoundError:
            # Ignore files that have been deleted while processing.
            pass

    statistics = Statistics(
        name=name,
        description=description,
        total=warc_count,
        disk_size=_convert_bytes(disk_size_bytes),
        last_modified=datetime.fromtimestamp(last_modified) if last_modified else None,
    )
    _warc_cache_statistics_cache[key] = statistics
    return statistics


_warc_s3_statistics_cache: dict[
    str,
    Statistics,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=_CACHE_SECONDS_STATISTICS,
)


def _get_warc_s3_statistics(
    config: Config,
    name: str,
    description: str,
    bucket_name: str,
) -> Statistics:
    """Retrieve WARC cache statistics."""
    key = bucket_name
    if key in _warc_s3_statistics_cache:
        return _warc_s3_statistics_cache[key]
    print(f"Get statistics: {name}")

    client = Session().client(
        service_name="s3",
        endpoint_url=config.s3.endpoint_url,
        aws_access_key_id=config.s3.access_key,
        aws_secret_access_key=config.s3.secret_key,
    )
    pages = client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket_name,
    )

    disk_size_bytes: int = 0
    last_modified: float = 0
    warc_count: int = 0
    for page in pages:
        for obj in page["Contents"]:
            disk_size_bytes += obj["Size"]
            last_modified = max(last_modified, obj["LastModified"].timestamp())
            warc_count += 1

    statistics = Statistics(
        name=name,
        description=description,
        total=warc_count,
        disk_size=_convert_bytes(disk_size_bytes),
        last_modified=datetime.fromtimestamp(last_modified) if last_modified else None,
    )
    _warc_s3_statistics_cache[key] = statistics
    return statistics


_progress_cache: dict[
    tuple[DocumentType, str, str, str],
    Progress,
] = ExpiringDict(
    max_len=100,
    max_age_seconds=_CACHE_SECONDS_PROGRESS,
)


def _get_processed_progress(
    config: Config,
    input_name: str,
    output_name: str,
    description: str,
    document: DocumentType,
    index: str,
    status_field: str,
    filter_query: Query | None = None,
) -> Progress:
    key = (document, index, repr(filter_query), status_field)
    if key in _progress_cache:
        return _progress_cache[key]
    print(f"Get progress: {input_name} → {output_name}")

    config.es.client.indices.refresh(index=index)
    search = document.search(using=config.es.client, index=index)
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
            description="Web archiving services that offer CDX and Memento APIs.",
            document=Archive,
            index=config.es.index_archives,
        ),
        _get_statistics(
            config=config,
            name="Providers",
            description="Search providers, i.e., websites that offer "
            "a search functionality.",
            document=Provider,
            index=config.es.index_providers,
        ),
        _get_statistics(
            config=config,
            name="Sources",
            description="Cross product of archives and "
            "provider domains and URL prefixes.",
            document=Source,
            index=config.es.index_sources,
        ),
        _get_statistics(
            config=config,
            name="Captures",
            description="Captures from the archives "
            "that match domain and URL prefixes.",
            document=Capture,
            index=config.es.index_captures,
        ),
        _get_statistics(
            config=config,
            name="SERPs",
            description="Search engine result pages "
            "identified among the captures.",
            document=Serp,
            index=config.es.index_serps,
        ),
        _get_statistics(
            config=config,
            name="+ URL query",
            description="SERPs for which the query has been parsed from the URL.",
            document=Serp,
            index=config.es.index_serps,
        ),
        _get_statistics(
            config=config,
            name="+ URL page",
            description="SERPs for which the page has been parsed from the URL.",
            document=Serp,
            index=config.es.index_serps,
            filter_field="url_page",
            status_field="url_page_parser.should_parse",
            last_modified_field="url_page_parser.last_parsed",
        ),
        _get_statistics(
            config=config,
            name="+ URL offset",
            description="SERPs for which the offset has been parsed from the URL.",
            document=Serp,
            index=config.es.index_serps,
            filter_field="url_offset",
            status_field="url_offset_parser.should_parse",
            last_modified_field="url_offset_parser.last_parsed",
        ),
        _get_statistics(
            config=config,
            name="+ WARC",
            description="SERPs for which the WARC has been downloaded.",
            document=Serp,
            index=config.es.index_serps,
            filter_field="warc_location",
            status_field="warc_downloader.should_download",
            last_modified_field="warc_downloader.last_downloaded",
        ),
        _get_statistics(
            config=config,
            name="+ WARC query",
            description="SERPs for which the query has been parsed from the WARC.",
            document=Serp,
            index=config.es.index_serps,
            filter_field="warc_query",
            status_field="warc_query_parser.should_parse",
            last_modified_field="warc_query_parser.last_parsed",
        ),
        _get_statistics(
            config=config,
            name="+ WARC snippets",
            description="SERPs for which the snippets have been parsed from the WARC.",
            document=Serp,
            index=config.es.index_serps,
            filter_field="warc_snippets.id",
            status_field="warc_snippets_parser.should_parse",
            last_modified_field="warc_snippets_parser.last_parsed",
        ),
        _get_warc_cache_statistics(
            name="→ WARC cache (in progress)",
            description="Downloaded SERP WARC files still locked by a downloader.",
            cache_path=config.warc_cache.path_serps,
            temporary=True,
        ),
        _get_warc_cache_statistics(
            name="→ WARC cache (ready)",
            description="Downloaded SERP WARC files ready to be uploaded to S3.",
            cache_path=config.warc_cache.path_serps,
            temporary=False,
        ),
        _get_warc_s3_statistics(
            config=config,
            name="→ WARC S3",
            description="Downloaded SERP WARC files finalized in S3 block storage.",
            bucket_name=config.s3.bucket_name,
        ),
        _get_statistics(
            config=config,
            name="Results",
            description="Search results from the SERPs.",
            document=Result,
            index=config.es.index_results,
        ),
        # _get_statistics(
        #     config=config,
        #     name="+ WARC",
        #     description="Search results for which the WARC has been downloaded.",
        #     document=Result,
        #     index=config.es.index_results,
        #     filter_field="warc_location",
        #     status_field="warc_downloader.should_download",
        #     last_modified_field="warc_downloader.last_downloaded",
        # ),
        _get_statistics(
            config=config,
            name="URL query parsers",
            description="Parser to get the query from a SERP's URL.",
            document=UrlQueryParser,
            index=config.es.index_url_query_parsers,
        ),
        _get_statistics(
            config=config,
            name="URL page parsers",
            description="Parser to get the page from a SERP's URL.",
            document=UrlPageParser,
            index=config.es.index_url_page_parsers,
        ),
        _get_statistics(
            config=config,
            name="URL offset parsers",
            description="Parser to get the offset from a SERP's URL.",
            document=UrlOffsetParser,
            index=config.es.index_url_offset_parsers,
        ),
        _get_statistics(
            config=config,
            name="WARC query parsers",
            description="Parser to get the query from a SERP's WARC contents.",
            document=WarcQueryParser,
            index=config.es.index_warc_query_parsers,
        ),
        _get_statistics(
            config=config,
            name="WARC snippets parsers",
            description="Parser to get the snippets from a SERP's WARC contents.",
            document=WarcSnippetsParser,
            index=config.es.index_warc_snippets_parsers,
        ),
    ]

    progress_list: list[Progress] = [
        _get_processed_progress(
            config=config,
            input_name="Archives",
            output_name="Sources",
            description="Build sources for all archives.",
            document=Archive,
            index=config.es.index_archives,
            filter_query=~Exists(field="exclusion_reason"),
            status_field="should_build_sources",
        ),
        _get_processed_progress(
            config=config,
            input_name="Providers",
            output_name="Sources",
            description="Build sources for all search providers.",
            document=Provider,
            index=config.es.index_providers,
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
            index=config.es.index_sources,
            filter_query=(
                # FIXME: The UK Web Archive is facing an outage: https://www.webarchive.org.uk/#en
                ~Term(archive__id="90be629c-2a95-52da-9ae8-ca58454c9826")
            ),
            status_field="should_fetch_captures",
        ),
        _get_processed_progress(
            config=config,
            input_name="Captures",
            output_name="SERPs",
            description="Parse queries from capture URLs.",
            document=Capture,
            index=config.es.index_captures,
            status_field="url_query_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse page from SERP URLs.",
            document=Serp,
            index=config.es.index_serps,
            status_field="url_page_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse offset from SERP URLs.",
            document=Serp,
            index=config.es.index_serps,
            status_field="url_offset_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Download WARCs.",
            document=Serp,
            index=config.es.index_serps,
            filter_query=(
                Term(capture__status_code=200)
            ),
            status_field="warc_downloader.should_download",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse query from WARC contents.",
            document=Serp,
            index=config.es.index_serps,
            filter_query=Exists(field="warc_location"),
            status_field="warc_query_parser.should_parse",
        ),
        _get_processed_progress(
            config=config,
            input_name="SERPs",
            output_name="SERPs",
            description="Parse snippets from WARC contents.",
            document=Serp,
            index=config.es.index_serps,
            filter_query=Exists(field="warc_location"),
            status_field="warc_snippets_parser.should_parse",
        ),
        # _get_processed_progress(
        #     config=config,
        #     input_name="Results",
        #     output_name="Results",
        #     description="Download WARCs.",
        #     document=Result,
        #     index=config.es.index_results,
        #     filter_query=Exists(field="snippet.url"),
        #     status_field="warc_downloader.should_download",
        # ),
    ]

    etag = str(
        hash(
            (
                tuple(statistics_list),
                tuple(progress_list),
            )
        )
    )

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
