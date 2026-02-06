import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Utilities import
from app.utils.url_cleaner import remove_tracking_parameters
from app.routers.search import router


# ---------------------
# Test Setup
# ---------------------
@pytest.fixture
def client():
    """Create test client with FastAPI app including the search router"""
    app = FastAPI()
    app.include_router(router)
    app.state.limiter_enabled = False  # Disable rate limiting
    return TestClient(app, raise_server_exceptions=False)


# ---------------------
# Helper: Mock async function returning value
# ---------------------
def async_return(value):
    mock = AsyncMock()
    mock.return_value = value
    return mock


# -------------------------------------------------------------------
# Additional edge case tests
# -------------------------------------------------------------------
def test_remove_tracking_parameters():
    """Test tracking parameter removal utility"""
    url = "https://google.com/search?q=test&utm_source=email&fbclid=123"
    cleaned = remove_tracking_parameters(url)
    assert "utm_source" not in cleaned
    assert "fbclid" not in cleaned
    assert "q=test" in cleaned


def test_unified_search_no_results(client):
    """Test unified search returning no results (now returns 200 with empty array)"""
    mock_result = {"hits": [], "total": 0}
    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_result)
    ):
        r = client.get("/serps?query=nonexistent")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["total"] == 0
        assert data["results"] == []


def test_get_serp_unified_include_with_whitespace(client):
    """Test unified SERP detail with include parameter containing whitespace"""
    mock_serp = {
        "_id": "test-id",
        "_source": {"capture": {"url": "https://google.com"}},
    }
    mock_url_data = {"serp_id": "test-id", "original_url": "https://google.com"}
    mock_unfurl_data = {
        "serp_id": "test-id",
        "original_url": "https://google.com",
        "parsed": {"scheme": "https", "domain": "google.com"},
    }

    with patch(
        "app.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ), patch(
        "app.routers.search.aql_service.get_serp_original_url",
        new=async_return(mock_url_data),
    ), patch(
        "app.routers.search.aql_service.get_serp_unfurl",
        new=async_return(mock_unfurl_data),
    ):
        r = client.get("/serps/test-id?include=original_url,unfurl")
        assert r.status_code == 200
        assert "original_url" in r.json()
        assert "unfurl" in r.json()
