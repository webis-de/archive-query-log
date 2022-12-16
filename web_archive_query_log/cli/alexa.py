from pathlib import Path

from click import option, Path as PathParam, argument

from web_archive_query_log import DATA_DIRECTORY_PATH, CDX_API_URL
from web_archive_query_log.cli.main import main
from web_archive_query_log.cli.util import URL


@main.group("alexa")
def alexa():
    pass


@alexa.command("fetch-archived-urls")
@option(
    "-u", "--api-url", "--cdx-api-url",
    type=URL,
    default=CDX_API_URL,
)
@argument(
    "output-path",
    type=PathParam(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH / "alexa-top-1m-archived-urls.jsonl"
)
def archived_urls(api_url: str, output_path: Path) -> None:
    from web_archive_query_log.services.alexa import AlexaTop1MArchivedUrls
    AlexaTop1MArchivedUrls(
        output_path=output_path,
        cdx_api_url=api_url,
    ).fetch()


@alexa.command("fuse-domains")
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
    from web_archive_query_log.services.alexa import AlexaTop1MFusedDomains
    AlexaTop1MFusedDomains(
        data_directory_path=data_dir,
        cdx_api_url=api_url,
    ).fetch()
