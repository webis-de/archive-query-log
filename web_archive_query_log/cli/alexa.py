from pathlib import Path

from click import option, Path as PathParam

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL
from web_archive_query_log.cli.main import main
from web_archive_query_log.cli.util import URL
from web_archive_query_log.services.alexa import AlexaTop1MArchivedUrls, \
    AlexaTop1MFusedDomains


@main.group("alexa")
def alexa():
    pass


@alexa.command("archived-urls")
@option(
    "-d", "--data-dir",
    type=PathParam(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH
)
@option(
    "-u", "--api-url", "--cdx-api-url",
    type=URL,
    default=CDX_API_URL,
)
def archived_urls(data_dir: Path, api_url: str) -> None:
    AlexaTop1MArchivedUrls(
        data_directory_path=data_dir,
        cdx_api_url=api_url,
    ).fetch()


@alexa.command("domains")
@option(
    "-d", "--data-dir",
    type=PathParam(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH
)
@option(
    "-u", "--api-url", "--cdx-api-url",
    type=URL,
    default=CDX_API_URL,
)
def domains(data_dir: Path, api_url: str) -> None:
    AlexaTop1MFusedDomains(
        data_directory_path=data_dir,
        cdx_api_url=api_url,
    ).fetch()
