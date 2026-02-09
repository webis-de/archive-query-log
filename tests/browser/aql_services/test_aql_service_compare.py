import pytest
from unittest.mock import patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# compare_serps Tests
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_compare_serps_basic():
    """Test basic comparison of 2 SERPs"""
    with patch("archive_query_log.browser.services.aql_service.get_serp_by_id") as mock_get:
        # Mock two different SERPs
        mock_get.side_effect = [
            {
                "_id": "serp1",
                "_source": {
                    "url_query": "test query",
                    "provider": {"id": "google", "name": "Google"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": "https://example.com/1", "title": "Result 1"},
                        {"url": "https://example.com/2", "title": "Result 2"},
                    ],
                },
            },
            {
                "_id": "serp2",
                "_source": {
                    "url_query": "test query",
                    "provider": {"id": "bing", "name": "Bing"},
                    "capture": {
                        "timestamp": "2021-01-02T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": "https://example.com/2", "title": "Result 2"},
                        {"url": "https://example.com/3", "title": "Result 3"},
                    ],
                },
            },
        ]

        result = await aql.compare_serps(["serp1", "serp2"])

        # Check structure
        assert result is not None
        assert "comparison_summary" in result
        assert "serps_metadata" in result
        assert "url_comparison" in result
        assert "ranking_comparison" in result
        assert "similarity_metrics" in result

        # Check summary
        summary = result["comparison_summary"]
        assert summary["serp_count"] == 2
        assert summary["serp_ids"] == ["serp1", "serp2"]
        assert summary["total_unique_urls"] == 3
        assert summary["common_urls_count"] == 1

        # Check metadata
        assert len(result["serps_metadata"]) == 2
        assert result["serps_metadata"][0]["serp_id"] == "serp1"
        assert result["serps_metadata"][0]["provider_id"] == "google"


@pytest.mark.asyncio
async def test_compare_serps_multiple():
    """Test comparison of 3 SERPs"""
    with patch("archive_query_log.browser.services.aql_service.get_serp_by_id") as mock_get:
        # Mock three SERPs
        mock_get.side_effect = [
            {
                "_id": f"serp{i}",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "google", "name": "Google"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": f"https://example.com/{j}", "title": f"Result {j}"}
                        for j in range(i, i + 2)
                    ],
                },
            }
            for i in range(1, 4)
        ]

        result = await aql.compare_serps(["serp1", "serp2", "serp3"])

        assert result is not None
        assert result["comparison_summary"]["serp_count"] == 3
        assert len(result["serps_metadata"]) == 3
        assert (
            len(result["similarity_metrics"]["pairwise_jaccard"]) == 3
        )  # (3 choose 2)
        assert len(result["similarity_metrics"]["pairwise_spearman"]) == 3


@pytest.mark.asyncio
async def test_compare_serps_common_urls():
    """Test that common URLs are correctly identified"""
    with patch("archive_query_log.browser.services.aql_service.get_serp_by_id") as mock_get:
        # Both SERPs have the same URLs
        mock_get.side_effect = [
            {
                "_id": "serp1",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "google", "name": "Google"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": "https://example.com/1", "title": "Result 1"},
                        {"url": "https://example.com/2", "title": "Result 2"},
                    ],
                },
            },
            {
                "_id": "serp2",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "bing", "name": "Bing"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": "https://example.com/1", "title": "Result 1"},
                        {"url": "https://example.com/2", "title": "Result 2"},
                    ],
                },
            },
        ]

        result = await aql.compare_serps(["serp1", "serp2"])

        # All URLs are common
        assert result["comparison_summary"]["common_urls_count"] == 2
        assert result["comparison_summary"]["total_unique_urls"] == 2
        assert len(result["url_comparison"]["common_urls"]) == 2

        # Jaccard similarity should be 1.0 (identical sets)
        jaccard = result["similarity_metrics"]["pairwise_jaccard"][0][
            "jaccard_similarity"
        ]
        assert jaccard == 1.0


@pytest.mark.asyncio
async def test_compare_serps_ranking_difference():
    """Test that ranking differences are calculated correctly"""
    with patch("archive_query_log.browser.services.aql_service.get_serp_by_id") as mock_get:
        # Same URLs but different rankings
        mock_get.side_effect = [
            {
                "_id": "serp1",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "google", "name": "Google"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": "https://example.com/1", "title": "Result 1"},
                        {"url": "https://example.com/2", "title": "Result 2"},
                        {"url": "https://example.com/3", "title": "Result 3"},
                    ],
                },
            },
            {
                "_id": "serp2",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "bing", "name": "Bing"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {"url": "https://example.com/3", "title": "Result 3"},
                        {"url": "https://example.com/2", "title": "Result 2"},
                        {"url": "https://example.com/1", "title": "Result 1"},
                    ],
                },
            },
        ]

        result = await aql.compare_serps(["serp1", "serp2"])

        # Check ranking comparison
        ranking_comp = result["ranking_comparison"]
        assert len(ranking_comp) == 3  # All 3 URLs are common

        # URL 1 and URL 3 should have position difference of 2
        url1_entry = next(
            r for r in ranking_comp if r["url"] == "https://example.com/1"
        )
        assert url1_entry["positions"]["serp1"] == 1
        assert url1_entry["positions"]["serp2"] == 3
        assert url1_entry["position_difference"] == 2

        url3_entry = next(
            r for r in ranking_comp if r["url"] == "https://example.com/3"
        )
        assert url3_entry["positions"]["serp1"] == 3
        assert url3_entry["positions"]["serp2"] == 1
        assert url3_entry["position_difference"] == 2


@pytest.mark.asyncio
async def test_compare_serps_invalid_id():
    """Test that None is returned when a SERP ID is not found"""
    with patch("archive_query_log.browser.services.aql_service.get_serp_by_id") as mock_get:
        # First SERP exists, second doesn't
        mock_get.side_effect = [
            {
                "_id": "serp1",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "google", "name": "Google"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [],
                },
            },
            None,  # Second SERP not found
        ]

        result = await aql.compare_serps(["serp1", "invalid_serp"])
        assert result is None


@pytest.mark.asyncio
async def test_compare_serps_empty_list():
    """Test that None is returned for empty or single ID list"""
    result = await aql.compare_serps([])
    assert result is None

    result = await aql.compare_serps(["serp1"])
    assert result is None


@pytest.mark.asyncio
async def test_compare_serps_no_results():
    """Test comparison when SERPs have no results"""
    with patch("archive_query_log.browser.services.aql_service.get_serp_by_id") as mock_get:
        mock_get.side_effect = [
            {
                "_id": "serp1",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "google", "name": "Google"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                },
            },
            {
                "_id": "serp2",
                "_source": {
                    "url_query": "test",
                    "provider": {"id": "bing", "name": "Bing"},
                    "capture": {
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                },
            },
        ]

        result = await aql.compare_serps(["serp1", "serp2"])

        # Should still return valid structure
        assert result is not None
        assert result["comparison_summary"]["common_urls_count"] == 0
        assert result["comparison_summary"]["total_unique_urls"] == 0
        assert len(result["ranking_comparison"]) == 0
