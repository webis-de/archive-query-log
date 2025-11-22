import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.routers.search import router, safe_search


from elasticsearch import ApiError, BadRequestError, ConnectionError

from fastapi import HTTPException


# ---------------------
# Test Setup
# ---------------------
@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------
# Helper: Mock async function returning value
# ---------------------
def async_return(value):
    mock = AsyncMock()
    mock.return_value = value
    return mock


# -------------------------------------------------------------------
# 1. Tests for safe_search()
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_safe_search_success():
    coro = async_return([{"x": 1}])()
    result = await safe_search(coro)
    assert result == [{"x": 1}]


@pytest.mark.asyncio
async def test_safe_search_no_results():
    coro = async_return([])()
    with pytest.raises(HTTPException) as exc:
        await safe_search(coro)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_safe_search_connection_error():
    async def boom():
        raise ConnectionError(message="conn", meta=None)

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_safe_search_transport_error():
    async def boom():
        raise ApiError(message="api error", meta=None)

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_safe_search_request_error():
    async def boom():
        raise BadRequestError(message="bad rq", meta=None)

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())

    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_safe_search_generic_error():
    async def boom():
        raise Exception()

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())

    assert exc.value.status_code == 500


# -------------------------------------------------------------------
# 2. Tests for endpoints
# -------------------------------------------------------------------
def test_search_basic_success(client):
    with patch(
        "app.routers.search.aql_service.search_serps_basic", new=async_return([1, 2])
    ):
        r = client.get("/search/basic?query=test&size=2")
        assert r.status_code == 200
        assert r.json() == {"count": 2, "results": [1, 2]}


def test_search_basic_invalid_size(client):
    r = client.get("/search/basic?query=test&size=0")
    assert r.status_code == 400


def test_search_providers_success(client):
    with patch(
        "app.routers.search.aql_service.search_providers", new=async_return(["a"])
    ):
        r = client.get("/search/providers?name=test&size=1")
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": ["a"]}


def test_search_advanced_success(client):
    with patch(
        "app.routers.search.aql_service.search_serps_advanced", new=async_return(["ok"])
    ):
        r = client.get("/search/advanced?query=x&size=1")
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": ["ok"]}


def test_autocomplete_success(client):
    with patch(
        "app.routers.search.aql_service.autocomplete_providers", new=async_return(["p"])
    ):
        r = client.get("/autocomplete/providers?q=te&size=1")
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": ["p"]}


def test_autocomplete_invalid_size(client):
    r = client.get("/autocomplete/providers?q=te&size=0")
    assert r.status_code == 400


def test_search_by_year_success(client):
    with patch("app.routers.search.aql_service.search_by_year", new=async_return([10])):
        r = client.get("/search/by-year?query=t&year=2020&size=1")
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": [10]}


# -------------------------------------------------------------------
# Tests for get serp by id
# -------------------------------------------------------------------


def test_get_serp_by_id_success(client):
    """Test successful retrieval of SERP by ID"""
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
        "app.routers.search.aql_service.get_serp_by_id", new=async_return(mock_serp)
    ):
        r = client.get("serp/test-uuid-1234")
        assert r.status_code == 200
        assert r.json() == mock_serp


def test_get_serp_by_id_not_found(client):
    """Test SERP not found returns 404"""
    with patch("app.routers.search.aql_service.get_serp_by_id", new=async_return(None)):
        r = client.get("serp/nonexistent-id")
        assert r.status_code == 404
        assert "No results found" in r.json()["detail"]


def test_get_serp_by_id_invalid_uuid_format(client):
    """Test with malformed UUID"""
    with patch("app.routers.search.aql_service.get_serp_by_id", new=async_return(None)):
        r = client.get("serp/not-a-valid-uuid")
        assert r.status_code == 404


def test_get_serp_by_id_elasticsearch_error(client):
    """Test Elasticsearch connection error handling"""

    async def raise_connection_error():
        raise ConnectionError(message="Connection failed", meta=None)

    with patch(
        "app.routers.search.aql_service.get_serp_by_id",
        side_effect=raise_connection_error,
    ):
        r = client.get("serp/test-uuid-1234")
        assert r.status_code == 500


# -------------------------------------------------------------------
# Tests for get serp by id
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# Tests for get original url
# -------------------------------------------------------------------


def test_get_original_url_success(client):
    """Test successful retrieval of original URL"""

    expected_response = {
        "serp_id": "test-uuid-1234",
        "original_url": "https://google.com/search?q=test&utm_source=tracking",
    }

    with patch(
        "app.routers.search.aql_service.get_serp_original_url",
        new=async_return(expected_response),
    ):
        r = client.get("/serp/test-uuid-1234/original-url")
        assert r.status_code == 200
        assert r.json() == expected_response
        assert "original_url" in r.json()


def test_get_original_url_with_special_chars(client):
    """Test URL with special characters (encoded)"""
    mock_response = {
        "serp_id": "test-id",
        "original_url": "https://google.com/search?q=%E3%83%86%E3%82%B9%E3%83%88",
    }

    with patch(
        "app.routers.search.aql_service.get_serp_original_url",
        new=async_return(mock_response),
    ):
        r = client.get("/serp/test-id/original-url")
        assert r.status_code == 200
        assert "%E3%83%86" in r.json()["original_url"]


def test_get_original_url_id_not_found(client):
    """Test SERP not found returns 404"""
    with patch("app.routers.search.aql_service.get_serp_by_id", new=async_return(None)):
        r = client.get("/serp/nonexistent-id/original-url")
        assert r.status_code == 404
        assert "No results found" in r.json()["detail"]


def test_get_original_url_id_invalid_uuid_format(client):
    """Test with malformed UUID"""
    with patch("app.routers.search.aql_service.get_serp_by_id", new=async_return(None)):
        r = client.get("/serp/not-a-valid-uuid/original-url")
        assert r.status_code == 404


def test_get_original_url_elasticsearch_error(client):
    """Test Elasticsearch error handling"""

    async def raise_error():
        raise ConnectionError(message="ES down", meta=None)

    with patch(
        "app.routers.search.aql_service.get_serp_original_url", side_effect=raise_error
    ):
        r = client.get("/serp/test-id/original-url")
        assert r.status_code == 500


# -------------------------------------------------------------------
# Tests for get original url
# -------------------------------------------------------------------


# --------------------- Additional tests for complete Coverage ---------------------


# 1. Invalid size for remaining endpoints
def test_search_providers_invalid_size(client):
    r = client.get("/search/providers?name=test&size=0")
    assert r.status_code == 400


def test_search_advanced_invalid_size(client):
    r = client.get("/search/advanced?query=x&size=0")
    assert r.status_code == 400


def test_autocomplete_by_providers_invalid_size(client):
    r = client.get("/autocomplete/providers?q=te&size=0")
    assert r.status_code == 400


def test_search_by_year_invalid_size(client):
    r = client.get("/search/by-year?query=x&year=2020&size=0")
    assert r.status_code == 400


# 2. Advanced search with filters
def test_search_advanced_with_filters(client):
    with patch(
        "app.routers.search.aql_service.search_serps_advanced",
        new=async_return(["filtered"]),
    ):
        r = client.get(
            "/search/advanced?query=x&provider_id=123&year=2021&status_code=200&size=1"
        )
        assert r.status_code == 200
        assert r.json() == {"count": 1, "results": ["filtered"]}


# 3. search_by_year returns empty -> triggers 404
def test_search_by_year_no_results(client):
    with patch("app.routers.search.aql_service.search_by_year", new=async_return([])):
        r = client.get("/search/by-year?query=x&year=2020&size=1")
        assert r.status_code == 404
