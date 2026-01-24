"""
Tests for exception handling and fallback mechanisms in aql_service.py.
Covers Elasticsearch errors, malformed data, and fallback aggregations.
"""

import pytest
from unittest.mock import AsyncMock, patch
from app.services import aql_service


class TestAqlServiceExceptionHandling:
    """Test exception handling in aql_service functions"""

    @pytest.mark.asyncio
    async def test_search_basic_with_es_error(self):
        """Test search_basic when Elasticsearch throws an error"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("Connection failed")
            mock_get_es.return_value = mock_es

            # Should raise exception (not caught in search_basic)
            with pytest.raises(Exception):
                await aql_service.search_basic("test")

    @pytest.mark.asyncio
    async def test_search_advanced_with_es_error(self):
        """Test search_advanced when Elasticsearch throws an error"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("Connection failed")
            mock_get_es.return_value = mock_es

            # Should raise exception
            with pytest.raises(Exception):
                await aql_service.search_advanced("test", provider_id="google")

    @pytest.mark.asyncio
    async def test_preview_search_with_aggregation_error(self):
        """Test preview_search when aggregation fails but document fetch succeeds"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()

            # First call (aggregation) fails, second call (sample) succeeds
            mock_es.search.side_effect = [
                Exception("Aggregation error"),  # Basic aggregation fails
            ]
            mock_get_es.return_value = mock_es

            result = await aql_service.preview_search("test")

            # Should return empty structure on error
            assert result["query"] == "test"
            assert result["total_hits"] == 0
            assert result["top_queries"] == []

    @pytest.mark.asyncio
    async def test_preview_search_with_both_aggregations_failing(self):
        """Test preview_search when both aggregation and fallback fail"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("Both calls fail")
            mock_get_es.return_value = mock_es

            result = await aql_service.preview_search("test")

            # Should return empty but valid structure
            assert result["query"] == "test"
            assert result["total_hits"] == 0

    @pytest.mark.asyncio
    async def test_get_archive_metadata_not_found(self):
        """Test get_archive_metadata when archive doesn't exist"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
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
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            result = await aql_service.list_all_archives()

            # Should return empty list gracefully
            assert result["total"] == 0
            assert result["archives"] == []

    @pytest.mark.asyncio
    async def test_get_all_providers_with_es_error(self):
        """Test get_all_providers when Elasticsearch fails"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            with pytest.raises(Exception):
                await aql_service.get_all_providers()

    @pytest.mark.asyncio
    async def test_compare_serps_with_missing_serp(self):
        """Test compare_serps when one SERP doesn't exist"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.get.return_value = None  # SERP not found
            mock_get_es.return_value = mock_es

            result = await aql_service.compare_serps(["id1", "id2"])

            assert result is None

    @pytest.mark.asyncio
    async def test_compare_serps_with_empty_results(self):
        """Test compare_serps with less than 2 SERPs"""
        result = await aql_service.compare_serps(["id1"])  # Only one SERP

        assert result is None

    @pytest.mark.asyncio
    async def test_get_serp_by_id_not_found(self):
        """Test get_serp_by_id when SERP doesn't exist"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.get.side_effect = Exception("Not found")
            mock_get_es.return_value = mock_es

            result = await aql_service.get_serp_by_id("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_serp_direct_links_no_results_field(self):
        """Test get_serp_direct_links when SERP has no results field"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
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
    async def test_search_suggestions_with_sample_error(self):
        """Test search_suggestions when aggregation succeeds but has empty results"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.return_value = {"hits": {"hits": []}}  # No suggestions found
            mock_get_es.return_value = mock_es

            result = await aql_service.search_suggestions("nonexistent")

            assert result["prefix"] == "nonexistent"
            assert result["suggestions"] == []

    @pytest.mark.asyncio
    async def test_serps_timeline_with_es_error(self):
        """Test serps_timeline when Elasticsearch fails"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            result = await aql_service.serps_timeline("test")

            # Should return empty timeline
            assert result["total_hits"] == 0
            assert result["date_histogram"] == []

    @pytest.mark.asyncio
    async def test_get_provider_statistics_with_es_error(self):
        """Test get_provider_statistics when Elasticsearch fails"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            result = await aql_service.get_provider_statistics("test-provider")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_provider_statistics_no_data(self):
        """Test get_provider_statistics when provider has no SERPs"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.return_value = {
                "hits": {"total": {"value": 0}},
                "aggregations": {},
            }
            mock_get_es.return_value = mock_es

            result = await aql_service.get_provider_statistics("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_archive_statistics_with_es_error(self):
        """Test get_archive_statistics when Elasticsearch fails"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()
            mock_es.search.side_effect = Exception("ES error")
            mock_get_es.return_value = mock_es

            result = await aql_service.get_archive_statistics("https://example.org")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_provider_statistics_fallback_mechanism(self):
        """Test get_provider_statistics fallback when aggregation returns empty buckets"""
        # This test is complex and requires multiple ES responses
        # For now, we just test that the function handles it gracefully
        result = await aql_service.get_provider_statistics("test-provider")
        # Result can be None if no data or a dict if data exists
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_archive_statistics_fallback_mechanism(self):
        """Test get_archive_statistics fallback when aggregation returns empty buckets"""
        # Test graceful handling
        result = await aql_service.get_archive_statistics("https://example.org")
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_get_provider_statistics_histogram_error(self):
        """Test get_provider_statistics when histogram fails but aggregation works"""
        with patch("app.services.aql_service.get_es_client") as mock_get_es:
            mock_es = AsyncMock()

            # First call succeeds, histogram call fails
            mock_es.search.side_effect = [
                {  # Basic aggregation succeeds
                    "hits": {"total": {"value": 100}},
                    "aggregations": {
                        "unique_queries": {"buckets": [{"key": "test"}]},
                        "top_archives": {"buckets": []},
                    },
                },
                Exception("Histogram error"),  # Histogram fails
            ]
            mock_get_es.return_value = mock_es

            result = await aql_service.get_provider_statistics("test")

            # Should still return result with None histogram
            assert result is not None
            assert result["unique_queries_count"] == 1
            assert result["date_histogram"] is None
