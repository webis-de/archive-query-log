import pytest


@pytest.fixture
def mock_timeline_client(monkeypatch):
    class MockClient:
        async def search(self, *args, **kwargs):
            body = kwargs.get("body", {})
            size = body.get("size", 0)
            assert size == 0
            return {
                "hits": {"total": {"value": 9, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "by_time": {
                        "buckets": [
                            {"key_as_string": "2025-01-01T00:00:00Z", "doc_count": 4},
                            {"key_as_string": "2025-02-01T00:00:00Z", "doc_count": 5},
                        ]
                    }
                },
            }

    mock_client = MockClient()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)
    return mock_client


def test_serps_timeline_router(client, mock_timeline_client):
    resp = client.get(
        "/api/serps/timeline?query=test&provider_id=google&archive_id=https://web.archive.org/web"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"
    assert data["provider_id"] == "google"
    assert data["archive_id"] == "https://web.archive.org/web"
    assert data["total_hits"] == 9
    assert isinstance(data["date_histogram"], list)
    assert data["date_histogram"][0]["date"] == "2025-01-01"


def test_serps_timeline_with_params(client, mock_timeline_client):
    resp = client.get("/api/serps/timeline?query=test&interval=week&last_n_months=6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "test"
    assert data["interval"] == "week"
    assert data["last_n_months"] == 6


def test_serps_timeline_invalid_interval(client):
    resp = client.get("/api/serps/timeline?query=test&interval=year")
    assert resp.status_code == 400
    data = resp.json()
    assert "interval" in data["detail"]


def test_serps_timeline_invalid_last_n_months(client):
    resp = client.get("/api/serps/timeline?query=test&last_n_months=-1")
    assert resp.status_code == 400
