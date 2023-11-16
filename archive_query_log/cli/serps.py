from click import group

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Serp


@group()
def serps():
    pass


@serps.group()
def parse():
    pass


@parse.command("url-query")
@pass_config
def parse_url_query(config: Config) -> None:
    from archive_query_log.parsers.url_query import parse_serps_url_query
    Serp.init(using=config.es.client)
    parse_serps_url_query(config)
    Serp.index().refresh(using=config.es.client)


@parse.command("url-page")
@pass_config
def parse_url_page(config: Config) -> None:
    from archive_query_log.parsers.url_page import parse_serps_url_page
    parse_serps_url_page(config)
    Serp.index().refresh(using=config.es.client)


@parse.command("url-offset")
@pass_config
def parse_url_offset(config: Config) -> None:
    from archive_query_log.parsers.url_offset import parse_serps_url_offset
    parse_serps_url_offset(config)
    Serp.index().refresh(using=config.es.client)


@serps.group()
def download():
    pass


@download.command(help="Download archived documents of captures as WARC.")
@pass_config
def warc(config: Config) -> None:
    from archive_query_log.downloaders.warc import download_serps_warc
    download_serps_warc(config)
    Serp.index().refresh(using=config.es.client)
