from pathlib import Path
from typing import Optional

from click import Choice, argument, option

from web_archive_query_log import CDX_API_URL, DATA_DIRECTORY_PATH
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import URL, PathParam
from web_archive_query_log.config import SOURCES
from web_archive_query_log.queries import InternetArchiveQueries


@main.group("queries")
def queries():
    pass


@queries.command("fetch")
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
@argument(
    "search-engine",
    type=Choice(sorted(SOURCES.keys()), case_sensitive=False),
)
def fetch(
        search_engine: str,
        data_dir: Path,
        api_url: str,
) -> None:
    config = SOURCES[search_engine]
    for source in config:
        queries = InternetArchiveQueries(
            url_prefix=source.url_prefix,
            parser=source.query_parser,
            data_directory_path=data_dir,
            cdx_api_url=api_url,
        )
        queries.fetch()


@queries.command("num-pages")
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
@argument(
    "search-engine",
    type=Choice(sorted(SOURCES.keys()), case_sensitive=False),
    required=False,
)
def num_pages(
        api_url: str,
        data_dir: Path,
        search_engine: Optional[str]
) -> None:
    configs = SOURCES.values() \
        if search_engine is None \
        else (SOURCES[search_engine],)
    total_pages = 0
    for config in configs:
        for source in config:
            queries = InternetArchiveQueries(
                url_prefix=source.url_prefix,
                parser=source.query_parser,
                data_directory_path=data_dir,
                cdx_api_url=api_url,
            )
            pages = queries.num_pages
            print(f"{source.url_prefix}: {pages} pages")
            total_pages += pages
    print(f"total: {total_pages} pages")
