import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# get_serp_memento_url – standard case
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_memento_url_success():
    mock_serp = {
        "_id": "test-uuid-5678",
        "_source": {
            "archive": {"memento_api_url": "https://web.archive.org/web"},
            "capture": {
                "url": "https://google.com/search?q=python",
                "timestamp": "2021-06-15T14:30:45+00:00",
            },
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_memento_url("test-uuid-5678")

        assert result["serp_id"] == "test-uuid-5678"
        assert (
            result["memento_url"]
            == "https://web.archive.org/web/20210615143045/https://google.com/search?q=python"
        )


# ---------------------------------------------------------
# get_serp_memento_url – different timestamp
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_memento_url_different_timestamp():
    mock_serp = {
        "_id": "test-id-999",
        "_source": {
            "archive": {"memento_api_url": "https://archive.example.org"},
            "capture": {
                "url": "https://bing.com/search?q=test",
                "timestamp": "2020-01-01T00:00:00+00:00",
            },
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_memento_url("test-id-999")

        assert result["serp_id"] == "test-id-999"
        assert (
            result["memento_url"]
            == "https://archive.example.org/20200101000000/https://bing.com/search?q=test"
        )


# ---------------------------------------------------------
# get_serp_memento_url – SERP not found
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_memento_url_serp_not_found():
    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_memento_url("nonexistent-id")
        assert result is None
