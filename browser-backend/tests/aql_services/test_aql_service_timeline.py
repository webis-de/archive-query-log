import pytest
from app.services import aql_service


@pytest.mark.asyncio
async def test_serps_timeline_service(monkeypatch):
    """Service returns date histogram counts filtered by query/provider/archive and strips time."""

    class MockClient:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})
            assert body.get("size") == 0
            # Ensure hidden filter is applied via bool.filter.must_not
            query = body.get("query", {})
            if "bool" in query:
                filters = query["bool"].get("filter", [])
                assert any("must_not" in f.get("bool", {}) for f in filters)
            return {
                "hits": {"total": {"value": 12, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "by_time": {
                        "buckets": [
                            {"key_as_string": "2025-01-01T00:00:00Z", "doc_count": 5},
                            {"key_as_string": "2025-02-01T00:00:00Z", "doc_count": 7},
                        ]
                    }
                },
            }

    mock_client = MockClient()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)

    result = await aql_service.serps_timeline(
        query="test",
        provider_id="google",
        archive_id="https://web.archive.org/web",
        interval="month",
        last_n_months=12,
    )

    assert isinstance(result, dict)
    assert result["query"] == "test"
    assert result["provider_id"] == "google"
    assert result["archive_id"] == "https://web.archive.org/web"
    assert result["interval"] == "month"
    assert result["last_n_months"] == 12
    assert result["total_hits"] == 12
    assert isinstance(result["date_histogram"], list)
    assert result["date_histogram"][0]["date"] == "2025-01-01"
    assert result["date_histogram"][0]["count"] == 5
