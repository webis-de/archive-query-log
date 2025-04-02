from typing import Any, Type, Iterable

from click import group, Context, Parameter, echo, option, pass_context
from dotenv import find_dotenv, load_dotenv
from elasticsearch_dsl import Document
from tqdm.auto import tqdm

from archive_query_log import __version__ as app_version
from archive_query_log.cli.archives import archives
from archive_query_log.cli.captures import captures
from archive_query_log.cli.monitoring import monitoring
from archive_query_log.cli.parsers import parsers
from archive_query_log.cli.providers import providers
from archive_query_log.cli.results import results
from archive_query_log.cli.serps import serps
from archive_query_log.cli.sources import sources
from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import (
    Archive,
    Provider,
    Source,
    Capture,
    Serp,
    Result,
    UrlQueryParser,
    UrlPageParser,
    UrlOffsetParser,
    WarcQueryParser,
    WarcSnippetsParser,
    WarcMainContentParser,
    WarcDirectAnswersParser,
)


def echo_version(
    context: Context,
    _parameter: Parameter,
    value: Any,
) -> None:
    if not value or context.resilient_parsing:
        return
    echo(app_version)
    context.exit()


@group()
@option(
    "-V",
    "--version",
    is_flag=True,
    callback=echo_version,
    expose_value=False,
    is_eager=True,
)
@pass_context
def cli(context: Context) -> None:
    if find_dotenv():
        load_dotenv(override=True)
    config: Config = Config()
    context.obj = config


@cli.command()
@pass_config
def init(config: Config) -> None:
    indices_list: list[tuple[Type[Document], str]] = [
        (Archive, config.es.index_archives),
        (Provider, config.es.index_providers),
        (Source, config.es.index_sources),
        (Capture, config.es.index_captures),
        (Serp, config.es.index_serps),
        (Result, config.es.index_results),
        (UrlQueryParser, config.es.index_url_query_parsers),
        (UrlPageParser, config.es.index_url_page_parsers),
        (UrlOffsetParser, config.es.index_url_offset_parsers),
        (WarcQueryParser, config.es.index_warc_query_parsers),
        (WarcSnippetsParser, config.es.index_warc_snippets_parsers),
        (WarcMainContentParser, config.es.index_warc_main_content_parsers),
        (WarcDirectAnswersParser, config.es.index_warc_direct_answers_parsers),
    ]
    # noinspection PyTypeChecker
    indices: Iterable[tuple[Type[Document], str]] = tqdm(
        indices_list,
        desc="Initialize indices",
        unit="index",
    )
    for document_type, index in indices:
        document_type.init(using=config.es.client, index=index)


cli.add_command(archives)
cli.add_command(providers)
cli.add_command(parsers)
cli.add_command(sources)
cli.add_command(captures)
cli.add_command(serps)
cli.add_command(results)
cli.add_command(monitoring)
