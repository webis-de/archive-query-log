"""Test SERP view modes (snapshot view specifically)"""

from unittest.mock import AsyncMock, patch


def test_get_serp_snapshot_view_no_memento_url(client):
    """Test snapshot view when memento URL is not available"""
    mock_memento_data = {"serp_id": "test-id"}  # No memento_url field

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_memento_url",
        new=AsyncMock(return_value=mock_memento_data),
    ):
        response = client.get("/api/serps/test-id?view=snapshot")
        assert response.status_code == 404
        data = response.json()
        assert "Memento URL not available" in data["detail"]


def test_get_serp_snapshot_view_with_memento_url(client):
    """Test snapshot view redirects to memento URL"""
    mock_memento_data = {
        "serp_id": "test-id",
        "memento_url": "https://web.archive.org/web/2023010100000/https://google.com/search?q=test",
    }

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_memento_url",
        new=AsyncMock(return_value=mock_memento_data),
    ):
        response = client.get(
            "/api/serps/test-id?view=snapshot", follow_redirects=False
        )
        assert response.status_code == 307  # Redirect
        assert "web.archive.org" in response.headers["location"]
