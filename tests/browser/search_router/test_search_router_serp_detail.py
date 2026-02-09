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
# Tests for unified SERP detail endpoint - Basic
# -------------------------------------------------------------------
def test_get_serp_unified_basic(client):
    """Test getting SERP without any includes"""
    mock_serp = {
        "_id": "test-uuid-1234",
        "_source": {
            "url_query": "test query",
            "capture": {
                "url": "https://example.com/search",
                "timestamp": "2021-01-01T00:00:00+00:00",
            },
            "provider": {"domain": "example.com"},
        },
        "found": True,
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ):
        r = client.get("/serps/test-uuid-1234")
        assert r.status_code == 200
        assert r.json()["serp_id"] == "test-uuid-1234"
        assert r.json()["serp"] == mock_serp
        assert "original_url" not in r.json()
        assert "memento_url" not in r.json()


# -------------------------------------------------------------------
# Tests for unified SERP detail - Include original_url
# -------------------------------------------------------------------
def test_get_serp_unified_with_original_url(client):
    """Test getting SERP with original URL included"""
    mock_serp = {"_id": "test-id", "_source": {}}
    mock_url_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=test",
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_original_url",
        new=async_return(mock_url_data),
    ):
        r = client.get("/serps/test-id?include=original_url")
        assert r.status_code == 200
        assert r.json()["original_url"] == "https://google.com/search?q=test"
        assert "serp" in r.json()


def test_get_serp_unified_with_tracking_removal(client):
    """Test getting SERP with tracking parameters removed"""
    mock_serp = {"_id": "test-id", "_source": {}}
    mock_url_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=test&utm_source=email",
        "url_without_tracking": "https://google.com/search?q=test",
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_original_url",
        new=async_return(mock_url_data),
    ):
        r = client.get("/serps/test-id?include=original_url&remove_tracking=true")
        assert r.status_code == 200
        assert (
            r.json()["original_url"]
            == "https://google.com/search?q=test&utm_source=email"
        )
        assert r.json()["url_without_tracking"] == "https://google.com/search?q=test"


# -------------------------------------------------------------------
# Tests for unified SERP detail - Include memento_url
# -------------------------------------------------------------------
def test_get_serp_unified_with_memento_url(client):
    """Test getting SERP with memento URL included"""
    mock_serp = {"_id": "test-id", "_source": {}}
    mock_memento_data = {
        "serp_id": "test-id",
        "memento_url": "https://web.archive.org/web/20210101000000/https://google.com",
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_memento_url",
        new=async_return(mock_memento_data),
    ):
        r = client.get("/serps/test-id?include=memento_url")
        assert r.status_code == 200
        assert "memento_url" in r.json()
        assert "web.archive.org" in r.json()["memento_url"]


# -------------------------------------------------------------------
# Tests for unified SERP detail - Include related
# -------------------------------------------------------------------
def test_get_serp_unified_with_related(client):
    """Test getting SERP with related SERPs included"""
    mock_serp = {"_id": "test-id", "_source": {}}
    mock_related = [
        {"_id": "serp-456", "_source": {"url_query": "python"}},
        {"_id": "serp-789", "_source": {"url_query": "python"}},
    ]

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_related_serps",
        new=async_return(mock_related),
    ):
        r = client.get("/serps/test-id?include=related&related_size=10")
        assert r.status_code == 200
        assert "related" in r.json()
        assert r.json()["related"]["count"] == 2
        assert len(r.json()["related"]["serps"]) == 2


def test_get_serp_unified_related_invalid_size(client):
    """Test invalid related_size parameter"""
    r = client.get("/serps/test-id?include=related&related_size=0")
    assert r.status_code == 400


# -------------------------------------------------------------------
# Tests for unified SERP detail - Include unfurl
# -------------------------------------------------------------------
def test_get_serp_unified_with_unfurl(client):
    """Test getting SERP with unfurled URL included"""
    mock_serp = {
        "_id": "test-id",
        "_source": {"capture": {"url": "https://google.com/search?q=python"}},
    }
    mock_unfurl_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=python",
        "parsed": {
            "scheme": "https",
            "netloc": "google.com",
            "domain_parts": {"domain": "google", "suffix": "com"},
            "path": "/search",
            "query_parameters": {"q": "python"},
        },
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_unfurl",
        new=async_return(mock_unfurl_data),
    ):
        r = client.get("/serps/test-id?include=unfurl")
        assert r.status_code == 200
        assert "unfurl" in r.json()
        assert r.json()["unfurl"]["scheme"] == "https"
        assert r.json()["unfurl"]["domain_parts"]["domain"] == "google"


# -------------------------------------------------------------------
# Tests for unified SERP detail - Multiple includes
# -------------------------------------------------------------------
def test_get_serp_unified_multiple_includes(client):
    """Test getting SERP with multiple fields included"""
    mock_serp = {
        "_id": "test-id",
        "_source": {"capture": {"url": "https://google.com"}},
    }
    mock_url_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=test",
    }
    mock_memento_data = {
        "serp_id": "test-id",
        "memento_url": "https://web.archive.org/web/20210101/https://google.com",
    }
    mock_related = [{"_id": "related-1", "_source": {}}]
    mock_unfurl_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com",
        "parsed": {"scheme": "https", "domain": "google.com"},
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_original_url",
        new=async_return(mock_url_data),
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_memento_url",
        new=async_return(mock_memento_data),
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_related_serps",
        new=async_return(mock_related),
    ), patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_unfurl",
        new=async_return(mock_unfurl_data),
    ):
        r = client.get("/serps/test-id?include=original_url,memento_url,related,unfurl")
        assert r.status_code == 200
        assert "original_url" in r.json()
        assert "memento_url" in r.json()
        assert "related" in r.json()
        assert "unfurl" in r.json()


# -------------------------------------------------------------------
# Tests for unified SERP detail - Error handling
# -------------------------------------------------------------------
def test_get_serp_unified_not_found(client):
    """Test unified SERP detail when SERP doesn't exist"""
    with patch("archive_query_log.browser.routers.search.aql_service.get_serp_by_id", new=async_return(None)):
        r = client.get("/serps/nonexistent-id")
        assert r.status_code == 404


def test_get_serp_unified_elasticsearch_error(client):
    """Test unified SERP detail with Elasticsearch connection error"""

    async def raise_error(*args, **kwargs):
        from elasticsearch import ConnectionError as ESConnectionError

        raise ESConnectionError(message="ES down")

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id",
        new=AsyncMock(side_effect=raise_error),
    ):
        r = client.get("/serps/test-id")
        assert r.status_code == 503
        assert "connection" in r.json()["detail"].lower()
