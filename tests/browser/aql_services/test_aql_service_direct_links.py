import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# Test get_serp_direct_links
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_direct_links():
    """Test extracting direct links from a SERP"""
    results = await aql.get_serp_direct_links("test-serp-id")

    # Check that function returns a dict with expected structure
    assert isinstance(results, dict)
    assert "direct_links_count" in results
    assert "direct_links" in results
    assert isinstance(results["direct_links"], list)
    # With the mock ES client, we should get 2 results
    assert results["direct_links_count"] == 2
    assert len(results["direct_links"]) == 2


@pytest.mark.asyncio
async def test_get_serp_direct_links_not_found():
    """Test direct links retrieval when SERP doesn't exist"""
    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await aql.get_serp_direct_links("nonexistent-id")
        assert result is None


@pytest.mark.asyncio
async def test_get_serp_direct_links_with_results():
    """Test direct links extraction with mock results"""
    mock_serp = {
        "_id": "test-serp-id",
        "_source": {
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Result 1",
                    "snippet": "First result snippet",
                },
                {
                    "url": "https://example.com/2",
                    "title": "Result 2",
                    "description": "Second result description",
                },
            ]
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id",
        new=AsyncMock(return_value=mock_serp),
    ):
        result = await aql.get_serp_direct_links("test-serp-id")

        assert result is not None
        assert result["serp_id"] == "test-serp-id"
        assert result["direct_links_count"] == 2
        assert len(result["direct_links"]) == 2

        # Check first result
        assert result["direct_links"][0]["position"] == 1
        assert result["direct_links"][0]["url"] == "https://example.com/1"
        assert result["direct_links"][0]["title"] == "Result 1"
        assert result["direct_links"][0]["snippet"] == "First result snippet"

        # Check second result
        assert result["direct_links"][1]["position"] == 2
        assert result["direct_links"][1]["url"] == "https://example.com/2"
        assert result["direct_links"][1]["title"] == "Result 2"
        # Falls back to description if snippet not available
        assert result["direct_links"][1]["snippet"] == "Second result description"


@pytest.mark.asyncio
async def test_get_serp_direct_links_empty_results():
    """Test direct links extraction with no results"""
    mock_serp = {
        "_id": "test-serp-id",
        "_source": {},
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id",
        new=AsyncMock(return_value=mock_serp),
    ):
        result = await aql.get_serp_direct_links("test-serp-id")

        assert result is not None
        assert result["serp_id"] == "test-serp-id"
        assert result["direct_links_count"] == 0
        assert result["direct_links"] == []
