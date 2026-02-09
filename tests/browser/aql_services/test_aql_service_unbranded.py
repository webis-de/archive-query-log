"""Tests for aql_service.get_serp_unbranded functionality.

Tests the service-level unbranded SERP view normalization.
"""

import pytest
from archive_query_log.browser.services import aql_service


@pytest.mark.asyncio
async def test_get_serp_unbranded_returns_dict(client):
    """Test that get_serp_unbranded returns a properly structured dict."""
    result = await aql_service.get_serp_unbranded("1")

    assert result is not None
    assert isinstance(result, dict)
    assert "serp_id" in result
    assert "query" in result
    assert "results" in result
    assert "metadata" in result


@pytest.mark.asyncio
async def test_get_serp_unbranded_query_structure(client):
    """Test query structure in unbranded view."""
    result = await aql_service.get_serp_unbranded("1")

    query = result["query"]
    assert "raw" in query
    assert "parsed" in query


@pytest.mark.asyncio
async def test_get_serp_unbranded_results_normalized(client):
    """Test that results are normalized with position, url, title, snippet."""
    result = await aql_service.get_serp_unbranded("1")

    results = result["results"]
    assert len(results) > 0

    for idx, result_item in enumerate(results, 1):
        assert "position" in result_item
        assert "url" in result_item
        assert "title" in result_item
        assert "snippet" in result_item
        assert result_item["position"] == idx


@pytest.mark.asyncio
async def test_get_serp_unbranded_metadata_structure(client):
    """Test metadata includes timestamp, url, and status_code."""
    result = await aql_service.get_serp_unbranded("1")

    metadata = result["metadata"]
    assert "timestamp" in metadata
    assert "url" in metadata
    assert "status_code" in metadata


@pytest.mark.asyncio
async def test_get_serp_unbranded_serp_id_preserved(client):
    """Test that serp_id is correctly preserved in unbranded response."""
    result = await aql_service.get_serp_unbranded("1")
    assert result["serp_id"] == "1"
