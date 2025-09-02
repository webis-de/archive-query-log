from cyclopts import App

from archive_query_log.config import Config
from archive_query_log.orm import Serp, Result

serps = App(
    name="serps",
    alias="s",
    help="Manage search engine results pages (SERPs).",
)

parse = App(name="parse", alias="p", help="Parse SERPs.")
serps.command(parse)


@parse.command
def url_query(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Parse the search query from a SERP's URL.

    :param prefetch_limit: Parse SERP URLs for only a limited number of captures, and prefetch that batch to parse.
    """
    from archive_query_log.parsers.url_query import parse_serps_url_query

    Serp.init(
        using=config.es.client,
        index=config.es.index_serps,
    )
    parse_serps_url_query(
        config=config,
        prefetch_limit=prefetch_limit,
    )


@parse.command
def url_page(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Parse the SERP's page index from a SERP's URL.

    :param prefetch_limit: Parse only a limited number of SERPs, and prefetch that batch to parse.
    """
    from archive_query_log.parsers.url_page import parse_serps_url_page

    parse_serps_url_page(
        config=config,
        prefetch_limit=prefetch_limit,
    )


@parse.command
def url_offset(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Parse the SERP's pagination offset from a SERP's URL.

    :param prefetch_limit: Parse SERP URLs for only a limited number of captures, and prefetch that batch to parse.
    """
    from archive_query_log.parsers.url_offset import parse_serps_url_offset

    parse_serps_url_offset(
        config=config,
        prefetch_limit=prefetch_limit,
    )


@parse.command
def warc_query(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Parse the search query from a SERP's WARC file (e.g., HTML contents).

    :param prefetch_limit: Parse only a limited number of SERPs, and prefetch that batch to parse.
    """
    from archive_query_log.parsers.warc_query import parse_serps_warc_query

    parse_serps_warc_query(
        config=config,
        prefetch_limit=prefetch_limit,
    )


@parse.command
def warc_snippets(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Parse the web search result blocks from a SERP's WARC file (e.g., HTML contents).

    :param prefetch_limit: Parse only a limited number of SERPs, and prefetch that batch to parse.
    """
    from archive_query_log.parsers.warc_snippets import parse_serps_warc_snippets

    Result.init(
        using=config.es.client,
        index=config.es.index_results,
    )
    parse_serps_warc_snippets(
        config=config,
        prefetch_limit=prefetch_limit,
    )


@parse.command
def warc_direct_answers(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Parse the special contents result blocks from a SERP's WARC file (e.g., HTML contents).

    :param prefetch_limit: Parse only a limited number of SERPs, and prefetch that batch to parse.
    """
    from archive_query_log.parsers.warc_direct_answers import (
        parse_serps_warc_direct_answers,
    )

    parse_serps_warc_direct_answers(
        config=config,
        prefetch_limit=prefetch_limit,
    )


download = App(
    name="download",
    alias="d",
    help="Download SERP contents.",
)
serps.command(download)


@download.command(name="warc")
def download_warc(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Download archived contents of SERP captures as WARC to a file cache.

    :param prefetch_limit: Download only a limited number of SERPs, and prefetch that batch to parse.
    """
    from archive_query_log.downloaders.warc import download_serps_warc

    download_serps_warc(
        config=config,
        prefetch_limit=prefetch_limit,
    )


upload = App(
    name="upload",
    alias="u",
    help="Upload SERP contents.",
)
serps.command(upload)


@upload.command(name="warc")
def upload_warc(
    *,
    config: Config,
) -> None:
    """
    Upload WARCs of archived contents of SERP captures to S3 and update the index.
    """
    from archive_query_log.downloaders.warc import upload_serps_warc

    upload_serps_warc(config)
