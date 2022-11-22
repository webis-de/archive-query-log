from pathlib import Path
from typing import Optional

from click import Choice, argument, option, INT

from web_archive_query_log import CDX_API_URL, DATA_DIRECTORY_PATH
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import URL, PathParam
from web_archive_query_log.config import SOURCES
from web_archive_query_log.queries import InternetArchiveQueries
from web_archive_query_log.results import InternetArchiveSerps


@main.group("serps")
def serps():
    pass


@serps.command("fetch")
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
@option(
    "-c", "--chunk-size",
    type=INT,
    default=10,
)
@argument(
    "search-engine",
    type=Choice(sorted(SOURCES.keys()), case_sensitive=False),
)
def fetch(
        search_engine: str,
        data_dir: Path,
        api_url: str,
        chunk_size: int,
) -> None:
    config = SOURCES[search_engine]
    for source in config:
        serps = InternetArchiveSerps(
            queries=InternetArchiveQueries(
                url_prefix=source.url_prefix,
                parser=source.query_parser,
                data_directory_path=data_dir,
                cdx_api_url=api_url,
            ),
            parsers=source.serp_parsers,
            chunk_size=chunk_size,
        )
        serps.fetch()


@serps.command("num-chunks")
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
@option(
    "-c", "--chunk-size",
    type=INT,
    default=10,
)
@argument(
    "search-engine",
    type=Choice(sorted(SOURCES.keys()), case_sensitive=False),
    required=False,
)
def num_chunks(
        api_url: str,
        data_dir: Path,
        search_engine: Optional[str],
        chunk_size: int,
) -> None:
    configs = SOURCES.values() \
        if search_engine is None \
        else (SOURCES[search_engine],)
    total_chunks = 0
    for config in configs:
        for source in config:
            serps = InternetArchiveSerps(
                queries=InternetArchiveQueries(
                    url_prefix=source.url_prefix,
                    parser=source.query_parser,
                    data_directory_path=data_dir,
                    cdx_api_url=api_url,
                ),
                parsers=source.serp_parsers,
                chunk_size=chunk_size,
            )
            chunks = serps.num_chunks
            print(f"{source.url_prefix}: {chunks} chunks")
            total_chunks += chunks
    print(f"total: {total_chunks} chunks")
