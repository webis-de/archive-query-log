"""Test router for suggestions in search results"""

from unittest.mock import AsyncMock, patch


def test_unified_search_with_suggestions(client):
    """Test that unified search endpoint includes did_you_mean suggestions"""
    mock_result = {
        "hits": [{"_id": "1", "_source": {"url_query": "climate"}}],
        "total": 100,
        "suggestions": [
            {"text": "climate change", "score": 0.9, "freq": 500},
            {"text": "climatic", "score": 0.7, "freq": 200},
        ],
    }

    with patch(
        "app.routers.search.aql_service.search_basic",
        new=AsyncMock(return_value=mock_result),
    ):
        response = client.get("/api/serps?query=climat&fuzzy=true")
        assert response.status_code == 200
        data = response.json()

        assert "did_you_mean" in data
        assert len(data["did_you_mean"]) == 2
        assert data["did_you_mean"][0]["text"] == "climate change"


def test_unified_search_without_suggestions(client):
    """Test that unified search works without suggestions"""
    mock_result = {
        "hits": [{"_id": "1"}],
        "total": 10,
        # No suggestions field
    }

    with patch(
        "app.routers.search.aql_service.search_basic",
        new=AsyncMock(return_value=mock_result),
    ):
        response = client.get("/api/serps?query=test")
        assert response.status_code == 200
        data = response.json()

        # Should not have did_you_mean when no suggestions
        assert "did_you_mean" not in data
