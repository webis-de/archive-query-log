from pathlib import Path
from typing import Any, Type, Iterable

from click import group, Context, Parameter, echo, option, pass_context, \
    Path as PathType, UsageError
from elasticsearch_dsl import Document
from mergedeep import merge, Strategy
from tqdm.auto import tqdm
from yaml import safe_load

from archive_query_log import __version__ as app_version
from archive_query_log.cli.archives import archives
from archive_query_log.cli.captures import captures
from archive_query_log.cli.monitoring import monitoring
from archive_query_log.cli.parsers import parsers
from archive_query_log.cli.providers import providers
from archive_query_log.cli.serps import serps
from archive_query_log.cli.sources import sources
from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import (
    Archive, Provider, Source, Capture, Serp, Result, UrlQueryParser,
    UrlPageParser, UrlOffsetParser)


def echo_version(
        context: Context,
        _parameter: Parameter,
        value: Any,
) -> None:
    if not value or context.resilient_parsing:
        return
    echo(app_version)
    context.exit()


_DEFAULT_CONFIG_PATH = Path("config.yml")
_DEFAULT_CONFIG_OVERRIDE_PATH = Path("config.override.yml")
_DEFAULT_CONFIG_PATHS = []
if _DEFAULT_CONFIG_PATH.exists():
    _DEFAULT_CONFIG_PATHS.append(_DEFAULT_CONFIG_PATH)
if _DEFAULT_CONFIG_OVERRIDE_PATH.exists():
    _DEFAULT_CONFIG_PATHS.append(_DEFAULT_CONFIG_OVERRIDE_PATH)


@group()
@option("-V", "--version", is_flag=True, callback=echo_version,
        expose_value=False, is_eager=True)
@option("-f", "--config-file", "config_paths",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, writable=False,
                      resolve_path=True, allow_dash=False),
        default=_DEFAULT_CONFIG_PATHS, multiple=True, required=True)
@pass_context
def cli(context: Context, config_paths: list[Path]) -> None:
    if len(config_paths) == 0:
        raise UsageError("No config file specified.")
    config_dict: dict = {}
    for config_path in config_paths:
        with config_path.open("rb") as config_file:
            next_config_dict = safe_load(config_file)
            merge(config_dict, next_config_dict, strategy=Strategy.REPLACE)
    config: Config = Config.from_dict(config_dict)
    context.obj = config


@cli.command()
@pass_config
def init(config: Config) -> None:
    indices_list: list[Type[Document]] = [
        Archive,
        Provider,
        Source,
        Capture,
        Serp,
        Result,
        UrlQueryParser,
        UrlPageParser,
        UrlOffsetParser,
    ]
    # noinspection PyTypeChecker
    indices: Iterable[Type[Document]] = tqdm(
        indices_list,
        desc="Initialize Elasticsearch indices.",
        unit="index",
    )
    for index in indices:
        index.init(using=config.es.client)


cli.add_command(archives)
cli.add_command(providers)
cli.add_command(parsers)
cli.add_command(sources)
cli.add_command(captures)
cli.add_command(serps)
cli.add_command(monitoring)
