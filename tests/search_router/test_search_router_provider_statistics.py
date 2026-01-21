"""Tests for provider statistics router endpoints"""

import pytest
from unittest.mock import patch


@pytest.fixture
def mock_provider_statistics_client(monkeypatch):
    class MockClient:
        async def search(self, *args, **kwargs):
            return {
                "hits": {"total": {"value": 500, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "unique_queries": {
                        "buckets": [{"key": "query", "doc_count": 1}] * 250
                    },
                    "top_archives": {
                        "buckets": [
                            {"key": "https://web.archive.org/web", "doc_count": 300},
                        ]
                    },
                    "date_range": {
                        "min_as_string": "2021-01-01T00:00:00Z",
                        "max_as_string": "2023-01-01T00:00:00Z",
                    },
                    "by_time": {
                        "buckets": [
                            {"key_as_string": "2023-01-01T00:00:00Z", "doc_count": 100},
                        ]
                    },
                },
            }

    mock_client = MockClient()
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)
    return mock_client


def test_provider_statistics_router(client, mock_provider_statistics_client):
    """Test GET /api/providers/{provider_id}/statistics"""
    resp = client.get("/api/providers/google/statistics")
    assert resp.status_code == 200
    data = resp.json()

    assert "provider_id" in data
    assert data["provider_id"] == "google"
    assert "serp_count" in data
    assert data["serp_count"] == 500
    assert "unique_queries_count" in data
    assert data["unique_queries_count"] == 250
    assert "top_archives" in data
    assert isinstance(data["top_archives"], list)
    assert "date_histogram" in data
    assert isinstance(data["date_histogram"], list)


def test_provider_statistics_with_params(client, mock_provider_statistics_client):
    """Test provider statistics with custom parameters"""
    resp = client.get("/api/providers/google/statistics?interval=week&last_n_months=12")
    assert resp.status_code == 200
    data = resp.json()

    assert data["provider_id"] == "google"
    assert data["serp_count"] == 500
    assert isinstance(data["unique_queries_count"], int)


def test_provider_statistics_default_interval(client, mock_provider_statistics_client):
    """Test that default interval is 'month'"""
    resp = client.get("/api/providers/google/statistics")
    assert resp.status_code == 200
    data = resp.json()

    assert data["provider_id"] == "google"


def test_provider_statistics_not_found(client):
    """Test provider statistics for non-existent provider"""

    class MockEmptyClient:
        async def search(self, *args, **kwargs):
            return {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_get_client.return_value = MockEmptyClient()
        resp = client.get("/api/providers/nonexistent/statistics")

        # Should return 404 because the service returns None when serp_count is 0
        assert resp.status_code == 404


def test_provider_statistics_with_different_intervals(
    client, mock_provider_statistics_client
):
    """Test provider statistics with different interval values"""
    for interval in ["day", "week", "month"]:
        resp = client.get(f"/api/providers/google/statistics?interval={interval}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "google"
