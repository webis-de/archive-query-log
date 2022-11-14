from pathlib import Path
from typing import Optional

from click import group, argument, Choice, Path as PathParam, option, INT

from internet_archive_query_log import DATA_DIRECTORY_PATH, \
    CDX_API_URL
from internet_archive_query_log.config import SOURCES
from internet_archive_query_log.queries import InternetArchiveQueries
from internet_archive_query_log.serps import InternetArchiveSerps
from internet_archive_query_log.util import URL


@group()
def internet_archive_query_log():
    pass


@internet_archive_query_log.group()
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
def fetch_queries(
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
    "-u", "--api-url", "--cdx-api-url",
    type=URL,
    default=CDX_API_URL,
)
@argument(
    "search-engine",
    type=Choice(sorted(SOURCES.keys()), case_sensitive=False),
    required=False,
)
def num_query_pages(api_url: str, search_engine: Optional[str]) -> None:
    configs = SOURCES.values() \
        if search_engine is None \
        else (SOURCES[search_engine],)
    total_pages = 0
    for config in configs:
        for source in config:
            queries = InternetArchiveQueries(
                url_prefix=source.url_prefix,
                parser=source.query_parser,
                data_directory_path=NotImplemented,
                cdx_api_url=api_url,
            )
            pages = queries.num_pages
            print(f"{source.url_prefix}: {pages} pages")
            total_pages += pages
    print(f"total: {total_pages} pages")


@internet_archive_query_log.group()
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
def fetch_serps(
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
def num_serp_chunks(
        api_url: str,
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
                    data_directory_path=NotImplemented,
                    cdx_api_url=api_url,
                ),
                parsers=source.serp_parsers,
                chunk_size=chunk_size,
            )
            chunks = serps.num_chunks
            print(f"{source.url_prefix}: {chunks} chunks")
            total_chunks += chunks
    print(f"total: {total_chunks} chunks")


if __name__ == "__main__":
    internet_archive_query_log()
