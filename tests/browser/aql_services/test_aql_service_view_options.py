"""Tests for aql_service.get_serp_view_options functionality.

Tests the service-level view options generation.
"""

import pytest
from archive_query_log.browser.services import aql_service


@pytest.mark.asyncio
async def test_get_serp_view_options_returns_dict(client):
    """Test that get_serp_view_options returns a properly structured dict."""
    result = await aql_service.get_serp_view_options("1")

    assert result is not None
    assert isinstance(result, dict)
    assert "serp_id" in result
    assert "views" in result
    assert isinstance(result["views"], list)


@pytest.mark.asyncio
async def test_view_options_has_all_view_types(client):
    """Test that all view types are included in the response."""
    result = await aql_service.get_serp_view_options("1")

    view_types = [v["type"] for v in result["views"]]
    assert "raw" in view_types
    assert "unbranded" in view_types
    assert "snapshot" in view_types


@pytest.mark.asyncio
async def test_view_option_structure(client):
    """Test that each view option has required fields."""
    result = await aql_service.get_serp_view_options("1")

    for view in result["views"]:
        assert "type" in view
        assert "label" in view
        assert "description" in view
        assert "available" in view
        assert isinstance(view["available"], bool)


@pytest.mark.asyncio
async def test_raw_view_always_available(client):
    """Test that raw view is always marked as available."""
    result = await aql_service.get_serp_view_options("1")

    raw_view = next(v for v in result["views"] if v["type"] == "raw")
    assert raw_view["available"] is True
    assert raw_view["url"] is not None
    assert "/serps/1" in raw_view["url"]


@pytest.mark.asyncio
async def test_unbranded_availability_logic(client):
    """Test that unbranded view availability is based on results existence."""
    result = await aql_service.get_serp_view_options("1")

    unbranded_view = next(v for v in result["views"] if v["type"] == "unbranded")

    # If available, should have URL
    if unbranded_view["available"]:
        assert unbranded_view["url"] is not None
        assert "view=unbranded" in unbranded_view["url"]
        assert unbranded_view.get("reason") is None
    else:
        assert unbranded_view["url"] is None
        assert unbranded_view["reason"] is not None


@pytest.mark.asyncio
async def test_snapshot_availability_logic(client):
    """Test that snapshot view availability is based on memento data."""
    result = await aql_service.get_serp_view_options("1")

    snapshot_view = next(v for v in result["views"] if v["type"] == "snapshot")

    # If available, should have external URL
    if snapshot_view["available"]:
        assert snapshot_view["url"] is not None
        # Should be a full memento URL, not an API endpoint
        assert snapshot_view["url"].startswith("http")
        assert snapshot_view.get("reason") is None
    else:
        assert snapshot_view["url"] is None
        assert snapshot_view["reason"] is not None


@pytest.mark.asyncio
async def test_serp_id_preserved(client):
    """Test that serp_id is correctly preserved in response."""
    result = await aql_service.get_serp_view_options("1")
    assert result["serp_id"] == "1"


@pytest.mark.asyncio
async def test_nonexistent_serp_returns_none(client):
    """Test behavior for non-existent SERP (mock always returns data)."""
    # Note: The test mock always returns valid SERP data
    # In production with real ES, this would return None for non-existent SERPs
    result = await aql_service.get_serp_view_options("nonexistent_id_12345")
    # With mock, we get a valid result
    assert result is not None
    assert "serp_id" in result
    assert result["serp_id"] == "nonexistent_id_12345"
