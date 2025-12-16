import pytest
from app.services import aql_service


@pytest.mark.asyncio
async def test_preview_search_service(monkeypatch):
    """Service returns aggregated preview structure"""

    class MockClient:
        async def search(self, *args, **kwargs):
            return {
                "hits": {"total": {"value": 42, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "top_queries": {
                        "buckets": [{"key": "climate change", "doc_count": 20}]
                    },
                    "by_time": {
                        "buckets": [{"key_as_string": "2024-01-01", "doc_count": 10}]
                    },
                    "top_providers": {"buckets": [{"key": "google", "doc_count": 30}]},
                    "top_archives": {
                        "buckets": [
                            {"key": "https://web.archive.org/web", "doc_count": 40}
                        ]
                    },
                },
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
