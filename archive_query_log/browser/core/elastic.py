"""
Elasticsearch Async Client for FastAPI

Initializes a singleton AsyncElasticsearch client based on settings from .env,
and provides functions for accessing and shutting down the client.
"""

from elasticsearch import AsyncElasticsearch
from dotenv import load_dotenv, find_dotenv

from archive_query_log.config import Config

# Global Elasticsearch client (singleton)
es_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch:
    """
    Initializes the Async Elasticsearch client if it hasn't been created yet
    and returns it. Implements singleton pattern for the entire app.
    """
    global es_client
    if es_client is None:
        if find_dotenv():
            load_dotenv(override=True)
        es_client = Config().es.async_client
    return es_client


async def close_es_client() -> None:
    """
    Closes the Elasticsearch client cleanly on app shutdown.
    """
    global es_client
    if es_client is not None:
        await es_client.close()
        es_client = None
