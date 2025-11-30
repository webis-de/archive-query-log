# tests/test_legacy_endpoints.py

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
# Tests for legacy endpoints (backwards compatibility)
# -------------------------------------------------------------------
def test_legacy_search_basic(client):
    """Test legacy basic search endpoint still works"""
    with patch("app.routers.search.aql_service.search_basic", new=async_return([1, 2])):
        r = client.get("/search/basic?query=test&size=2")
        assert r.status_code == 200
        assert r.json() == {"count": 2, "results": [1, 2]}


def test_legacy_search_providers(client):
    """Test legacy provider search endpoint still works"""
    with patch(
        "app.routers.search.aql_service.search_providers", new=async_return(["a"])
    ):
        r = client.get("/search/providers?name=test&size=1")
        assert r.status_code == 200


def test_legacy_search_advanced(client):
    """Test legacy advanced search endpoint still works"""
    with patch(
        "app.routers.search.aql_service.search_advanced", new=async_return(["ok"])
    ):
        r = client.get("/search/advanced?query=x&size=1")
        assert r.status_code == 200


def test_legacy_search_by_year(client):
    """Test legacy by-year search endpoint still works"""
    with patch(
        "app.routers.search.aql_service.search_advanced", new=async_return([10])
    ):
        r = client.get("/search/by-year?query=t&year=2020&size=1")
        assert r.status_code == 200


def test_legacy_autocomplete_providers(client):
    """Test legacy autocomplete endpoint still works"""
    with patch(
        "app.routers.search.aql_service.autocomplete_providers", new=async_return(["p"])
    ):
        r = client.get("/autocomplete/providers?q=te&size=1")
        assert r.status_code == 200


def test_legacy_get_original_url(client):
    """Test legacy original URL endpoint still works"""
    expected_response = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=test",
    }

    with patch(
        "app.routers.search.aql_service.get_serp_original_url",
        new=async_return(expected_response),
    ):
        r = client.get("/serp/test-id/original-url")
        assert r.status_code == 200


def test_legacy_get_memento_url(client):
    """Test legacy memento URL endpoint still works"""
    expected_response = {
        "serp_id": "test-id",
        "memento_url": "https://web.archive.org/web/20210101/https://google.com",
    }

    with patch(
        "app.routers.search.aql_service.get_serp_memento_url",
        new=async_return(expected_response),
    ):
        r = client.get("/serp/test-id/memento-url")
        assert r.status_code == 200


def test_legacy_get_related_serps(client):
    """Test legacy related SERPs endpoint still works"""
    mock_related = [{"_id": "serp-1", "_source": {}}]

    with patch(
        "app.routers.search.aql_service.get_related_serps",
        new=async_return(mock_related),
    ):
        r = client.get("/serp/test-id/related?size=10")
        assert r.status_code == 200
        assert r.json()["count"] == 1


def test_legacy_get_unfurl(client):
    """Test legacy unfurl endpoint still works"""
    expected_response = {
        "serp_id": "test-id",
        "original_url": "https://google.com",
        "parsed": {"scheme": "https"},
    }

    with patch(
        "app.routers.search.aql_service.get_serp_unfurl",
        new=async_return(expected_response),
    ):
        r = client.get("/serp/test-id/unfurl")
        assert r.status_code == 200
