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

    # Mock the limiter to disable rate limiting in tests
    with patch("app.routers.search.limiter") as mock_limiter:
        # Make the limiter decorator a no-op
        mock_limiter.limit = lambda *args, **kwargs: lambda f: f

        app.include_router(router)

    return TestClient(app, raise_server_exceptions=False)


# ---------------------
# Helper: Mock async function returning value
# ---------------------
def async_return(value):
    mock = AsyncMock()
    mock.return_value = value
    return mock


# -------------------------------------------------------------------
# Tests for pagination - Basic
# -------------------------------------------------------------------
def test_unified_search_with_pagination_10(client):
    """Test unified search with page_size=10"""
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(10)],
        "total": 100,
    }

    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_results)
    ):
        r = client.get("/serps?query=test&page_size=10")
        assert r.status_code == 200
        data = r.json()

        assert data["query"] == "test"
        assert data["count"] == 10
        assert data["total"] == 100
        assert data["page_size"] == 10
        assert data["total_pages"] == 10
        assert data["pagination"]["results_per_page"] == 10
        assert data["pagination"]["total_pages"] == 10
        assert len(data["results"]) == 10


def test_unified_search_with_pagination_20(client):
    """Test unified search with page_size=20"""
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(20)],
        "total": 100,
    }

    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_results)
    ):
        r = client.get("/serps?query=test&page_size=20")
        assert r.status_code == 200
        data = r.json()

        assert data["page_size"] == 20
        assert data["total_pages"] == 5
        assert len(data["results"]) == 20


def test_unified_search_with_pagination_50(client):
    """Test unified search with page_size=50"""
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(50)],
        "total": 100,
    }

    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_results)
    ):
        r = client.get("/serps?query=test&page_size=50")
        assert r.status_code == 200
        data = r.json()

        assert data["page_size"] == 50
        assert data["total_pages"] == 2
        assert len(data["results"]) == 50


def test_unified_search_invalid_page_size(client):
    """Test unified search with invalid page_size"""
    r = client.get("/serps?query=test&page_size=25")
    assert r.status_code == 400
    assert "page_size must be one of" in r.json()["detail"]


def test_unified_search_pagination_ceiling_division(client):
    """Test that total_pages calculation is correct (ceiling division)"""
    # 25 results with page_size=10 should give 3 pages
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(10)],
        "total": 25,
    }

    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_results)
    ):
        r = client.get("/serps?query=test&page_size=10")
        assert r.status_code == 200
        assert r.json()["total_pages"] == 3


def test_unified_search_default_page_size(client):
    """Test unified search with default page_size (10)"""
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(10)],
        "total": 100,
    }

    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_results)
    ):
        r = client.get("/serps?query=test")
        assert r.status_code == 200
        data = r.json()
        assert data["page_size"] == 10
        assert data["total_pages"] == 10


# -------------------------------------------------------------------
# Tests for pagination - Advanced Search
# -------------------------------------------------------------------
def test_unified_search_advanced_with_pagination(client):
    """Test advanced search with pagination"""
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(20)],
        "total": 150,
    }

    with patch(
        "app.routers.search.aql_service.search_advanced",
        new=async_return(mock_results),
    ):
        r = client.get("/serps?query=test&year=2024&provider_id=google&page_size=20")
        assert r.status_code == 200
        data = r.json()

        assert data["total"] == 150
        assert data["total_pages"] == 8  # ceil(150/20) = 8
        assert data["page_size"] == 20


def test_unified_search_pagination_response_structure(client):
    """Test response contains all pagination information"""
    mock_results = {
        "hits": [{"_id": str(i), "_source": {}} for i in range(10)],
        "total": 45,
    }

    with patch(
        "app.routers.search.aql_service.search_basic", new=async_return(mock_results)
    ):
        r = client.get("/serps?query=test&page_size=10")
        assert r.status_code == 200
        data = r.json()

        # Check all required fields
        assert "query" in data
        assert "count" in data
        assert "total" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert "pagination" in data
        assert "results" in data

        # Check pagination structure
        pagination = data["pagination"]
        assert pagination["current_results"] == 10
        assert pagination["total_results"] == 45
        assert pagination["results_per_page"] == 10
        assert pagination["total_pages"] == 5
