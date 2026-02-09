"""Test archives endpoint edge cases"""

from unittest.mock import AsyncMock, patch


def test_list_archives_invalid_size_parameter(client):
    """Test that invalid size parameter returns 422 error"""
    # Size too small
    response = client.get("/api/archives?size=0")
    assert response.status_code == 422
    assert "Invalid size parameter" in response.json()["detail"]

    # Size too large
    response = client.get("/api/archives?size=1001")
    assert response.status_code == 422
    assert "Invalid size parameter" in response.json()["detail"]


def test_list_archives_with_size_alias(client):
    """Test that size parameter works as alias for limit"""
    mock_result = {
        "total": 5,
        "archives": [
            {"id": "1", "name": "Archive 1"},
            {"id": "2", "name": "Archive 2"},
        ],
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.list_all_archives",
        new=AsyncMock(return_value=mock_result),
    ):
        response = client.get("/api/archives?size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["archives"]) == 2
