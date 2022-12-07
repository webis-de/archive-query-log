from asyncio import run
from pathlib import Path

from click import option, argument, STRING, IntRange
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam, ServiceChoice


@main.group("service")
def service_group():
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


@service_group.command(
    "archived-urls",
    help="Fetch archived URLs from the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_urls_command(
        data_directory: Path,
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
        data_directory,
        service_config,
        domain,
        cdx_page,
    ))


@service_group.command(
    "archived-serp-urls",
    help="Parse queries from fetched archived URLs.",
)
@_data_directory_option()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_serp_urls_command(
        data_directory: Path,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.queries.parse import ArchivedSerpUrlsParser
    service_config = SERVICES[service]
    parser = ArchivedSerpUrlsParser(
        query_parsers=service_config.query_parsers,
        page_parsers=service_config.page_parsers,
        offset_parsers=service_config.offset_parsers,
    )
    parser.parse_service(
        data_directory,
        service_config,
        domain,
        cdx_page,
    )


@service_group.command(
    "archived-serp-contents",
    help="Download SERP contents (as WARC files) for parsed queries.",
)
@_data_directory_option()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_serp_contents_command(
        data_directory: Path,
        service: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.download.warc import WebArchiveWarcDownloader
    from web_archive_query_log.queries.iterable import ArchivedSerpUrls
    service = SERVICES[service_name]
    service_dir = data_directory / service.name
    downloader = WebArchiveWarcDownloader()
    domains = service.domains
    domains = tqdm(
        domains,
        desc=f"Download SERP contents",
        unit="domain",
    )
    for domain in domains:
        domain_dir = service_dir / domain
        run(downloader.download(
            domain_dir / "serps",
            ArchivedSerpUrls(domain_dir / "serp-urls.jsonl.gz"),
        ))


@service_group.command(
    "archived-serps",
    help="Parse SERP results from SERP contents.",
)
@_data_directory_option()
@_service_name_argument()
@_domain_argument()
@_cdx_page_argument()
def archived_serps_command(
        data_directory: Path,
        service_name: str,
        domain: str | None,
        cdx_page: int | None,
) -> None:
    raise NotImplementedError()
