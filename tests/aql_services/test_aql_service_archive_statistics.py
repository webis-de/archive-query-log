"""Tests for archive statistics functions"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services import aql_service


@pytest.mark.asyncio
async def test_get_archive_statistics_success():
    """Test retrieving statistics for a valid archive"""

    archive_id = "https://web.archive.org/web"

    with patch("app.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            side_effect=[
                # First call - basic aggregations
                {
                    "hits": {"total": {"value": 1000, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "unique_queries": {
                            "buckets": [{"key": "query", "doc_count": 1}] * 500
                        },
                        "top_providers": {
                            "buckets": [
                                {"key": "Google", "doc_count": 600},
                                {"key": "Bing", "doc_count": 400},
                            ]
                        },
                    },
                },
                # Second call - date histogram (might fail)
                {
                    "aggregations": {
                        "by_time": {
                            "buckets": [
                                {
                                    "key_as_string": "2023-01-01T00:00:00Z",
                                    "doc_count": 200,
                                },
                                {
                                    "key_as_string": "2023-02-01T00:00:00Z",
                                    "doc_count": 300,
                                },
                            ]
                        },
                    }
                },
            ]
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_archive_statistics(archive_id, interval="month")

        assert result is not None
        assert result["archive_id"] == archive_id
        assert result["serp_count"] == 1000
        assert result["unique_queries_count"] == 500
        assert len(result["top_providers"]) == 2
        assert result["top_providers"][0]["provider"] == "Google"
        assert result["top_providers"][0]["count"] == 600
        # Date histogram should be available if query succeeds
        assert "date_histogram" in result


@pytest.mark.asyncio
async def test_get_archive_statistics_not_found():
    """Test retrieving statistics for non-existent archive"""

    with patch("app.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_archive_statistics(
            "https://nonexistent.archive/web"
        )

        assert result is None


@pytest.mark.asyncio
async def test_get_archive_statistics_with_time_filter():
    """Test archive statistics with last_n_months filter"""

    with patch("app.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {"total": {"value": 200, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "unique_queries": {
                        "buckets": [{"key": "query", "doc_count": 1}] * 100
                    },
                    "top_providers": {"buckets": []},
                    "date_range": {
                        "min_as_string": "2024-10-01T00:00:00Z",
                        "max_as_string": "2025-01-01T00:00:00Z",
                    },
                    "by_time": {"buckets": []},
                },
            }
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_archive_statistics(
            "https://web.archive.org/web", last_n_months=12
        )

        assert result is not None
        assert result["serp_count"] == 200
        assert result["unique_queries_count"] == 100


@pytest.mark.asyncio
async def test_get_archive_statistics_different_intervals():
    """Test archive statistics with different interval values"""

    with patch("app.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {"total": {"value": 100, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "unique_queries": {"value": 50},
                    "top_providers": {"buckets": []},
                },
            }
        )
        mock_es_client.return_value = mock_client

        for interval in ["day", "week", "month"]:
            result = await aql_service.get_archive_statistics(
                "https://web.archive.org/web", interval=interval
            )
            assert result is not None
            assert result["serp_count"] == 100


@pytest.mark.asyncio
async def test_get_archive_statistics_empty_aggregations():
    """Test archive statistics when aggregations return empty buckets"""

    with patch("app.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {"total": {"value": 50, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "unique_queries": {
                        "buckets": [{"key": "query", "doc_count": 1}] * 25
                    },
                    "top_providers": {"buckets": []},
                },
            }
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_archive_statistics("https://web.archive.org/web")

        assert result is not None
        assert result["serp_count"] == 50
        assert result["unique_queries_count"] == 25
        assert result["top_providers"] == []
        assert result["date_histogram"] is None
