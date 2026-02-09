import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock

from archive_query_log.browser.routers.search import safe_search
from elasticsearch import TransportError, RequestError


# ---------------------
# Helper: Mock async function returning value
# ---------------------
def async_return(value):
    mock = AsyncMock()
    mock.return_value = value
    return mock


# -------------------------------------------------------------------
# Tests for safe_search()
# -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_search_success():
    """Test that safe_search returns the result when coroutine succeeds"""
    coro = async_return([{"x": 1}])()
    result = await safe_search(coro)
    assert result == [{"x": 1}]


@pytest.mark.asyncio
async def test_safe_search_no_results():
    """Test that safe_search raises 404 if coroutine returns empty list"""
    coro = async_return([])()
    with pytest.raises(HTTPException) as exc:
        await safe_search(coro)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_safe_search_connection_error():
    """Test that safe_search raises 503 on Elasticsearch connection error"""

    async def boom():
        from elasticsearch import ConnectionError as ConnectionError

        raise ConnectionError()

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())
    assert exc.value.status_code == 503
    assert "connection" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_safe_search_transport_error():
    """Test that safe_search raises 503 on Elasticsearch transport error"""

    async def boom():
        raise TransportError()

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())
    assert exc.value.status_code == 503
    assert "transport" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_safe_search_request_error():
    """Test that safe_search raises 400 on Elasticsearch RequestError"""

    async def boom():
        raise RequestError()

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())
    assert exc.value.status_code == 400
    assert "Invalid request" in exc.value.detail


@pytest.mark.asyncio
async def test_safe_search_generic_error():
    """Test that safe_search raises 500 on generic exceptions"""

    async def boom():
        raise Exception()

    with pytest.raises(HTTPException) as exc:
        await safe_search(boom())
    assert exc.value.status_code == 500
