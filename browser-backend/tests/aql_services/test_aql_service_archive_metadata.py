"""Tests for archive metadata retrieval functions"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_get_archive_metadata_success():
    """Test retrieving archive metadata for a valid archive"""
    from archive_query_log.browser.services import aql_service

    archive_id = "https://web.archive.org/web"

    # Mock the Elasticsearch response
    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "hits": {"total": {"value": 100, "relation": "eq"}, "hits": []}
            }
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_archive_metadata(archive_id)

        assert result is not None
        assert result["id"] == archive_id
        assert result["name"] == "Internet Archive (Wayback Machine)"
        assert result["memento_api_url"] == archive_id
        assert result["cdx_api_url"] == "https://web.archive.org/cdx/search/csv"
        assert result["homepage"] == "https://web.archive.org"
        assert result["serp_count"] == 100


@pytest.mark.asyncio
async def test_get_archive_metadata_not_found():
    """Test retrieving metadata for non-existent archive"""
    from archive_query_log.browser.services import aql_service

    archive_id = "https://non.existent.archive/web"

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.get_archive_metadata(archive_id)

        assert result is None


@pytest.mark.asyncio
async def test_list_all_archives():
    """Test listing all available archives"""
    from archive_query_log.browser.services import aql_service

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={
                "aggregations": {
                    "unique_archives": {
                        "buckets": [
                            {"key": "https://web.archive.org/web", "doc_count": 100},
                            {"key": "https://archive.example.org", "doc_count": 50},
                        ]
                    }
                }
            }
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.list_all_archives(size=100)

        assert result["total"] == 2
        assert len(result["archives"]) == 2
        assert result["archives"][0]["id"] == "https://web.archive.org/web"
        assert result["archives"][0]["serp_count"] == 100
        assert result["archives"][1]["id"] == "https://archive.example.org"
        assert result["archives"][1]["serp_count"] == 50


@pytest.mark.asyncio
async def test_list_all_archives_empty():
    """Test listing archives when none exist"""
    from archive_query_log.browser.services import aql_service

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_client:
        mock_client = AsyncMock()
        mock_client.search = AsyncMock(
            return_value={"aggregations": {"unique_archives": {"buckets": []}}}
        )
        mock_es_client.return_value = mock_client

        result = await aql_service.list_all_archives()

        assert result["total"] == 0
        assert result["archives"] == []


def test_derive_archive_name():
    """Test archive name derivation"""
    from archive_query_log.browser.services.aql_service import _derive_archive_name

    # Test known archives
    assert (
        _derive_archive_name("https://web.archive.org/web")
        == "Internet Archive (Wayback Machine)"
    )
    assert (
        _derive_archive_name("https://web.archive.org")
        == "Internet Archive (Wayback Machine)"
    )

    # Test generic archive
    name = _derive_archive_name("https://archive.example.org")
    assert "Archive" in name or "Example" in name


def test_derive_cdx_url():
    """Test CDX URL derivation"""
    from archive_query_log.browser.services.aql_service import _derive_cdx_url

    # Test Internet Archive
    assert (
        _derive_cdx_url("https://web.archive.org/web")
        == "https://web.archive.org/cdx/search/csv"
    )

    # Test generic archive
    cdx_url = _derive_cdx_url("https://archive.example.org")
    assert cdx_url == "https://archive.example.org/cdx/search/csv"

    # Test None
    assert _derive_cdx_url(None) is None


def test_derive_homepage():
    """Test homepage derivation"""
    from archive_query_log.browser.services.aql_service import _derive_homepage

    # Test Internet Archive
    assert _derive_homepage("https://web.archive.org/web") == "https://web.archive.org"

    # Test generic archive
    homepage = _derive_homepage("https://archive.example.org/web")
    assert homepage == "https://archive.example.org"

    # Test None
    assert _derive_homepage(None) is None
