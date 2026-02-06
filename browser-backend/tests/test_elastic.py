import pytest
from unittest.mock import patch, AsyncMock

from app.core.elastic import get_es_client, close_es_client


@pytest.mark.asyncio
async def test_get_es_client_creates_singleton():
    # ensure clean state
    from app.core import elastic

    elastic.es_client = None

    with patch("app.core.elastic.AsyncElasticsearch") as mock_es:
        instance = mock_es.return_value
        client1 = get_es_client()
        client2 = get_es_client()

        assert client1 is instance
        assert client2 is instance
        mock_es.assert_called_once()  # Singleton: only one creation


@pytest.mark.asyncio
async def test_close_es_client_closes_and_resets():
    # Reset global client
    import app.core.elastic as elastic

    elastic.es_client = None

    with patch("app.core.elastic.AsyncElasticsearch") as mock_es:
        instance = mock_es.return_value

        client = get_es_client()
        assert isinstance(client, type(instance))  # statt "is"

        client.close = AsyncMock()

        await close_es_client()
        client.close.assert_awaited_once()
        assert elastic.es_client is None
