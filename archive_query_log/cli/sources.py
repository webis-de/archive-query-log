from click import group, option

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Source


@group()
def sources():
    pass


@sources.command()
@option("--skip-archives", is_flag=True)
@option("--skip-providers", is_flag=True)
@pass_config
def build(
        config: Config,
        skip_archives: bool,
        skip_providers: bool,
) -> None:
    from archive_query_log.sources import build_sources
    Source.init(using=config.es.client, index=config.es.index_sources)
    build_sources(
        config=config,
        skip_archives=skip_archives,
        skip_providers=skip_providers,
    )
