import pytest
from unittest.mock import patch, AsyncMock

import app.services.aql_service as aql


# Utility: fake ES response
def es_response(hits):
    return {"hits": {"hits": hits}}


# Utility: create mocked ES client
def mock_es(return_value):
    client = AsyncMock()
    client.search.return_value = return_value
    return client


# ---------------------------------------------------------
# 1. search_serps_basic
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_serps_basic():
    fake_hits = [{"a": 1}]

    with patch(
        "app.services.aql_service.get_es_client",
        return_value=mock_es(es_response(fake_hits)),
    ) as mock_get:
        results = await aql.search_serps_basic("test", size=5)

        mock_get.assert_called_once()
        assert results == fake_hits


# ---------------------------------------------------------
# 2. search_providers
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_providers():
    fake_hits = [{"provider": "x"}]

    with patch(
        "app.services.aql_service.get_es_client",
        return_value=mock_es(es_response(fake_hits)),
    ) as mock_get:
        results = await aql.search_providers("abc", size=3)

        mock_get.assert_called_once()
        assert results == fake_hits


# ---------------------------------------------------------
# 3. search_serps_advanced – test full filter combination
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_serps_advanced_all_filters():
    fake_hits = [{"hit": 1}]

    mock_client = mock_es(es_response(fake_hits))

    with patch("app.services.aql_service.get_es_client", return_value=mock_client):
        results = await aql.search_serps_advanced(
            query="foo", provider_id="p123", year=2020, status_code=404, size=7
        )

        # Verify ES client was called with correct query body
        mock_client.search.assert_awaited_once()
        args, kwargs = mock_client.search.call_args

        assert kwargs["index"] == "aql_serps"

        body = kwargs["body"]

        # Must match structure
        assert body["size"] == 7
        assert {"match": {"url_query": "foo"}} in body["query"]["bool"]["must"]

        filters = body["query"]["bool"]["filter"]
        assert {"term": {"provider.id": "p123"}} in filters
        assert {"term": {"capture.status_code": 404}} in filters

        # Range filter for year
        assert any("range" in f for f in filters)

        assert results == fake_hits


# ---------------------------------------------------------
# 4. search_serps_advanced – test minimal filters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_serps_advanced_minimal():
    fake_hits = [{"hit": 99}]
    mock_client = mock_es(es_response(fake_hits))

    with patch("app.services.aql_service.get_es_client", return_value=mock_client):
        results = await aql.search_serps_advanced(query="x")

        mock_client.search.assert_awaited_once()
        body = mock_client.search.call_args.kwargs["body"]

        # no filters except must
        assert body["query"]["bool"]["filter"] == []
        assert results == fake_hits


# ---------------------------------------------------------
# 5. autocomplete_providers
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_autocomplete_providers():
    fake_hits = [{"_source": {"name": "Alpha"}}, {"_source": {"name": "Beta"}}]
    mock_client = mock_es(es_response(fake_hits))

    with patch("app.services.aql_service.get_es_client", return_value=mock_client):
        results = await aql.autocomplete_providers("a", size=2)

        mock_client.search.assert_awaited_once()
        assert results == ["Alpha", "Beta"]


# ---------------------------------------------------------
# 6. search_by_year – test delegating
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_by_year_calls_advanced():
    with patch(
        "app.services.aql_service.search_serps_advanced",
        new=AsyncMock(return_value=[1, 2]),
    ) as mock_adv:
        results = await aql.search_by_year("foo", 2022, size=5)

        mock_adv.assert_awaited_once_with(query="foo", year=2022, size=5)
        assert results == [1, 2]


# ---------------------------------------------------------
# 7. get_serp_by_id
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_by_id_success():
    """Test get_serp_by_id with real Elasticsearch mock"""
    mock_es_response = {
        "_id": "test-id",
        "_source": {"url_query": "test"},
        "found": True,
    }

    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.return_value = mock_es_response
        mock_get_client.return_value = mock_es

        result = await aql.get_serp_by_id("test-id")

        assert result == mock_es_response
        mock_es.get.assert_called_once_with(index="aql_serps", id="test-id")


@pytest.mark.asyncio
async def test_get_serp_by_id_exception():
    """Test get_serp_by_id when Elasticsearch raises exception"""
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.side_effect = Exception("ES error")
        mock_get_client.return_value = mock_es

        result = await aql.get_serp_by_id("test-id")

        assert result is None


# ---------------------------------------------------------
# 8. get_serp_original_url
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_original_url_success():
    """Test get_serp_original_url returns correct URL"""
    mock_serp = {
        "_id": "test-uuid-1234",
        "_source": {
            "capture": {"url": "https://google.com/search?q=test&utm_source=tracking"}
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_original_url("test-uuid-1234")

        assert result == {
            "serp_id": "test-uuid-1234",
            "original_url": "https://google.com/search?q=test&utm_source=tracking",
        }


@pytest.mark.asyncio
async def test_get_serp_original_url_with_tracking_removal():
    """Test get_serp_original_url with tracking parameter removal"""
    mock_serp = {
        "_id": "test-id",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=test&utm_source=email&fbclid=123"
            }
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_original_url("test-id", remove_tracking=True)

        assert result["serp_id"] == "test-id"
        assert (
            result["original_url"]
            == "https://google.com/search?q=test&utm_source=email&fbclid=123"
        )
        assert "url_without_tracking" in result
        assert "utm_source" not in result["url_without_tracking"]
        assert "fbclid" not in result["url_without_tracking"]
        assert "q=test" in result["url_without_tracking"]


@pytest.mark.asyncio
async def test_get_serp_original_url_serp_not_found():
    """Test get_serp_original_url when SERP doesn't exist"""
    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_original_url("nonexistent-id")

        assert result is None


# ---------------------------------------------------------
# 9. get_serp_memento_url
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_memento_url_success():
    """Test get_serp_memento_url constructs correct Memento URL"""
    mock_serp = {
        "_id": "test-uuid-5678",
        "_source": {
            "archive": {"memento_api_url": "https://web.archive.org/web"},
            "capture": {
                "url": "https://google.com/search?q=python",
                "timestamp": "2021-06-15T14:30:45+00:00",
            },
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_memento_url("test-uuid-5678")

        assert result["serp_id"] == "test-uuid-5678"
        assert (
            result["memento_url"]
            == "https://web.archive.org/web/20210615143045/https://google.com/search?q=python"
        )


@pytest.mark.asyncio
async def test_get_serp_memento_url_different_timestamp():
    """Test memento URL with different timestamp format"""
    mock_serp = {
        "_id": "test-id-999",
        "_source": {
            "archive": {"memento_api_url": "https://archive.example.org"},
            "capture": {
                "url": "https://bing.com/search?q=test",
                "timestamp": "2020-01-01T00:00:00+00:00",
            },
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_memento_url("test-id-999")

        assert result["serp_id"] == "test-id-999"
        assert (
            result["memento_url"]
            == "https://archive.example.org/20200101000000/https://bing.com/search?q=test"
        )


@pytest.mark.asyncio
async def test_get_serp_memento_url_serp_not_found():
    """Test get_serp_memento_url when SERP doesn't exist"""
    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_memento_url("nonexistent-id")

        assert result is None
