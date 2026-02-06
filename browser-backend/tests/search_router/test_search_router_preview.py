import pytest


@pytest.fixture
def mock_preview_client(monkeypatch):
    class MockClient:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})
            size = body.get("size", 0)

            # Aggregations call (size=0)
            if size == 0:
                return {
                    "hits": {"total": {"value": 7, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "top_queries": {"buckets": [{"key": "test q", "doc_count": 3}]},
                        "by_time": {
                            "buckets": [{"key_as_string": "2025-01-01", "doc_count": 2}]
                        },
                        "top_providers": {
                            "buckets": [{"key": "google", "doc_count": 5}]
                        },
                        "top_archives": {
                            "buckets": [
                                {"key": "https://web.archive.org/web", "doc_count": 6}
                            ]
                        },
                    },
                }
            # Sample call (size>0)
            else:
                return {
                    "hits": {
                        "total": {"value": 7, "relation": "eq"},
                        "hits": [
                            {"_source": {"url_query": "test q"}} for _ in range(size)
                        ],
                    }
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


def test_serps_preview_with_params(client, mock_preview_client):
    """Test preview with custom top_n_queries and interval parameters"""
    resp = client.get(
        "/api/serps/preview?query=test&top_n_queries=15&"
        "interval=week&top_providers=10&top_archives=8"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"
    assert isinstance(data["total_hits"], int)
    assert isinstance(data["top_queries"], list)
    assert isinstance(data["date_histogram"], list)


def test_serps_preview_with_last_n_months(client, mock_preview_client):
    """Test preview with last_n_months filter"""
    resp = client.get("/api/serps/preview?query=test&last_n_months=12")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"
    assert "date_histogram" in data
