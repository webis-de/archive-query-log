import pytest
from unittest.mock import AsyncMock, patch
import app.services.aql_service as aql


# ---------------------------------------------------------
# 1. search_basic
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_basic():
    results = await aql.search_basic("test", size=5)
    # Since the global mock returns fixed hits, we only check for structure.
    assert isinstance(results, list)
    assert "url_query" in results[0]["_source"]


# ---------------------------------------------------------
# 2. search_providers
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_providers():
    results = await aql.search_providers("abc", size=3)
    assert isinstance(results, list)
    # Provider-Feld must be present in results
    assert (
        results[0]["_source"]["name"] == "Google"
        or results[0]["_source"]["name"] == "Bing"
    )


# ---------------------------------------------------------
# 3. search_advanced – all filters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_advanced_all_filters():
    results = await aql.search_advanced(
        query="foo",
        provider_id="p123",
        year=2020,
        status_code=404,
        size=7,
    )
    assert isinstance(results, list)


# ---------------------------------------------------------
# 4. search_advanced – minimal filters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_advanced_minimal():
    results = await aql.search_advanced(query="x")
    assert isinstance(results, list)


# ---------------------------------------------------------
# 5. search_by_year – delegating to search_advanced
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_by_year_calls_advanced():
    with patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=[1, 2]),
    ) as mock_adv:
        results = await aql.search_by_year("foo", 2022, size=5)
        mock_adv.assert_awaited_once_with(query="foo", year=2022, size=5)
        assert results == [1, 2]
