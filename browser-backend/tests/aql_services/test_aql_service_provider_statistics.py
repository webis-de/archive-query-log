"""Tests for provider statistics functions"""

import pytest
from unittest.mock import AsyncMock, patch
from archive_query_log.browser.services import aql_service


@pytest.mark.asyncio
async def test_get_provider_statistics_success():
    """Test retrieving statistics for a valid provider"""

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            side_effect=[
                # First call - basic aggregations
                {
                    "hits": {"total": {"value": 500, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "unique_queries": {
                            "buckets": [{"key": "query", "doc_count": 1}] * 250
                        },
                        "top_archives": {
                            "buckets": [
                                {
                                    "key": "https://web.archive.org/web",
                                    "doc_count": 300,
                                },
                                {
                                    "key": "https://archive.example.org",
                                    "doc_count": 200,
                                },
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
                                    "doc_count": 100,
                                },
                                {
                                    "key_as_string": "2023-02-01T00:00:00Z",
                                    "doc_count": 150,
                                },
                            ]
                        },
                    }
                },
            ]
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_provider_statistics("google", interval="month")

        assert result is not None
        assert result["provider_id"] == "google"
        assert result["serp_count"] == 500
        assert result["unique_queries_count"] == 250
        assert len(result["top_archives"]) == 2
        assert result["top_archives"][0]["archive"] == "https://web.archive.org/web"
        assert result["top_archives"][0]["count"] == 300
        # Date histogram should be available if query succeeds
        assert "date_histogram" in result


@pytest.mark.asyncio
async def test_get_provider_statistics_not_found():
    """Test retrieving statistics for non-existent provider"""

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_provider_statistics("nonexistent")

        assert result is None


@pytest.mark.asyncio
async def test_get_provider_statistics_with_time_filter():
    """Test provider statistics with last_n_months filter"""

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {"total": {"value": 100, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "unique_queries": {
                        "buckets": [{"key": "query", "doc_count": 1}] * 50
                    },
                    "top_archives": {"buckets": []},
                    "date_range": {
                        "min_as_string": "2024-10-01T00:00:00Z",
                        "max_as_string": "2025-01-01T00:00:00Z",
                    },
                    "by_time": {"buckets": []},
                },
            }
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_provider_statistics("google", last_n_months=12)

        assert result is not None
        assert result["serp_count"] == 100
        assert result["unique_queries_count"] == 50


@pytest.mark.asyncio
async def test_get_provider_statistics_interval_normalization():
    """Test that invalid intervals are normalized to 'month'"""

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {"total": {"value": 100, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "unique_queries": {
                        "buckets": [{"key": "query", "doc_count": 1}] * 250
                    },
                    "top_archives": {"buckets": []},
                },
            }
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_provider_statistics("google", interval="INVALID")

        assert result is not None
        assert result["serp_count"] == 100
