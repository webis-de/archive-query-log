import pytest


@pytest.fixture
def mock_preview_client(monkeypatch):
    class MockClient:
        async def search(self, *args, **kwargs):
            return {
                "hits": {"total": {"value": 7, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "top_queries": {"buckets": [{"key": "test q", "doc_count": 3}]},
                    "by_time": {
                        "buckets": [{"key_as_string": "2025-01-01", "doc_count": 2}]
                    },
                    "top_providers": {"buckets": [{"key": "google", "doc_count": 5}]},
                    "top_archives": {
                        "buckets": [
                            {"key": "https://web.archive.org/web", "doc_count": 6}
                        ]
                    },
                },
            }

    mock_client = MockClient()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)
    return mock_client


def test_serps_preview_router(client, mock_preview_client):
    resp = client.get("/api/serps/preview?query=test")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_hits" in data
    assert "top_queries" in data
    assert "date_histogram" in data
    assert "top_providers" in data
    assert "top_archives" in data
