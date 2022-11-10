from pathlib import Path

from click import group, argument, Choice, Path as PathParam, option

from internet_archive_query_log import DATA_DIRECTORY_PATH, \
    CDX_API_URL
from internet_archive_query_log.config import Config
from internet_archive_query_log.queries import InternetArchiveQueries
from internet_archive_query_log.util import URL


@group()
def internet_archive_query_log():
    pass


_CONFIGS = {
    "google": Config(
        prefixes={
            "google.com/search"
        },
        query_parameter="q",
    )
}


@internet_archive_query_log.command("fetch-queries")
@argument(
    "search-engine",
    type=Choice(sorted(_CONFIGS.keys()), case_sensitive=False),
)
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
def fetch_queries(search_engine: str, data_dir: Path, api_url: str, **kwargs):
    config = _CONFIGS[search_engine]
    for prefix in config.prefixes:
        InternetArchiveQueries(
            prefix=prefix,
            query_parameter=config.query_parameter,
            data_directory_path=data_dir,
            cdx_api_url=api_url,
        ).fetch()


if __name__ == "__main__":
    internet_archive_query_log()
