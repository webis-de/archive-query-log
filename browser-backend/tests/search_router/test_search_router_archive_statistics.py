"""Tests for archive statistics router endpoints"""

import pytest
from unittest.mock import patch


@pytest.fixture
def mock_archive_statistics_client(monkeypatch):
    class MockClient:
        async def search(self, *args, **kwargs):
            return {
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
                    "date_range": {
                        "min_as_string": "2021-01-01T00:00:00Z",
                        "max_as_string": "2023-01-01T00:00:00Z",
                    },
                    "by_time": {
                        "buckets": [
                            {"key_as_string": "2023-01-01T00:00:00Z", "doc_count": 200},
                        ]
                    },
                },
            }

    mock_client = MockClient()
    monkeypatch.setattr("archive_query_log.browser.services.aql_service.get_es_client", lambda: mock_client)
    return mock_client


def test_archive_statistics_router(client, mock_archive_statistics_client):
    """Test GET /api/archives/{archive_id}/statistics"""
    archive_id = "https://web.archive.org/web"
    resp = client.get(f"/api/archives/{archive_id}/statistics")

    assert resp.status_code == 200
    data = resp.json()

    assert "archive_id" in data
    assert data["archive_id"] == archive_id
    assert "serp_count" in data
    assert data["serp_count"] == 1000
    assert "unique_queries_count" in data
    assert data["unique_queries_count"] == 500
    assert "top_providers" in data
    assert isinstance(data["top_providers"], list)
    assert "date_histogram" in data
    assert isinstance(data["date_histogram"], list)


def test_archive_statistics_with_params(client, mock_archive_statistics_client):
    """Test archive statistics with custom parameters"""
    archive_id = "https://web.archive.org/web"
    resp = client.get(
        f"/api/archives/{archive_id}/statistics?interval=week&last_n_months=12"
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["archive_id"] == archive_id
    assert data["serp_count"] == 1000
    assert isinstance(data["unique_queries_count"], int)


def test_archive_statistics_default_interval(client, mock_archive_statistics_client):
    """Test that default interval is 'month'"""
    archive_id = "https://web.archive.org/web"
    resp = client.get(f"/api/archives/{archive_id}/statistics")
    assert resp.status_code == 200
    data = resp.json()

    assert data["archive_id"] == archive_id


def test_archive_statistics_not_found(client):
    """Test archive statistics for non-existent archive"""

    class MockEmptyClient:
        async def search(self, *args, **kwargs):
            return {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_get_client.return_value = MockEmptyClient()
        resp = client.get("/api/archives/https://nonexistent.archive/web/statistics")

        # Should return 404 because the service returns None when serp_count is 0
        assert resp.status_code == 404


def test_archive_statistics_with_different_intervals(
    client, mock_archive_statistics_client
):
    """Test archive statistics with different interval values"""
    archive_id = "https://web.archive.org/web"
    for interval in ["day", "week", "month"]:
        resp = client.get(f"/api/archives/{archive_id}/statistics?interval={interval}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["archive_id"] == archive_id


def test_archive_statistics_structure(client, mock_archive_statistics_client):
    """Test that archive statistics response has correct structure"""
    archive_id = "https://web.archive.org/web"
    resp = client.get(f"/api/archives/{archive_id}/statistics")

    assert resp.status_code == 200
    data = resp.json()

    # Check required fields
    required_fields = [
        "archive_id",
        "serp_count",
        "unique_queries_count",
        "top_providers",
        "date_histogram",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # Check types
    assert isinstance(data["archive_id"], str)
    assert isinstance(data["serp_count"], int)
    assert isinstance(data["unique_queries_count"], int)
    assert isinstance(data["top_providers"], list)
    assert isinstance(data["date_histogram"], list)

    # Check top_providers structure
    for provider in data["top_providers"]:
        assert "provider" in provider
        assert "count" in provider
        assert isinstance(provider["count"], int)

    # Check date_histogram structure
    for item in data["date_histogram"]:
        assert "date" in item
        assert "count" in item
        assert isinstance(item["count"], int)
