from cyclopts import App

from archive_query_log.config import Config
from archive_query_log.orm import Serp, WebSearchResultBlock, SpecialContentsResultBlock

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
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Parse the search query from a SERP's URL.

    :param size: How many captures to parse.
    """
    from archive_query_log.parsers.url_query import parse_serps_url_query

    Serp.init(
        using=config.es.client,
        index=config.es.index_serps,
    )
    parse_serps_url_query(
        config=config,
        size=size,
        dry_run=dry_run,
    )


@parse.command
def url_page(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Parse the SERP's page index from a SERP's URL.

    :param size: How many SERPs to parse.
    """
    from archive_query_log.parsers.url_page import parse_serps_url_page

    parse_serps_url_page(
        config=config,
        size=size,
        dry_run=dry_run,
    )


@parse.command
def url_offset(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Parse the SERP's pagination offset from a SERP's URL.

    :param size: How many SERPs to parse.
    """
    from archive_query_log.parsers.url_offset import parse_serps_url_offset

    parse_serps_url_offset(
        config=config,
        size=size,
        dry_run=dry_run,
    )


@parse.command
def warc_query(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Parse the search query from a SERP's WARC file (e.g., HTML contents).

    :param size: How many SERPs to parse.
    """
    from archive_query_log.parsers.warc_query import parse_serps_warc_query

    parse_serps_warc_query(
        config=config,
        size=size,
        dry_run=dry_run,
    )


@parse.command
def warc_web_search_result_blocks(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Parse the web search result blocks from a SERP's WARC file (e.g., HTML contents).

    :param size: How many SERPs to parse.
    """
    from archive_query_log.parsers.warc_web_search_result_blocks import (
        parse_serps_warc_web_search_result_blocks,
    )

    WebSearchResultBlock.init(
        using=config.es.client,
        index=config.es.index_web_search_result_blocks,
    )
    parse_serps_warc_web_search_result_blocks(
        config=config,
        size=size,
        dry_run=dry_run,
    )


@parse.command
def warc_special_contents_result_blocks(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Parse the special contents result blocks from a SERP's WARC file (e.g., HTML contents).

    :param size: How many SERPs to parse.
    """
    from archive_query_log.parsers.warc_special_contents_result_blocks import (
        parse_serps_warc_special_contents_result_blocks,
    )

    SpecialContentsResultBlock.init(
        using=config.es.client,
        index=config.es.index_special_contents_result_blocks,
    )
    parse_serps_warc_special_contents_result_blocks(
        config=config,
        size=size,
        dry_run=dry_run,
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
    size: int = 10,
    config: Config,
) -> None:
    """
    Download archived contents of SERP captures as WARC to a file cache.

    :param size: How many SERPs to download.
    """
    from archive_query_log.downloaders.warc import download_serps_warc

    download_serps_warc(
        config=config,
        size=size,
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
