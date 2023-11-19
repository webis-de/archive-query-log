from pathlib import Path

from click import group, Path as PathType, argument, option

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Capture


@group()
def captures() -> None:
    pass


@captures.command()
@pass_config
def fetch(config: Config) -> None:
    from archive_query_log.captures import fetch_captures
    Capture.init(using=config.es.client)
    fetch_captures(config)


@captures.group("import")
def import_() -> None:
    pass


_CEPH_DIR = Path("/mnt/ceph/storage/")
_DEFAULT_DATA_DIR = (
    _CEPH_DIR / "data-in-progress/data-research/web-search/"
                "archive-query-log/focused/"
    if _CEPH_DIR.is_mount() and _CEPH_DIR.exists()
    else None)


@import_.command(help="Import captures from the AQL-22 dataset.")
@argument("data_dir_path",
          type=PathType(path_type=Path, exists=True, file_okay=False,
                        dir_okay=True, readable=True, writable=False,
                        resolve_path=True, allow_dash=False),
          metavar="DATA_DIR", required=True, default=_DEFAULT_DATA_DIR)
@option("--check-memento/--no-check-memento", default=True)
@option("--search-provider", type=str, envvar="SEARCH_PROVIDER")
@option("--search-provider-index", type=int,
        envvar="SEARCH_PROVIDER_INDEX")
@pass_config
def aql_22(
        config: Config,
        data_dir_path: Path,
        check_memento: bool,
        search_provider: str | None,
        search_provider_index: int | None,
) -> None:
    from archive_query_log.imports.aql22 import import_captures
    Capture.init(using=config.es.client)
    import_captures(
        config=config,
        data_dir_path=data_dir_path,
        check_memento=check_memento,
        search_provider=search_provider,
        search_provider_index=search_provider_index,
    )
