"""
Tests for exception handlers and error scenarios.
Covers Elasticsearch errors, fallback mechanisms, and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, patch
from archive_query_log.browser.services import aql_service


class TestExceptionHandling:
    """Test exception handling in aql_service functions"""

    @pytest.mark.asyncio
    async def test_get_archive_metadata_not_found(self):
        """Test get_archive_metadata when archive doesn't exist"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.return_value = {
                "hits": {"total": 0, "hits": []},
            }
            mock_get_es.return_value = mock_es

            result = await aql_service.get_archive_metadata("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_list_all_archives_with_es_error(self):
        """Test list_all_archives when Elasticsearch throws error"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            result = await aql_service.list_all_archives()

            # Should return empty list gracefully
            assert result["total"] == 0
            assert result["archives"] == []

    @pytest.mark.asyncio
    async def test_compare_serps_with_less_than_two_serps(self):
        """Test compare_serps with less than 2 SERPs"""
        result = await aql_service.compare_serps(["id1"])  # Only one SERP

        assert result is None

    @pytest.mark.asyncio
    async def test_get_serp_by_id_not_found(self):
        """Test get_serp_by_id when SERP doesn't exist"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.get.side_effect = Exception("Not found")
            mock_get_es.return_value = mock_es

            result = await aql_service.get_serp_by_id("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_serp_direct_links_no_results_field(self):
        """Test get_serp_direct_links when SERP has no results field"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.get.return_value = {
                "_id": "test-id",
                "_source": {
                    "url_query": "test",
                    # No 'results' field
                },
            }
            mock_get_es.return_value = mock_es

            result = await aql_service.get_serp_direct_links("test-id")

            assert result["direct_links_count"] == 0
            assert result["direct_links"] == []

    @pytest.mark.asyncio
    async def test_search_suggestions_with_empty_results(self):
        """Test search_suggestions when no suggestions found"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.return_value = {"hits": {"hits": []}}  # No suggestions found
            mock_get_es.return_value = mock_es

            result = await aql_service.search_suggestions("nonexistent")

            assert result["prefix"] == "nonexistent"
            assert result["suggestions"] == []

    @pytest.mark.asyncio
    async def test_serps_timeline_with_es_error(self):
        """Test serps_timeline when Elasticsearch fails"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            result = await aql_service.serps_timeline("test")

            # Should return empty timeline
            assert result["total_hits"] == 0
            assert result["date_histogram"] == []

    @pytest.mark.asyncio
    async def test_preview_search_with_aggregation_error(self):
        """Test preview_search when aggregation fails"""
        with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("Aggregation error")
            mock_get_es.return_value = mock_es

            result = await aql_service.preview_search("test")

            # Should return empty structure on error
            assert result["query"] == "test"
            assert result["total_hits"] == 0
            assert result["top_queries"] == []
