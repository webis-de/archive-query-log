from asyncio import run
from pathlib import Path

from click import argument, Path as PathParam

from web_archive_query_log.cli import main
from web_archive_query_log.urls.util import read_urls


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
    downloader = WebArchiveWarcDownloader(download_dir)
    urls = read_urls(urls_file)
    run(downloader.download(urls))
