from pathlib import Path
from typing import Any

from click import group, Context, Parameter, echo, option, pass_context, \
    Path as PathType
from mergedeep import merge, Strategy
from yaml import safe_load

from archive_query_log import __version__, PROJECT_DIRECTORY_PATH
from archive_query_log.new.cli.archives import archives
from archive_query_log.new.cli.captures import captures
from archive_query_log.new.cli.monitoring import monitoring
from archive_query_log.new.cli.providers import providers
from archive_query_log.new.cli.sources import sources
from archive_query_log.new.cli.util import pass_config
from archive_query_log.new.config import Config
from archive_query_log.new.orm import Archive, Provider, Source, Capture


def print_version(
        context: Context,
        _parameter: Parameter,
        value: Any,
) -> None:
    if not value or context.resilient_parsing:
        return
    echo(__version__)
    context.exit()


_DEFAULT_CONFIG_PATHS = [
    PROJECT_DIRECTORY_PATH / "config.yml",
    PROJECT_DIRECTORY_PATH / "config.override.yml",
]


@group()
@option("-V", "--version", is_flag=True, callback=print_version,
        expose_value=False, is_eager=True)
@option("-f", "--config-file", "config_paths",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, writable=False,
                      resolve_path=True, allow_dash=False),
        default=_DEFAULT_CONFIG_PATHS, multiple=True, required=True)
@pass_context
def cli(context: Context, config_paths: list[Path]) -> None:
    config_dict = {}
    for config_path in config_paths:
        with config_path.open("rb") as config_file:
            next_config_dict = safe_load(config_file)
            merge(config_dict, next_config_dict, strategy=Strategy.REPLACE)
    config: Config = Config.from_dict(config_dict)
    context.obj = config


@cli.command()
@pass_config
def init(config: Config) -> None:
    echo("Initialize Elasticsearch indices.")
    Archive.init(using=config.es.client)
    Provider.init(using=config.es.client)
    Source.init(using=config.es.client)
    Capture.init(using=config.es.client)


cli.add_command(archives)
cli.add_command(providers)
cli.add_command(sources)
cli.add_command(captures)
cli.add_command(monitoring)
