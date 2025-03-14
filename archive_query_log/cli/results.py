from click import group

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config


@group()
def results():
    pass


@results.group()
def download():
    pass


@download.command(help="Download archived documents of captures as WARC.")
@pass_config
def warc(config: Config) -> None:
    raise NotImplementedError("This command is not yet implemented.")
    # from archive_query_log.downloaders.warc import download_results_warc
    # download_results_warc(config)
