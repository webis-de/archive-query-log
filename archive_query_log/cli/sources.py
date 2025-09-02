from cyclopts import App

from archive_query_log.config import Config
from archive_query_log.orm import Source


sources = App(
    name="sources",
    alias="sc",
    help="Manage data sources.",
)


@sources.command()
def build(
    *,
    skip_archives: bool,
    skip_providers: bool,
    config: Config,
) -> None:
    """
    Build data sources based on all available web archives and search providers.
    """
    from archive_query_log.sources import build_sources

    Source.init(using=config.es.client, index=config.es.index_sources)
    build_sources(
        config=config,
        skip_archives=skip_archives,
        skip_providers=skip_providers,
    )
