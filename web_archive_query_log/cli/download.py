from asyncio import run
from pathlib import Path

from click import argument, Path as PathParam

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
    downloader = WebArchiveWarcDownloader(
        ArchivedUrls(urls_file),
        download_dir,
    )
    run(downloader.download())
