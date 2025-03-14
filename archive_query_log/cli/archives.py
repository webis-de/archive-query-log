from click import group, option, IntRange, FloatRange

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.imports.archive_it import \
    DEFAULT_ARCHIVE_IT_PAGE_SIZE, DEFAULT_ARCHIVE_IT_WAYBACK_URL, \
    DEFAULT_ARCHIVE_IT_API_URL
from archive_query_log.orm import Archive


@group()
def archives() -> None:
    pass


@archives.command()
@option("-n", "--name", type=str, required=True,
        prompt="Name")
@option("-d", "--description", type=str)
@option("-c", "--cdx-api-url", type=str, required=True,
        prompt="CDX API URL", metavar="URL")
@option("-m", "--memento-api-url", type=str, required=True,
        prompt="Memento API URL", metavar="URL")
@option("--priority", type=FloatRange(min=0, min_open=False))
@pass_config
def add(
        config: Config,
        name: str,
        description: str | None,
        cdx_api_url: str,
        memento_api_url: str,
        priority: float | None,
) -> None:
    from archive_query_log.archives import add_archive
    Archive.init(using=config.es.client, index=config.es.index_archives)
    add_archive(
        config=config,
        name=name,
        description=description,
        cdx_api_url=cdx_api_url,
        memento_api_url=memento_api_url,
        priority=priority,
    )


@archives.group("import")
def import_() -> None:
    pass


@import_.command()
@option("--api-url", type=str, required=True,
        default=DEFAULT_ARCHIVE_IT_API_URL, metavar="URL")
@option("--wayback-url", type=str, required=True,
        default=DEFAULT_ARCHIVE_IT_WAYBACK_URL, metavar="URL")
@option("--page-size", type=IntRange(min=1), required=True,
        default=DEFAULT_ARCHIVE_IT_PAGE_SIZE)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--no-merge", is_flag=True, default=False, type=bool)
@option("--auto-merge", is_flag=True, default=False, type=bool)
@pass_config
def archive_it(
        config: Config,
        api_url: str,
        wayback_url: str,
        page_size: int,
        priority: float | None,
        no_merge: bool,
        auto_merge: bool,
) -> None:
    from archive_query_log.imports.archive_it import import_archives
    Archive.init(using=config.es.client, index=config.es.index_archives)
    import_archives(
        config=config,
        api_url=api_url,
        wayback_url=wayback_url,
        page_size=page_size,
        no_merge=no_merge,
        auto_merge=auto_merge,
        priority=priority,
    )
