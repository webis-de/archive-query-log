import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


@pytest.mark.asyncio
async def test_get_provider_by_id_success():
    mock_es_response = {"_id": "google", "_source": {"name": "Google"}, "found": True}

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.return_value = mock_es_response
        mock_get_client.return_value = mock_es

        res = await aql.get_provider_by_id("google")
        assert res == mock_es_response
        assert res["_id"] == "google"
        assert res["_source"]["name"] == "Google"
        mock_es.get.assert_called_once_with(index="aql_providers", id="google")


@pytest.mark.asyncio
async def test_get_provider_by_id_not_found():
    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.side_effect = Exception("ES error")
        # Mock search to return no results (fallback from name lookup)
        mock_es.search.return_value = {"hits": {"hits": []}}
        mock_get_client.return_value = mock_es

        res = await aql.get_provider_by_id("unknown")
        assert res is None
