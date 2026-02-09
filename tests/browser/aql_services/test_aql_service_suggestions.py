"""Tests for search_basic with fuzzy suggestions (did_you_mean)"""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_search_basic_with_suggestions():
    """Test that search_basic returns suggestions when fuzzy=True"""
    from archive_query_log.browser.services import aql_service

    mock_response = {
        "hits": {
            "hits": [{"_id": "1", "_source": {"url_query": "climate"}}],
            "total": {"value": 1},
        },
        "suggest": {
            "did_you_mean": [
                {
                    "text": "climat",
                    "options": [
                        {"text": "climate", "score": 0.85, "freq": 100},
                        {"text": "climat", "score": 0.5, "freq": 10},  # Same as input
                    ],
                }
            ]
        },
    }

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.search.return_value = mock_response
        mock_get_client.return_value = mock_es

        result = await aql_service.search_basic(
            query="climat", size=10, fuzzy=True, fuzziness="AUTO"
        )

        assert "suggestions" in result
        assert len(result["suggestions"]) == 1
        # Only "climate" should be in suggestions (not "climat" since it's same as input)
        assert result["suggestions"][0]["text"] == "climate"
        assert result["suggestions"][0]["score"] == 0.85
        assert result["suggestions"][0]["freq"] == 100


@pytest.mark.asyncio
async def test_search_basic_no_suggestions_when_empty():
    """Test that no suggestions are returned when options list is empty"""
    from archive_query_log.browser.services import aql_service

    mock_response = {
        "hits": {
            "hits": [{"_id": "1", "_source": {"url_query": "test"}}],
            "total": {"value": 1},
        },
        "suggest": {"did_you_mean": [{"text": "test", "options": []}]},
    }

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.search.return_value = mock_response
        mock_get_client.return_value = mock_es

        result = await aql_service.search_basic(
            query="test", size=10, fuzzy=True, fuzziness="1"
        )

        assert "suggestions" not in result


@pytest.mark.asyncio
async def test_search_basic_with_expand_synonyms():
    """Test search with expand_synonyms=True"""
    from archive_query_log.browser.services import aql_service

    mock_response = {
        "hits": {
            "hits": [{"_id": "1", "_source": {"url_query": "climate"}}],
            "total": 10,  # Old format (integer)
        },
        "suggest": {"did_you_mean": []},
    }

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.search.return_value = mock_response
        mock_get_client.return_value = mock_es

        result = await aql_service.search_basic(
            query="climate", size=10, expand_synonyms=True
        )

        # Should handle old integer format for total
        assert result["total"] == 10
        assert len(result["hits"]) == 1


@pytest.mark.asyncio
async def test_search_basic_total_as_integer():
    """Test that search_basic handles total as integer (old ES format)"""
    from archive_query_log.browser.services import aql_service

    mock_response = {
        "hits": {
            "hits": [{"_id": "1"}],
            "total": 42,  # Old format: integer instead of dict
        },
    }

    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.search.return_value = mock_response
        mock_get_client.return_value = mock_es

        result = await aql_service.search_basic(query="test", size=10)

        assert result["total"] == 42
