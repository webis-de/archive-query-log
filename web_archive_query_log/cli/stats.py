from asyncio import run
from gzip import GzipFile
from pathlib import Path

from click import option, argument, STRING, IntRange, BOOL
from fastwarc import ArchiveIterator, WarcRecordType
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL, LOGGER
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam, ServiceChoice

# See:
# https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md#pagination-api
_URLS_PER_BLOCK = 3000
_BLOCKS_PER_PAGE = 50


@main.group("stats")
def stats_group():
    pass


def _data_directory_option():
    return option(
        "-d", "--data-directory", "--data-directory-path",
        type=PathParam(
            exists=True,
            file_okay=False,
            dir_okay=True,
            writable=True,
            readable=False,
            resolve_path=True,
            path_type=Path,
        ),
        default=DATA_DIRECTORY_PATH
    )


def _focused_argument():
    return option(
        "-f", "--focused",
        type=BOOL,
        default=False,
        is_flag=True,
    )


def _service_name_argument():
    return argument(
        "service",
        type=ServiceChoice(),
        required=True,
    )


def _domain_argument():
    return argument(
        "domain",
        type=STRING,
        required=False,
    )


def _cdx_page_argument():
    return argument(
        "cdx_page",
        type=IntRange(min=0),
        required=False,
    )


@stats_group.command(
    "all-archived-urls",
    help="Get upper bound for the number of all archived URLs from "
         "the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def all_archived_urls_command(
        data_directory: Path,
        focused: bool,
        service: str | None,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.urls.fetch import ArchivedUrlsFetcher, \
        UrlMatchScope
    service_config = SERVICES[service]
    match_scope = UrlMatchScope.PREFIX if focused else UrlMatchScope.DOMAIN
    fetcher = ArchivedUrlsFetcher(
        match_scope=match_scope,
        include_status_codes={200},
        exclude_status_codes=set(),
        include_mime_types={"text/html"},
        exclude_mime_types=set(),
        cdx_api_url=CDX_API_URL
    )
    if focused:
        if len(service_config.focused_url_prefixes) == 0:
            LOGGER.warning(
                f"No focused URL prefixes configured for service {service}."
            )
    num_pages = run(fetcher.num_service_pages(
        data_directory=data_directory,
        focused=focused,
        service=service_config,
        domain=domain,
        cdx_page=cdx_page,
    ))
    print(num_pages * _BLOCKS_PER_PAGE * _URLS_PER_BLOCK)


@stats_group.command(
    "archived-urls",
    help="Get number of fetched  archived URLs from "
         "the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_urls_command(
        data_directory: Path,
        focused: bool,
        service: str | int,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    glob_paths = []
    if focused:
        glob_paths.append("focused")
    glob_paths.append("archived-urls")
    glob_paths.append(service)
    if domain is not None:
        glob_paths.append(f"{domain}*")
    else:
        glob_paths.append("*")
    if cdx_page is not None:
        glob_paths.append(f"*{cdx_page}.jsonl.gz")
    else:
        glob_paths.append(f"*.jsonl.gz")
    glob_path = "/".join(glob_paths)
    total_paths = sum(1 for _ in data_directory.glob(glob_path))
    count = 0
    paths = data_directory.glob(glob_path)
    paths = tqdm(
        paths,
        total=total_paths,
        desc="Count archived URLs",
        unit="file",
    )
    for path in paths:
        with GzipFile(path, "r") as file:
            count += sum(1 for _ in file)
    print(count)


@stats_group.command(
    "archived-query-urls",
    help="Get number of queries from fetched archived URLs.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_query_urls_command(
        data_directory: Path,
        focused: bool,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    glob_paths = []
    if focused:
        glob_paths.append("focused")
    glob_paths.append("archived-query-urls")
    glob_paths.append(service)
    if domain is not None:
        glob_paths.append(f"{domain}*")
    else:
        glob_paths.append("*")
    if cdx_page is not None:
        glob_paths.append(f"*{cdx_page}.jsonl.gz")
    else:
        glob_paths.append(f"*.jsonl.gz")
    glob_path = "/".join(glob_paths)
    total_paths = sum(1 for _ in data_directory.glob(glob_path))
    count = 0
    paths = data_directory.glob(glob_path)
    paths = tqdm(
        paths,
        total=total_paths,
        desc="Count archived URLs",
        unit="file",
    )
    for path in paths:
        with GzipFile(path, "r") as file:
            count += sum(1 for _ in file)
    print(count)


@stats_group.command(
    "archived-raw-serps",
    help="Get number of raw SERP contents (in WARC files) for parsed queries.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_raw_serps_command(
        data_directory: Path,
        focused: bool,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    glob_paths = []
    if focused:
        glob_paths.append("focused")
    glob_paths.append("archived-raw-serps")
    glob_paths.append(service)
    if domain is not None:
        glob_paths.append(f"{domain}*")
    else:
        glob_paths.append("*")
    if cdx_page is not None:
        glob_paths.append(f"*{cdx_page}")
    else:
        glob_paths.append("*")
    glob_paths.append(f"*.warc.gz")
    glob_path = "/".join(glob_paths)
    print(glob_path)
    total_paths = sum(1 for _ in data_directory.glob(glob_path))
    count = 0
    paths = data_directory.glob(glob_path)
    paths = tqdm(
        paths,
        total=total_paths,
        desc="Count archived URLs",
        unit="file",
    )
    for path in paths:
        with path.open("rb") as file:
            count += sum(1 for _ in ArchiveIterator(
                file,
                record_types=WarcRecordType.response,
            ))
    print(count)


@stats_group.command(
    "archived-parsed-serps",
    help="Get number of parsed SERPs.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_parsed_serps_command(
        data_directory: Path,
        focused: bool,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    glob_paths = []
    if focused:
        glob_paths.append("focused")
    glob_paths.append("archived-parsed-serps")
    glob_paths.append(service)
    if domain is not None:
        glob_paths.append(f"{domain}*")
    else:
        glob_paths.append("*")
    if cdx_page is not None:
        glob_paths.append(f"*{cdx_page}.jsonl.gz")
    else:
        glob_paths.append(f"*.jsonl.gz")
    glob_path = "/".join(glob_paths)
    total_paths = sum(1 for _ in data_directory.glob(glob_path))
    count = 0
    paths = data_directory.glob(glob_path)
    paths = tqdm(
        paths,
        total=total_paths,
        desc="Count archived URLs",
        unit="file",
    )
    for path in paths:
        with GzipFile(path, "r") as file:
            count += sum(1 for _ in file)
    print(count)


@stats_group.command(
    "archived-raw-search-results",
    help="Get number of downloaded raw search result contents (as WARC files) "
         "for parsed SERPs.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_raw_search_results_command(
        data_directory: Path,
        focused: bool,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    raise NotImplementedError()


@stats_group.command(
    "archived-parsed-search-results",
    help="Parse search results from raw search result contents.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_parsed_search_results_command(
        data_directory: Path,
        focused: bool,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    raise NotImplementedError()
