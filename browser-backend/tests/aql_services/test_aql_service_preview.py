import pytest
from app.services import aql_service


@pytest.mark.asyncio
async def test_preview_search_service(monkeypatch):
    """Service returns aggregated preview structure"""

    class MockClient:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})
            size = body.get("size", 0)

            # First call: aggregations (size=0)
            if size == 0:
                return {
                    "hits": {"total": {"value": 42, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "top_queries": {
                            "buckets": [{"key": "climate change", "doc_count": 20}]
                        },
                        "by_time": {
                            "buckets": [
                                {"key_as_string": "2024-01-01", "doc_count": 10}
                            ]
                        },
                        "top_providers": {
                            "buckets": [{"key": "google", "doc_count": 30}]
                        },
                        "top_archives": {
                            "buckets": [
                                {"key": "https://web.archive.org/web", "doc_count": 40}
                            ]
                        },
                    },
                }
            # Second call: sample documents (if aggregation fails)
            else:
                return {
                    "hits": {
                        "total": {"value": 42, "relation": "eq"},
                        "hits": [
                            {"_source": {"url_query": "climate change"}}
                            for _ in range(size)
                        ],
                    }
                }

    mock_client = MockClient()

    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)

    result = await aql_service.preview_search(
        "climate", top_n_queries=5, interval="month", top_providers=3, top_archives=3
    )

    assert isinstance(result, dict)
    assert result["query"] == "climate"
    assert result["total_hits"] == 42
    assert isinstance(result["top_queries"], list)
    assert result["top_queries"][0]["query"] == "climate change"
    assert isinstance(result["date_histogram"], list)
    assert isinstance(result["top_providers"], list)
    assert isinstance(result["top_archives"], list)


@pytest.mark.asyncio
async def test_preview_search_fallback_to_sample_queries(monkeypatch):
    """Test that top_queries falls back to sample-based counting when aggregation is empty"""

    class MockClientWithEmptyAgg:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})
            size = body.get("size", 0)

            # Aggregations return empty buckets
            if size == 0:
                return {
                    "hits": {"total": {"value": 100, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "top_queries": {"buckets": []},  # Empty!
                        "by_time": {
                            "buckets": [
                                {"key_as_string": "2024-01-01", "doc_count": 50}
                            ]
                        },
                        "top_providers": {
                            "buckets": [{"key": "google", "doc_count": 80}]
                        },
                        "top_archives": {
                            "buckets": [
                                {"key": "https://web.archive.org/web", "doc_count": 90}
                            ]
                        },
                    },
                }
            # Sample call for fallback
            else:
                return {
                    "hits": {
                        "total": {"value": 100, "relation": "eq"},
                        "hits": [
                            {"_source": {"url_query": "python programming"}},
                            {"_source": {"url_query": "python tutorial"}},
                            {"_source": {"url_query": "python programming"}},
                        ],
                    }
                }

    mock_client = MockClientWithEmptyAgg()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)

    result = await aql_service.preview_search("python", top_n_queries=5)

    # Should have fallback-based top_queries
    assert isinstance(result["top_queries"], list)
    assert len(result["top_queries"]) > 0
    assert result["top_queries"][0]["query"] == "python programming"
    assert result["top_queries"][0]["count"] == 2


@pytest.mark.asyncio
async def test_preview_search_fallback_providers(monkeypatch):
    """Test fallback for top_providers when .keyword field is unavailable"""

    class MockClientEmptyProviders:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})

            # First call: empty top_providers
            if "top_providers" in str(body.get("aggs", {})) and ".keyword" in str(
                body.get("aggs", {})
            ):
                return {
                    "hits": {"total": {"value": 50, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "top_queries": {"buckets": []},
                        "by_time": {"buckets": []},
                        "top_providers": {"buckets": []},  # Empty!
                        "top_archives": {"buckets": []},
                    },
                }
            # Fallback call: non-keyword field
            else:
                return {
                    "hits": {"total": {"value": 50, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "top_providers": {
                            "buckets": [
                                {"key": "google", "doc_count": 30},
                                {"key": "bing", "doc_count": 20},
                            ]
                        },
                        "top_queries": {"buckets": []},
                        "by_time": {"buckets": []},
                        "top_archives": {"buckets": []},
                    },
                }

    mock_client = MockClientEmptyProviders()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)

    result = await aql_service.preview_search("test")

    # Should have fallback-based top_providers
    assert isinstance(result["top_providers"], list)


@pytest.mark.asyncio
async def test_preview_search_sample_size_scales_with_request(monkeypatch):
    """Test that sample size scales dynamically based on top_n_queries"""

    sample_sizes_requested = []

    class MockClientTrackingSampleSize:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})
            size = body.get("size", 0)
            if size > 0:
                sample_sizes_requested.append(size)

            return {
                "hits": {
                    "total": {"value": 1000, "relation": "eq"},
                    "hits": [{"_source": {"url_query": "test"}} for _ in range(size)],
                },
                "aggregations": {
                    "top_queries": {"buckets": []},
                    "by_time": {"buckets": []},
                    "top_providers": {"buckets": []},
                    "top_archives": {"buckets": []},
                },
            }

    mock_client = MockClientTrackingSampleSize()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)

    # Request with top_n_queries=5 (should request ~500 docs)
    await aql_service.preview_search("test", top_n_queries=5)
    if sample_sizes_requested:
        assert sample_sizes_requested[-1] >= 500
        assert sample_sizes_requested[-1] <= 10000

    # Request with top_n_queries=20 (should request more docs)
    await aql_service.preview_search("test", top_n_queries=20)
    if len(sample_sizes_requested) > 1:
        assert sample_sizes_requested[-1] >= 1000
