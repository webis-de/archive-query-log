from typing import Type, Iterable

from cyclopts import App
from dotenv import find_dotenv, load_dotenv
from tqdm.auto import tqdm

from archive_query_log.cli.archives import archives
from archive_query_log.cli.captures import captures
from archive_query_log.cli.monitoring import monitoring
from archive_query_log.cli.parsers import parsers
from archive_query_log.cli.providers import providers
from archive_query_log.cli.results import results
from archive_query_log.cli.serps import serps
from archive_query_log.cli.sources import sources
from archive_query_log.config import Config
from archive_query_log.orm import (
    BaseDocument,
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


def cli() -> None:
    if find_dotenv():
        load_dotenv(override=True)
    app()


app = App()


@app.command
def init(
    *,
    config: Config,
) -> None:
    """
    Initialize the Elasticsearch indices.
    """
    indices_list: list[tuple[Type[BaseDocument], str]] = [
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
    indices: Iterable[tuple[Type[BaseDocument], str]] = tqdm(
        indices_list,
        desc="Initialize indices",
        unit="index",
    )
    for document_type, index in indices:
        document_type.init(using=config.es.client, index=index)


app.command(archives)
app.command(providers)
app.command(parsers)
app.command(sources)
app.command(captures)
app.command(serps)
app.command(results)
app.command(monitoring)
