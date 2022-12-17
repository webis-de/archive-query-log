from asyncio import run
from pathlib import Path

from click import option, argument, STRING, IntRange, BOOL

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam, ServiceChoice


@main.group("make")
def make_group():
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


@make_group.command(
    "archived-urls",
    help="Fetch archived URLs from the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_urls_command(
        data_directory: Path,
        focused: bool,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.urls.fetch import ArchivedUrlsFetcher, \
        UrlMatchScope
    service_config = SERVICES[service]
    fetcher = ArchivedUrlsFetcher(
        match_scope=UrlMatchScope.DOMAIN,
        include_status_codes={200},
        exclude_status_codes=set(),
        include_mime_types={"text/html"},
        exclude_mime_types=set(),
        cdx_api_url=CDX_API_URL
    )
    run(fetcher.fetch_service(
        data_directory=data_directory,
        focused=focused,
        service=service_config,
        domain=domain,
        cdx_page=cdx_page,
    ))


@make_group.command(
    "archived-query-urls",
    help="Parse queries from fetched archived URLs.",
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
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.queries.parse import ArchivedQueryUrlParser
    service_config = SERVICES[service]
    parser = ArchivedQueryUrlParser(
        query_parsers=service_config.query_parsers,
        page_parsers=service_config.page_parsers,
        offset_parsers=service_config.offset_parsers,
    )
    parser.parse_service(
        data_directory=data_directory,
        focused=focused,
        service=service_config,
        domain=domain,
        cdx_page=cdx_page,
    )


@make_group.command(
    "archived-raw-serps",
    help="Download raw SERP contents (as WARC files) for parsed queries.",
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
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.download.warc import WebArchiveWarcDownloader
    service_config = SERVICES[service]
    downloader = WebArchiveWarcDownloader(verbose=True)
    run(downloader.download_service(
        data_directory=data_directory,
        focused=focused,
        service=service_config,
        domain=domain,
        cdx_page=cdx_page,
    ))


@make_group.command(
    "archived-parsed-serps",
    help="Parse SERP results from raw SERPs.",
)
@_data_directory_option()
@_focused_argument()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_parsed_serps_command(
        data_directory: Path,
        focused: bool,
        service_name: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    raise NotImplementedError()


@make_group.command(
    "archived-raw-search-results",
    help="Download raw search result contents (as WARC files) "
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


@make_group.command(
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
