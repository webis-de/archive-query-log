import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# Standard case: Related SERPs with the same query
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_related_serps_success():
    mock_serp = {
        "_id": "serp-123",
        "_source": {"url_query": "python tutorial", "provider": {"id": "provider-1"}},
    }
    mock_related = [
        {"_id": "serp-123", "_source": {"url_query": "python tutorial"}},
        {"_id": "serp-456", "_source": {"url_query": "python tutorial"}},
        {"_id": "serp-789", "_source": {"url_query": "python tutorial"}},
    ]

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "archive_query_log.browser.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ) as mock_search:
        result = await aql.get_related_serps("serp-123", size=10)

        mock_search.assert_awaited_once_with(
            query="python tutorial", provider_id=None, size=11
        )
        # Exclude current SERP
        assert len(result) == 2
        assert all(hit["_id"] != "serp-123" for hit in result)


# Related SERPs with the same provider
@pytest.mark.asyncio
async def test_get_related_serps_with_same_provider():
    mock_serp = {
        "_id": "serp-abc",
        "_source": {
            "url_query": "machine learning",
            "provider": {"id": "google-provider"},
        },
    }
    mock_related = [{"_id": "serp-def", "_source": {"url_query": "machine learning"}}]

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "archive_query_log.browser.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ) as mock_search:
        result = await aql.get_related_serps("serp-abc", size=5, same_provider=True)

        mock_search.assert_awaited_once_with(
            query="machine learning", provider_id="google-provider", size=6
        )
        assert len(result) == 1
        assert result[0]["_id"] == "serp-def"


# Exclude current SERP
@pytest.mark.asyncio
async def test_get_related_serps_excludes_current_serp():
    mock_serp = {
        "_id": "current-serp",
        "_source": {"url_query": "test query", "provider": {"id": "provider-x"}},
    }
    mock_related = [
        {"_id": "current-serp", "_source": {}},
        {"_id": "related-1", "_source": {}},
        {"_id": "related-2", "_source": {}},
    ]

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "archive_query_log.browser.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ):
        result = await aql.get_related_serps("current-serp", size=2)

        assert len(result) == 2
        assert not any(hit["_id"] == "current-serp" for hit in result)


# Size is respected
@pytest.mark.asyncio
async def test_get_related_serps_respects_size_limit():
    mock_serp = {
        "_id": "serp-main",
        "_source": {"url_query": "test", "provider": {"id": "p1"}},
    }
    mock_related = [{"_id": f"serp-{i}", "_source": {}} for i in range(6)]  # 6 Findings

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "archive_query_log.browser.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ):
        result = await aql.get_related_serps("serp-main", size=5)
        assert len(result) == 5


# SERP not found
@pytest.mark.asyncio
async def test_get_related_serps_serp_not_found():
    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_related_serps("nonexistent-id")
        assert result == []


# No related SERPs found
@pytest.mark.asyncio
async def test_get_related_serps_no_related_found():
    mock_serp = {
        "_id": "lonely-serp",
        "_source": {"url_query": "very unique query", "provider": {"id": "p1"}},
    }
    mock_related = [{"_id": "lonely-serp", "_source": {}}]

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "archive_query_log.browser.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ):
        result = await aql.get_related_serps("lonely-serp", size=10)
        assert result == []


# Custom size parameter
@pytest.mark.asyncio
async def test_get_related_serps_custom_size():
    mock_serp = {
        "_id": "serp-x",
        "_source": {"url_query": "test", "provider": {"id": "p1"}},
    }
    mock_related = [
        {"_id": f"serp-{i}", "_source": {}} for i in range(21)
    ]  # 21 foundings

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "archive_query_log.browser.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ) as mock_search:
        result = await aql.get_related_serps("serp-x", size=20)

        mock_search.assert_awaited_once_with(query="test", provider_id=None, size=21)
        assert len(result) == 20
