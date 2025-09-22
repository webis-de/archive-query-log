from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import URL, ResolvedPath, NonNegativeFloat, PositiveInt

from archive_query_log.config import Config
from archive_query_log.export.base import ExportFormat
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
    priority: NonNegativeFloat | None = None,
    dry_run: bool = False,
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
        dry_run=dry_run,
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
    page_size: PositiveInt = DEFAULT_ARCHIVE_IT_PAGE_SIZE,
    priority: NonNegativeFloat | None = None,
    no_merge: bool = False,
    auto_merge: bool = False,
    dry_run: bool = False,
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
        dry_run=dry_run,
    )


@archives.command
def export(
    sample_size: PositiveInt,
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config,
) -> None:
    """
    Export a sample of web archives.
    """
    from archive_query_log.export import export_local

    export_local(
        document_type=Archive,
        index=config.es.index_archives,
        format=format,
        sample_size=sample_size,
        output_path=output_path,
        config=config,
    )
