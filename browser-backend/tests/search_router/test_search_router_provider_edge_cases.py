"""Test edge cases for provider endpoints"""

from unittest.mock import AsyncMock, patch


def test_get_all_providers_negative_size(client):
    """Test that negative size parameter returns 400 error"""
    response = client.get("/api/providers?size=-1")
    assert response.status_code == 400
    data = response.json()
    assert "Size must be 0 (for all) or a positive integer" in data["detail"]


def test_get_all_providers_with_zero_size(client):
    """Test that size=0 returns all providers"""
    mock_providers = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

    with patch(
        "app.routers.search.aql_service.get_all_providers",
        new=AsyncMock(return_value=mock_providers),
    ):
        response = client.get("/api/providers?size=0")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["results"]) == 3
