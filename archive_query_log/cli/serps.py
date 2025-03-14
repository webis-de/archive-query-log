from click import group

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Serp, Result


@group()
def serps():
    pass


@serps.group()
def parse():
    pass


@parse.command()
@pass_config
def url_query(config: Config) -> None:
    from archive_query_log.parsers.url_query import parse_serps_url_query
    Serp.init(using=config.es.client, index=config.es.index_serps)
    parse_serps_url_query(config)


@parse.command()
@pass_config
def url_page(config: Config) -> None:
    from archive_query_log.parsers.url_page import parse_serps_url_page
    parse_serps_url_page(config)


@parse.command()
@pass_config
def url_offset(config: Config) -> None:
    from archive_query_log.parsers.url_offset import parse_serps_url_offset
    parse_serps_url_offset(config)


@parse.command()
@pass_config
def warc_query(config: Config) -> None:
    from archive_query_log.parsers.warc_query import parse_serps_warc_query
    parse_serps_warc_query(config)


@parse.command()
@pass_config
def warc_snippets(config: Config) -> None:
    from archive_query_log.parsers.warc_snippets import \
        parse_serps_warc_snippets
    Result.init(using=config.es.client, index=config.es.index_results)
    parse_serps_warc_snippets(config)


@parse.command()
@pass_config
def warc_direct_answers(config: Config) -> None:
    from archive_query_log.parsers.warc_direct_answers import \
        parse_serps_warc_direct_answers
    parse_serps_warc_direct_answers(config)


@serps.group()
def download():
    pass


@download.command(name="warc", help="Download archived documents of captures as WARC to a file cache.")
@pass_config
def download_warc(config: Config) -> None:
    from archive_query_log.downloaders.warc import download_serps_warc
    download_serps_warc(config)


@serps.group()
def upload():
    pass


@upload.command(name="warc", help="Upload WARCs of archived documents of captures to S3 and update the index.")
@pass_config
def upload_warc(config: Config) -> None:
    from archive_query_log.downloaders.warc import upload_serps_warc
    upload_serps_warc(config)
