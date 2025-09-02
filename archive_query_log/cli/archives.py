from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import URL
from cyclopts.validators import Number

from archive_query_log.config import Config
from archive_query_log.imports.archive_it import (
    DEFAULT_ARCHIVE_IT_PAGE_SIZE,
    DEFAULT_ARCHIVE_IT_WAYBACK_URL,
    DEFAULT_ARCHIVE_IT_API_URL,
)
from archive_query_log.orm import Archive


archives = App(
    name="archives",
    alias="a",
    help="Manage web archives.",
)


@archives.command
def add(
    *,
    name: Annotated[
        str,
        Parameter(alias="-n"),
    ],
    description: Annotated[
        str,
        Parameter(alias="-d"),
    ]
    | None = None,
    cdx_api_url: Annotated[
        URL,
        Parameter(alias="-c"),
    ],
    memento_api_url: Annotated[
        URL,
        Parameter(alias="-m"),
    ],
    priority: Annotated[float, Number(gte=0)] | None = None,
    config: Config,
) -> None:
    """
    Add a new web archive for crawling.
    """
    from archive_query_log.archives import add_archive

    print("Adding archive:", name)

    Archive.init(using=config.es.client, index=config.es.index_archives)
    add_archive(
        config=config,
        name=name,
        description=description,
        cdx_api_url=cdx_api_url,
        memento_api_url=memento_api_url,
        priority=priority,
    )


import_ = App(
    name="import",
    help="Import web archives.",
)
archives.command(import_)


@import_.command
def archive_it(
    *,
    api_url: URL = DEFAULT_ARCHIVE_IT_API_URL,
    wayback_url: URL = DEFAULT_ARCHIVE_IT_WAYBACK_URL,
    page_size: Annotated[int, Number(gte=1)] = DEFAULT_ARCHIVE_IT_PAGE_SIZE,
    priority: Annotated[float, Number(gte=0)] | None = None,
    no_merge: bool = False,
    auto_merge: bool = False,
    config: Config,
) -> None:
    """
    Import all web archives from the Archive-It service, via their API.
    """
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
