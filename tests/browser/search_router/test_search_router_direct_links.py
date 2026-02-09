import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from archive_query_log.browser.routers.search import router


# ---------------------
# Test Setup
# ---------------------
@pytest.fixture
def client():
    """Create test client with fresh FastAPI app instance including the search router"""
    app = FastAPI()

    # Mock the limiter to disable rate limiting in tests
    with patch("archive_query_log.browser.routers.search.limiter") as mock_limiter:
        # Make the limiter decorator a no-op
        mock_limiter.limit = lambda *args, **kwargs: lambda f: f

        archive_query_log.browser.include_router(router)

    return TestClient(app, raise_server_exceptions=False)


# ---------------------
# Helper: Mock async function returning value
# ---------------------
def async_return(value):
    mock = AsyncMock()
    mock.return_value = value
    return mock


# -------------------------------------------------------------------
# Tests for unified SERP detail - Include direct_links
# -------------------------------------------------------------------
def test_get_serp_unified_with_direct_links(client):
    """Test getting SERP with direct links included"""
    mock_serp = {"_id": "test-id", "_source": {}}
    mock_direct_links_data = {
        "serp_id": "test-id",
        "direct_links_count": 2,
        "direct_links": [
            {
                "position": 1,
                "url": "https://example.com/1",
                "title": "Result 1",
                "snippet": "First result snippet",
            },
            {
                "position": 2,
                "url": "https://example.com/2",
                "title": "Result 2",
                "snippet": "Second result snippet",
            },
        ],
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_direct_links",
        new=async_return(mock_direct_links_data),
    ):
        r = client.get("/serps/test-id?include=direct_links")
        assert r.status_code == 200
        assert "direct_links" in r.json()
        assert r.json()["direct_links_count"] == 2
        assert len(r.json()["direct_links"]) == 2
        assert r.json()["direct_links"][0]["position"] == 1
        assert r.json()["direct_links"][0]["url"] == "https://example.com/1"


def test_get_serp_unified_with_direct_links_and_other_fields(client):
    """Test getting SERP with direct links and other fields included"""
    mock_serp = {
        "_id": "test-id",
        "_source": {"capture": {"url": "https://google.com/search?q=test"}},
    }
    mock_url_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=test",
    }
    mock_direct_links_data = {
        "serp_id": "test-id",
        "direct_links_count": 1,
        "direct_links": [
            {
                "position": 1,
                "url": "https://example.com",
                "title": "Example",
                "snippet": "Example website",
            }
        ],
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_original_url",
        new=async_return(mock_url_data),
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_direct_links",
        new=async_return(mock_direct_links_data),
    ):
        r = client.get("/serps/test-id?include=original_url,direct_links")
        assert r.status_code == 200
        assert "original_url" in r.json()
        assert "direct_links" in r.json()
        assert r.json()["direct_links_count"] == 1


def test_get_serp_unified_direct_links_no_results(client):
    """Test getting SERP with direct links when no results are available"""
    mock_serp = {"_id": "test-id", "_source": {}}
    mock_direct_links_data = {
        "serp_id": "test-id",
        "direct_links_count": 0,
        "direct_links": [],
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_direct_links",
        new=async_return(mock_direct_links_data),
    ):
        r = client.get("/serps/test-id?include=direct_links")
        assert r.status_code == 200
        assert r.json()["direct_links_count"] == 0
        assert r.json()["direct_links"] == []
