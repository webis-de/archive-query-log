from cyclopts import App

from archive_query_log.config import Config
from archive_query_log.orm import WebSearchResultBlock

web_search_result_blocks = App(
    name="web-search-result-blocks",
    alias="wsrb",
    help="Manage web search result blocks.",
)

parse = App(name="parse", alias="p", help="Parse web search result blocks.")
web_search_result_blocks.command(parse)


# TODO: Add parsers for main content.


@web_search_result_blocks.command
def fetch_captures(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Fetch captures of web search result block landing pages from web archives.

    :param size: How many captures to fetch.
    """

    from archive_query_log.captures import fetch_web_search_result_block_captures

    WebSearchResultBlock.init(
        using=config.es.client,
        index=config.es.index_web_search_result_blocks,
    )
    fetch_web_search_result_block_captures(
        config=config,
        size=size,
        dry_run=dry_run,
    )


download = App(
    name="download",
    alias="d",
    help="Download web search result block landing pages.",
)
web_search_result_blocks.command(download)


@download.command(name="warc-before-serp")
def download_warc_before_serp(
    *,
    size: int = 10,
    config: Config,
) -> None:
    """
    Download archived contents of web search result block landing page captures as WARC to S3.

    :param size: How many web search result block landing pages to download.
    """
    from archive_query_log.downloaders.warc import (
        download_web_search_result_block_warc_before_serp,
    )

    download_web_search_result_block_warc_before_serp(
        config=config,
        size=size,
    )


@download.command(name="warc-after-serp")
def download_warc_after_serp(
    *,
    size: int = 10,
    config: Config,
) -> None:
    """
    Download archived contents of web search result block landing page captures as WARC to S3.

    :param size: How many web search result block landing pages to download.
    """
    from archive_query_log.downloaders.warc import (
        download_web_search_result_block_warc_after_serp,
    )

    download_web_search_result_block_warc_after_serp(
        config=config,
        size=size,
    )
