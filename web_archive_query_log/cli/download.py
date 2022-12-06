from asyncio import run
from pathlib import Path

from click import argument, Path as PathParam, option
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.cli.util import ServiceChoice
from web_archive_query_log.cli import main


@main.group("download")
def download():
    pass


@download.command("warc")
@argument(
    "urls-file",
    type=PathParam(
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        path_type=Path,
    )
)
@argument(
    "download-dir",
    type=PathParam(
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
)
def warc(download_dir: Path, urls_file: Path) -> None:
    from web_archive_query_log.download.warc import WebArchiveWarcDownloader
    from web_archive_query_log.urls.iterable import ArchivedUrls
    downloader = WebArchiveWarcDownloader()
    run(downloader.download(
        download_dir,
        ArchivedUrls(urls_file),
    ))


@download.command("download-service")
@option(
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
@argument(
    "service_name",
    type=ServiceChoice(),
    required=True,
)
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
        desc=f"Download SERPs",
        unit="domain",
    )
    for domain in domains:
        domain_dir = service_dir / domain
        run(downloader.download(
            domain_dir / "serps",
            ArchivedSerpUrls(domain_dir / "serp-urls.jsonl.gz"),
        ))
