from asyncio import run
from pathlib import Path

from click import option, argument
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
        "service_name",
        type=ServiceChoice(),
        required=True,
    )


@service_group.command(
    "archived-urls",
    help="Fetch archived URLs from the Wayback Machine's CDX API.",
)
@_data_directory_option()
@_service_name_argument()
def urls(data_directory: Path, service_name: str) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.urls.fetch import ArchivedUrlsFetcher, \
        UrlMatchScope
    from web_archive_query_log.util.urls import safe_quote_url
    service = SERVICES[service_name]
    service_dir = data_directory / service.name
    fetcher = ArchivedUrlsFetcher(
        match_scope=UrlMatchScope.DOMAIN,
        include_status_codes={200},
        exclude_status_codes=set(),
        include_mime_types={"text/html"},
        exclude_mime_types=set(),
        cdx_api_url=CDX_API_URL
    )
    domain_dirs = {
        domain: service_dir / safe_quote_url(domain)
        for domain in set(service.domains)
    }
    for domain_dir in domain_dirs.values():
        domain_dir.mkdir(parents=True, exist_ok=True)
    run(fetcher.fetch_many({
        domain: domain_dir / "urls.jsonl.gz"
        for domain, domain_dir in domain_dirs.items()
    }))


@service_group.command(
    "archived-serp-urls",
    help="Parse queries from fetched archived URLs.",
)
@_data_directory_option()
@_service_name_argument()
def queries(data_directory: Path, service_name: str) -> None:
    from web_archive_query_log.config import SERVICES
    from web_archive_query_log.queries.parse import ArchivedSerpUrlsParser
    service = SERVICES[service_name]
    service_dir = data_directory / service.name
    parser = ArchivedSerpUrlsParser(
        query_parsers=service.query_parsers,
        page_parsers=service.page_parsers,
        offset_parsers=service.offset_parsers,
        verbose=True,
    )
    domains = service.domains
    domains = tqdm(
        domains,
        desc=f"Parse queries",
        unit="domain",
    )
    for domain in domains:
        domain_dir = service_dir / domain
        parser.parse(
            input_path=domain_dir / "urls.jsonl.gz",
            output_path=domain_dir / "serp-urls.jsonl.gz",
        )


@service_group.command(
    "archived-serp-contents",
    help="Download SERP contents (as WARC files) for parsed queries.",
)
@_data_directory_option()
@_service_name_argument()
def fetch_service(
        data_directory: Path,
        service_name: str,
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
def fetch_service(
        data_directory: Path,
        service_name: str,
) -> None:
    raise NotImplementedError()
