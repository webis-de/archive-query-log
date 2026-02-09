import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# get_serp_original_url – standard case
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_original_url_success():
    mock_serp = {
        "_id": "test-uuid-1234",
        "_source": {
            "capture": {"url": "https://google.com/search?q=test&utm_source=tracking"}
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_original_url("test-uuid-1234")

        assert result["serp_id"] == "test-uuid-1234"
        assert (
            result["original_url"]
            == "https://google.com/search?q=test&utm_source=tracking"
        )


# ---------------------------------------------------------
# get_serp_original_url – Remove tracking parameters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_original_url_with_tracking_removal():
    mock_serp = {
        "_id": "test-id",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=test&utm_source=email&fbclid=123"
            }
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_original_url("test-id", remove_tracking=True)

        assert result["serp_id"] == "test-id"
        assert "utm_source" not in result["url_without_tracking"]
        assert "fbclid" not in result["url_without_tracking"]
        assert "q=test" in result["url_without_tracking"]


# ---------------------------------------------------------
# get_serp_original_url – SERP not found
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_original_url_serp_not_found():
    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_original_url("nonexistent-id")
        assert result is None
