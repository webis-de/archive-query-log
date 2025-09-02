from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import ResolvedExistingDirectory

from archive_query_log.config import Config
from archive_query_log.orm import Capture


captures = App(
    name="captures",
    alias="c",
    help="Manage web captures.",
)


@captures.command
def fetch(
    *,
    prefetch_limit: int | None = None,
    config: Config,
) -> None:
    """
    Fetch captures from web archives.

    :param prefetch_limit: Fetch captures for only a limited number of sources, and prefetch that batch to fetch from.
    """

    from archive_query_log.captures import fetch_captures

    Capture.init(
        using=config.es.client,
        index=config.es.index_captures,
    )
    fetch_captures(
        config=config,
        prefetch_limit=prefetch_limit,
    )


import_ = App(
    name="import",
    help="Import previously crawled captures.",
)
captures.command(import_)


@import_.command
def aql_22(
    data_dir_path: ResolvedExistingDirectory = Path(
        "/mnt/ceph/storage/data-in-progress/data-research/web-search/archive-query-log/focused/"
    ),
    *,
    check_memento: bool,
    search_provider: Annotated[str | None, Parameter(env_var="SEARCH_PROVIDER")] | None,
    search_provider_index: Annotated[
        int | None, Parameter(env_var="SEARCH_PROVIDER_INDEX")
    ]
    | None,
    config: Config,
) -> None:
    """
    Import crawled captures from the AQL-22 dataset.
    """

    from archive_query_log.imports.aql22 import import_captures

    Capture.init(using=config.es.client, index=config.es.index_captures)
    import_captures(
        config=config,
        data_dir_path=data_dir_path,
        check_memento=check_memento,
        search_provider=search_provider,
        search_provider_index=search_provider_index,
    )
