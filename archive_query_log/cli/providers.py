from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import (
    ResolvedDirectory,
    ResolvedExistingFile,
    ResolvedPath,
    PositiveInt,
    NonNegativeFloat,
)

from archive_query_log.cli.util import Domain
from archive_query_log.config import Config
from archive_query_log.export.base import ExportFormat
from archive_query_log.orm import Provider


providers = App(
    name="providers",
    alias="pv",
    help="Manage search providers.",
)


@providers.command()
def add(
    *,
    name: str | None,
    description: str | None,
    notes: str | None,
    exclusion_reason: Annotated[
        str | None,
        Parameter(alias="--exclusion"),
    ],
    domains: Annotated[
        list[Domain],
        Parameter(alias="--domain"),
    ],
    url_path_prefixes: Annotated[
        list[str],
        Parameter(alias="--url-path-prefix"),
    ],
    priority: NonNegativeFloat | None = None,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Add a new search provider.
    """
    from archive_query_log.providers import add_provider

    Provider.init(using=config.es.client, index=config.es.index_providers)
    add_provider(
        config=config,
        name=name,
        description=description,
        notes=notes,
        exclusion_reason=exclusion_reason,
        domains=set(domains),
        url_path_prefixes=set(url_path_prefixes),
        priority=priority,
        dry_run=dry_run,
    )


@providers.command(name="import")
def import_(
    *,
    services_path: Annotated[
        ResolvedExistingFile,
        Parameter(alias=["-s", "--services-file"]),
    ] = Path("data") / "selected-services.yaml",
    cache_path: Annotated[
        ResolvedDirectory,
        Parameter(alias=["-c", "--cache-dir"]),
    ] = Path("data") / "cache" / "provider-names",
    review: int | None = None,
    no_merge: bool = False,
    auto_merge: bool = False,
    dry_run: bool = False,
    config: Config,
) -> None:
    """
    Import search providers from a YAML search services file.
    """
    from archive_query_log.imports.yaml import import_providers

    Provider.init(using=config.es.client, index=config.es.index_providers)
    import_providers(
        config=config,
        services_path=services_path,
        cache_path=cache_path,
        review=review,
        no_merge=no_merge,
        auto_merge=auto_merge,
        dry_run=dry_run,
    )


@providers.command
def export(
    sample_size: PositiveInt,
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config,
) -> None:
    """
    Export a sample of search providers locally.
    """
    from archive_query_log.export import export_local

    export_local(
        document_type=Provider,
        index=config.es.index_providers,
        format=format,
        sample_size=sample_size,
        output_path=output_path,
        config=config,
    )


@providers.command
def export_all(
    output_path: ResolvedPath,
    *,
    format: ExportFormat = "jsonl",
    config: Config,
) -> None:
    """
    Export all search providers via Ray.
    """
    from archive_query_log.export import export_ray

    export_ray(
        document_type=Provider,
        index=config.es.index_providers,
        format=format,
        output_path=output_path,
        config=config,
    )
