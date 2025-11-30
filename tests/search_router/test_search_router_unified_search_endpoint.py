import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.routers.search import router


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
    with patch("app.routers.search.aql_service.search_basic", new=async_return([1, 2])):
        r = client.get("/serps?query=test&size=2")
        assert r.status_code == 200
        assert r.json() == {"count": 2, "results": [1, 2]}


def test_unified_search_advanced(client):
    """Test advanced search via unified endpoint"""
    with patch(
        "app.routers.search.aql_service.search_advanced", new=async_return(["ok"])
    ):
        r = client.get("/serps?query=x&year=2024&provider_id=google&size=1")
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": ["ok"]}


def test_unified_search_by_year(client):
    """Test search with year filter"""
    with patch(
        "app.routers.search.aql_service.search_advanced", new=async_return([10])
    ):
        r = client.get("/serps?query=t&year=2020&size=1")
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": [10]}


def test_unified_search_all_filters(client):
    """Test search with all filters"""
    with patch(
        "app.routers.search.aql_service.search_advanced",
        new=async_return(["filtered"]),
    ):
        r = client.get(
            "/serps?query=x&provider_id=123&year=2021&status_code=200&size=5"
        )
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": ["filtered"]}


def test_unified_search_invalid_size(client):
    """Test SERP search with invalid size"""
    r = client.get("/serps?query=test&size=0")
    assert r.status_code == 400


def test_unified_search_no_results(client):
    """Test unified search returning no results"""
    with patch("app.routers.search.aql_service.search_basic", new=async_return([])):
        r = client.get("/serps?query=nonexistent")
        assert r.status_code == 404
