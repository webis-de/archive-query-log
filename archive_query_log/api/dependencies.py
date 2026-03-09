from typing import Annotated, TypeAlias, Iterator, AsyncIterator

from fastapi import Depends
from elasticsearch import Elasticsearch, AsyncElasticsearch


from archive_query_log.config import Config


def _load_config() -> Iterator[Config]:
    yield Config()


ConfigDependency: TypeAlias = Annotated[
    Config,
    Depends(_load_config),
]


def _load_elasticsearch(config: ConfigDependency) -> Iterator[Elasticsearch]:
    es = config.es.client
    try:
        yield es
    finally:
        es.close()


ElasticsearchDependency: TypeAlias = Annotated[
    Elasticsearch,
    Depends(_load_elasticsearch),
]


async def _load_async_elasticsearch(
    config: ConfigDependency,
) -> AsyncIterator[AsyncElasticsearch]:
    es = config.es.async_client
    try:
        yield es
    finally:
        await es.close()


AsyncElasticsearchDependency: TypeAlias = Annotated[
    AsyncElasticsearch,
    Depends(_load_async_elasticsearch),
]
