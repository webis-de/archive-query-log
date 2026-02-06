"""
Elasticsearch Async Client for FastAPI

Initializes a singleton AsyncElasticsearch client based on settings from .env,
and provides functions for accessing and shutting down the client.
"""

from elasticsearch import AsyncElasticsearch
from app.core.settings import settings

# Global Elasticsearch client (singleton)
es_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch:
    """
    Initializes the Async Elasticsearch client if it hasn't been created yet
    and returns it. Implements singleton pattern for the entire app.
    """
    global es_client
    if es_client is None:
        es_client = AsyncElasticsearch(
            hosts=[settings.es_host],
            api_key=settings.es_api_key,
            verify_certs=settings.es_verify,
            max_retries=3,  # retry failed requests up to 3 times
            retry_on_timeout=True,  # retry if a request times out
        )
    return es_client


async def close_es_client():
    """
    Closes the Elasticsearch client cleanly on app shutdown.
    """
    global es_client
    if es_client is not None:
        await es_client.close()
        es_client = None
