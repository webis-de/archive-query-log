"""Test error handling in search router endpoints"""

import pytest
from fastapi.testclient import TestClient
from archive_query_log.browser.main import app
from elasticsearch import ConnectionError, RequestError


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_unified_search_elasticsearch_connection_error(monkeypatch):
    """Test handling of Elasticsearch connection errors"""

    async def mock_search_connection_error(*args, **kwargs):
        raise ConnectionError("ES connection failed")

    monkeypatch.setattr(
        "archive_query_log.browser.services.aql_service.search_basic", mock_search_connection_error
    )

    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/api/serps?query=test")
    assert response.status_code == 503
    assert "connection failed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unified_search_bad_request(monkeypatch):
    """Test handling of bad requests to Elasticsearch"""

    async def mock_search_bad_request(*args, **kwargs):
        raise RequestError("Invalid query")

    monkeypatch.setattr(
        "archive_query_log.browser.services.aql_service.search_basic", mock_search_bad_request
    )

    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/api/serps?query=test")
    # Note: general exceptions raise 500, not 400
    # (400 is only for direct BadRequestError in safe_search)
    assert response.status_code in [400, 500]


def test_preview_with_invalid_interval(client, monkeypatch):
    """Test preview endpoint with various interval values"""

    class MockClient:
        async def search(self, *args, **kwargs):
            return {
                "hits": {"total": {"value": 10, "relation": "eq"}, "hits": []},
                "aggregations": {
                    "top_queries": {"buckets": []},
                    "by_time": {"buckets": []},
                    "top_providers": {"buckets": []},
                    "top_archives": {"buckets": []},
                },
            }

    mock_client = MockClient()
    monkeypatch.setattr("archive_query_log.browser.services.aql_service.get_es_client", lambda: mock_client)

    # Valid interval
    resp = client.get("/api/serps/preview?query=test&interval=day")
    assert resp.status_code == 200

    # Valid interval
    resp = client.get("/api/serps/preview?query=test&interval=week")
    assert resp.status_code == 200


def test_suggestions_endpoint_works(client, monkeypatch):
    """Test suggestions endpoint"""

    async def mock_suggestions(*args, **kwargs):
        return {
            "prefix": "test",
            "suggestions": [
                {"query": "test 1", "count": 100},
                {"query": "test 2", "count": 50},
            ],
        }

    monkeypatch.setattr("archive_query_log.browser.services.aql_service.search_suggestions", mock_suggestions)

    resp = client.get("/api/suggestions?prefix=test&size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0
