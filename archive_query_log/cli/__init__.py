from typing import Type, Iterable

from cyclopts import App
from dotenv import find_dotenv, load_dotenv
from tqdm.auto import tqdm

from archive_query_log.cli.archives import archives
from archive_query_log.cli.captures import captures
from archive_query_log.cli.api import api
from archive_query_log.cli.providers import providers
from archive_query_log.cli.serps import serps
from archive_query_log.cli.sources import sources
from archive_query_log.cli.organic_results import organic_results
from archive_query_log.config import Config
from archive_query_log.orm import (
    BaseDocument,
    Archive,
    Provider,
    Source,
    Capture,
    Serp,
    OrganicResult,
    Feature,
)


def cli() -> None:
    if find_dotenv():
        load_dotenv(override=True)
    app()


app = App()


@app.command
def init(
    *,
    config: Config = Config(),
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
        (OrganicResult, config.es.index_organic_results),
        (Feature, config.es.index_features),
    ]
    indices: Iterable[tuple[Type[BaseDocument], str]] = tqdm(
        indices_list,
        desc="Initialize indices",
        unit="index",
    )
    for document_type, index in indices:
        document_type.init(using=config.es.client, index=index)


app.command(archives)
app.command(providers)
app.command(sources)
app.command(captures)
app.command(serps)
app.command(api)
app.command(organic_results)
