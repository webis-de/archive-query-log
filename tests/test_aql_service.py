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
