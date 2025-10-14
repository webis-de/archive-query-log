from cyclopts import App
from cyclopts.types import ResolvedPath, PositiveInt

from archive_query_log.config import Config
from archive_query_log.export.base import ExportFormat
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
    dry_run: bool = False,
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
        dry_run=dry_run,
    )


@sources.command
def export(
    sample_size: PositiveInt,
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config,
) -> None:
    """
    Export a sample of crawlable sources locally.
    """
    from archive_query_log.export import export_local

    export_local(
        document_type=Source,
        index=config.es.index_sources,
        format=format,
        sample_size=sample_size,
        output_path=output_path,
        config=config,
    )


@sources.command
def export_all(
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config,
) -> None:
    """
    Export all crawlable sources via Ray.
    """
    from archive_query_log.export import export_ray

    export_ray(
        document_type=Source,
        index=config.es.index_sources,
        format=format,
        output_path=output_path,
        config=config,
    )
