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
    app.include_router(router)
    app.state.limiter_enabled = False  # Disable rate limiting for tests
    return TestClient(app, raise_server_exceptions=False)


# ---------------------
# Helper: Mock async function returning value
# ---------------------
def async_return(value):
    mock = AsyncMock()
    mock.return_value = value
    return mock


# -------------------------------------------------------------------
# Tests for unified search endpoint
# -------------------------------------------------------------------


def test_unified_search_basic(client):
    """Test basic search via unified endpoint"""
    mock_result = {"hits": [1, 2], "total": 2}
    with patch(
        "archive_query_log.browser.routers.search.aql_service.search_basic", new=async_return(mock_result)
    ):
        r = client.get("/serps?query=test")  # Default page_size=10
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert data["total"] == 2
        assert data["results"] == [1, 2]


def test_unified_search_advanced(client):
    """Test advanced search via unified endpoint"""
    mock_result = {"hits": ["ok"], "total": 1}
    with patch(
        "archive_query_log.browser.routers.search.aql_service.search_advanced", new=async_return(mock_result)
    ):
        r = client.get(
            "/serps?query=x&year=2024&provider_id=google"
        )  # Default page_size=10
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["total"] == 1
        assert data["results"] == ["ok"]


def test_unified_search_by_year(client):
    """Test search with year filter"""
    mock_result = {"hits": [10], "total": 1}
    with patch(
        "archive_query_log.browser.routers.search.aql_service.search_advanced", new=async_return(mock_result)
    ):
        r = client.get("/serps?query=t&year=2020")  # Default page_size=10
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["results"] == [10]


def test_unified_search_all_filters(client):
    """Test search with all filters"""
    mock_result = {"hits": ["filtered"], "total": 1}
    with patch(
        "archive_query_log.browser.routers.search.aql_service.search_advanced",
        new=async_return(mock_result),
    ):
        r = client.get(
            "/serps?query=x&provider_id=123&year=2021&status_code=200&page_size=10"
        )
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["results"] == ["filtered"]


def test_unified_search_invalid_page_size(client):
    """Test SERP search with invalid page_size"""
    r = client.get("/serps?query=test&page_size=25")
    assert r.status_code == 400


def test_unified_search_no_results(client):
    """Test unified search returning no results (now returns 200 with empty results)"""
    mock_result = {"hits": [], "total": 0}
    with patch(
        "archive_query_log.browser.routers.search.aql_service.search_basic", new=async_return(mock_result)
    ):
        r = client.get("/serps?query=nonexistent")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["total"] == 0
        assert data["results"] == []
