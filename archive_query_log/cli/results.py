from cyclopts import App

from archive_query_log.config import Config


results = App(
    name="results",
    alias="r",
    help="Manage search results.",
)

download = App(
    name="download",
    help="Download search results.",
)
results.command(download)


@download.command
def warc(
    *,
    config: Config,
) -> None:
    """
    Download archived documents of captures as WARC.
    """
    raise NotImplementedError("This command is not yet implemented.")
    # from archive_query_log.downloaders.warc import download_results_warc
    # download_results_warc(config)
