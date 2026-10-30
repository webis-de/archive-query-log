from cyclopts import App
from cyclopts.types import PositiveInt, ResolvedPath

from archive_query_log.config import Config
from archive_query_log.export.base import ExportFormat
from archive_query_log.orm import OrganicResult

organic_results = App(
    name="web-search-result-blocks",
    alias="wsrb",
    help="Manage web search result blocks.",
)

parse = App(name="parse", alias="p", help="Parse web search result blocks.")
organic_results.command(parse)


# TODO: Add parsers for main content.


@organic_results.command
def fetch_captures(
    *,
    size: int = 10,
    dry_run: bool = False,
    config: Config = Config(),
) -> None:
    """
    Fetch captures of web search result block landing pages from web archives.

    :param size: How many captures to fetch.
    """

    from archive_query_log.captures import fetch_organic_result_captures

    OrganicResult.init(
        using=config.es.client,
        index=config.es.index_organic_results,
    )
    fetch_organic_result_captures(
        config=config,
        size=size,
        dry_run=dry_run,
    )


download = App(
    name="download",
    alias="d",
    help="Download web search result block landing pages.",
)
organic_results.command(download)


@download.command(name="warc-before-serp")
def download_warc_before_serp(
    *,
    size: int = 10,
    config: Config = Config(),
) -> None:
    """
    Download archived contents of web search result block landing page captures as WARC to file cache.

    :param size: How many web search result block landing pages to download.
    """
    from archive_query_log.downloaders.warc import (
        download_organic_result_warc_before_serp,
    )

    OrganicResult.init(
        using=config.es.client,
        index=config.es.index_organic_results,
    )
    download_organic_result_warc_before_serp(
        config=config,
        size=size,
    )


@download.command(name="warc-after-serp")
def download_warc_after_serp(
    *,
    size: int = 10,
    config: Config = Config(),
) -> None:
    """
    Download archived contents of web search result block landing page captures as WARC to file cache.

    :param size: How many web search result block landing pages to download.
    """
    from archive_query_log.downloaders.warc import (
        download_organic_result_warc_after_serp,
    )

    OrganicResult.init(
        using=config.es.client,
        index=config.es.index_organic_results,
    )
    download_organic_result_warc_after_serp(
        config=config,
        size=size,
    )


@organic_results.command
def export(
    sample_size: PositiveInt,
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config = Config(),
) -> None:
    """
    Export a sample of web search result blocks locally.
    """
    from archive_query_log.export import export_local

    export_local(
        document_type=OrganicResult,
        index=config.es.index_organic_results,
        format=format,
        sample_size=sample_size,
        output_path=output_path,
        config=config,
    )


@organic_results.command
def export_all(
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config = Config(),
) -> None:
    """
    Export all web search result blocks via Ray.
    """
    from archive_query_log.export import export_ray

    export_ray(
        document_type=OrganicResult,
        index=config.es.index_organic_results,
        format=format,
        output_path=output_path,
        config=config,
    )

upload = App(
    name="upload",
    alias="u",
    help="Upload web search result block landing pages.",
)
organic_results.command(upload)

@upload.command(name="warc")
def upload_warc(
    *,
    config: Config = Config(),
) -> None:
    """
    Upload WARCs of archived contents of organic result captures to S3 and update the index.
    """
    from archive_query_log.downloaders.warc import upload_organic_results_warc

    upload_organic_results_warc(config)