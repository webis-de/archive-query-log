"""Test validation errors in unified search endpoint"""

from unittest.mock import AsyncMock, patch


def test_unified_search_invalid_fuzziness(client):
    """Test that invalid fuzziness parameter returns 400 error"""
    response = client.get("/api/serps?query=test&fuzzy=true&fuzziness=5")
    assert response.status_code == 400
    data = response.json()
    assert "fuzziness must be one of" in data["detail"]


def test_unified_search_invalid_include_field(client):
    """Test that invalid include field returns 400 error"""
    mock_serp = {"_id": "test-id", "_source": {}}

    with patch(
        "archive_query_log.browser.routers.search.aql_service.get_serp_by_id",
        new=AsyncMock(return_value=mock_serp),
    ):
        response = client.get("/api/serps/test-id?include=invalid_field")
        assert response.status_code == 400
        data = response.json()
        assert "Invalid include fields" in data["detail"]
        assert "invalid_field" in data["detail"]


def test_safe_search_paginated_bad_request(client):
    """Test safe_search_paginated handles BadRequestError"""
    from elasticsearch import BadRequestError

    with patch(
        "archive_query_log.browser.routers.search.aql_service.list_all_archives",
        side_effect=BadRequestError("Bad request", {}, {}),
    ):
        response = client.get("/api/archives")
        assert response.status_code == 400
        assert "Invalid request to Elasticsearch" in response.json()["detail"]


def test_safe_search_paginated_connection_error(client):
    """Test safe_search_paginated handles ConnectionError"""
    from elasticsearch import ConnectionError as ESConnectionError

    with patch(
        "archive_query_log.browser.routers.search.aql_service.list_all_archives",
        side_effect=ESConnectionError("Connection failed", []),
    ):
        response = client.get("/api/archives")
        assert response.status_code == 503
        assert "Elasticsearch connection failed" in response.json()["detail"]


def test_safe_search_paginated_api_error(client):
    """Test safe_search_paginated handles ApiError"""
    from elasticsearch import ApiError

    with patch(
        "archive_query_log.browser.routers.search.aql_service.list_all_archives",
        side_effect=ApiError("API error", {}, {}),
    ):
        response = client.get("/api/archives")
        assert response.status_code == 503
        assert "Elasticsearch transport error" in response.json()["detail"]
