from pathlib import Path

from click import group, option, Path as PathType, FloatRange

from archive_query_log.cli.util import validate_split_domains, pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Provider


@group()
def providers() -> None:
    pass


@providers.command()
@option("--name", type=str)
@option("--description", type=str)
@option("--notes", type=str)
@option("--exclusion-reason", "--exclusion", type=str)
@option("--domains", "--domain", type=str, multiple=True,
        required=True, callback=validate_split_domains)
@option("--url-path-prefixes", "--url-path-prefix", type=str,
        multiple=True, required=True, metavar="PREFIXES")
@option("--priority", type=FloatRange(min=0, min_open=False))
@pass_config
def add(
        config: Config,
        name: str | None,
        description: str | None,
        notes: str | None,
        exclusion_reason: str | None,
        domains: list[str],
        url_path_prefixes: list[str],
        priority: float | None,
) -> None:
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
    )


@providers.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@option("-c", "--cache-dir", "cache_path",
        type=PathType(path_type=Path, exists=False, file_okay=False,
                      dir_okay=True, readable=True, writable=True,
                      resolve_path=True, allow_dash=False),
        default=Path("data") / "cache" / "provider-names")
@option("--review", type=int)
@option("--no-merge", is_flag=True, default=False, type=bool)
@option("--auto-merge", is_flag=True, default=False, type=bool)
@pass_config
def import_(
        config: Config,
        services_path: Path,
        cache_path: Path,
        review: int | None,
        no_merge: bool,
        auto_merge: bool,
) -> None:
    from archive_query_log.imports.yaml import import_providers
    Provider.init(using=config.es.client, index=config.es.index_providers)
    import_providers(
        config=config,
        services_path=services_path,
        cache_path=cache_path,
        review=review,
        no_merge=no_merge,
        auto_merge=auto_merge,
    )
