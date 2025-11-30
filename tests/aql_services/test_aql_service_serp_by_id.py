import pytest
from unittest.mock import AsyncMock, patch
import app.services.aql_service as aql


# ---------------------------------------------------------
# get_serp_by_id – successful retrieval
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_by_id_success():
    mock_es_response = {
        "_id": "test-id",
        "_source": {"url_query": "test"},
        "found": True,
    }

    # Patching the ES client for this specific test
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.return_value = mock_es_response
        mock_get_client.return_value = mock_es

        result = await aql.get_serp_by_id("test-id")

        assert result == mock_es_response
        mock_es.get.assert_called_once_with(index="aql_serps", id="test-id")


# ---------------------------------------------------------
# get_serp_by_id – Exception / Error case
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_by_id_exception():
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.side_effect = Exception("ES error")
        mock_get_client.return_value = mock_es

        result = await aql.get_serp_by_id("test-id")

        # Exception should be caught and None returned
        assert result is None
