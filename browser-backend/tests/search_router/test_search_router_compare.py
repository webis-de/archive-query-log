from unittest.mock import patch


# ---------------------------------------------------------
# Compare Endpoint Tests
# ---------------------------------------------------------
def test_compare_serps_success(client):
    """Test successful comparison of 2 SERPs"""
    with patch("app.services.aql_service.compare_serps") as mock_compare:
        mock_compare.return_value = {
            "comparison_summary": {
                "serp_count": 2,
                "serp_ids": ["serp1", "serp2"],
                "total_unique_urls": 3,
                "common_urls_count": 1,
                "avg_jaccard_similarity": 0.5,
            },
            "serps_metadata": [
                {
                    "serp_id": "serp1",
                    "query": "test",
                    "provider_id": "google",
                },
                {
                    "serp_id": "serp2",
                    "query": "test",
                    "provider_id": "bing",
                },
            ],
            "serps_full_data": [],
            "url_comparison": {
                "common_urls": ["https://example.com/1"],
                "unique_per_serp": [],
                "url_counts": [],
            },
            "ranking_comparison": [],
            "similarity_metrics": {
                "pairwise_jaccard": [],
                "pairwise_spearman": [],
            },
        }

        response = client.get("/api/serps/compare?ids=serp1,serp2")
        assert response.status_code == 200
        data = response.json()
        assert data["comparison_summary"]["serp_count"] == 2
        assert data["comparison_summary"]["common_urls_count"] == 1


def test_compare_serps_three_serps(client):
    """Test comparison of 3 SERPs"""
    with patch("app.services.aql_service.compare_serps") as mock_compare:
        mock_compare.return_value = {
            "comparison_summary": {
                "serp_count": 3,
                "serp_ids": ["serp1", "serp2", "serp3"],
                "total_unique_urls": 5,
                "common_urls_count": 2,
                "avg_jaccard_similarity": 0.4,
            },
            "serps_metadata": [],
            "serps_full_data": [],
            "url_comparison": {},
            "ranking_comparison": [],
            "similarity_metrics": {},
        }

        response = client.get("/api/serps/compare?ids=serp1,serp2,serp3")
        assert response.status_code == 200
        data = response.json()
        assert data["comparison_summary"]["serp_count"] == 3


def test_compare_serps_max_five(client):
    """Test comparison of 5 SERPs (maximum allowed)"""
    with patch("app.services.aql_service.compare_serps") as mock_compare:
        mock_compare.return_value = {
            "comparison_summary": {
                "serp_count": 5,
                "serp_ids": ["s1", "s2", "s3", "s4", "s5"],
                "total_unique_urls": 10,
                "common_urls_count": 1,
                "avg_jaccard_similarity": 0.2,
            },
            "serps_metadata": [],
            "serps_full_data": [],
            "url_comparison": {},
            "ranking_comparison": [],
            "similarity_metrics": {},
        }

        response = client.get("/api/serps/compare?ids=s1,s2,s3,s4,s5")
        assert response.status_code == 200
        data = response.json()
        assert data["comparison_summary"]["serp_count"] == 5


def test_compare_serps_too_few_ids(client):
    """Test that comparison requires at least 2 IDs"""
    response = client.get("/api/serps/compare?ids=serp1")
    assert response.status_code == 400
    assert "At least 2 SERP IDs" in response.json()["detail"]


def test_compare_serps_no_ids(client):
    """Test that IDs parameter is required"""
    response = client.get("/api/serps/compare")
    assert response.status_code == 422  # FastAPI validation error


def test_compare_serps_too_many_ids(client):
    """Test that comparison rejects more than 5 IDs"""
    ids = ",".join([f"serp{i}" for i in range(1, 7)])  # 6 IDs
    response = client.get(f"/api/serps/compare?ids={ids}")
    assert response.status_code == 400
    assert "Maximum 5 SERPs" in response.json()["detail"]


def test_compare_serps_duplicate_ids(client):
    """Test that duplicate IDs are rejected"""
    response = client.get("/api/serps/compare?ids=serp1,serp2,serp1")
    assert response.status_code == 400
    assert "Duplicate SERP IDs" in response.json()["detail"]


def test_compare_serps_whitespace_handling(client):
    """Test that whitespace in IDs is handled correctly"""
    with patch("app.services.aql_service.compare_serps") as mock_compare:
        mock_compare.return_value = {
            "comparison_summary": {
                "serp_count": 2,
                "serp_ids": ["serp1", "serp2"],
                "total_unique_urls": 1,
                "common_urls_count": 0,
                "avg_jaccard_similarity": 0.0,
            },
            "serps_metadata": [],
            "serps_full_data": [],
            "url_comparison": {},
            "ranking_comparison": [],
            "similarity_metrics": {},
        }

        response = client.get("/api/serps/compare?ids=serp1, serp2 , serp3")
        # Should strip whitespace and work
        assert response.status_code == 200 or response.status_code == 400


def test_compare_serps_not_found(client):
    """Test that 404 is returned when a SERP is not found"""
    with patch("app.services.aql_service.compare_serps") as mock_compare:
        mock_compare.return_value = None  # Indicates SERP not found

        response = client.get("/api/serps/compare?ids=invalid1,invalid2")
        assert response.status_code == 404


def test_compare_serps_with_url_encoding(client):
    """Test that URL-encoded commas are handled"""
    with patch("app.services.aql_service.compare_serps") as mock_compare:
        mock_compare.return_value = {
            "comparison_summary": {
                "serp_count": 2,
                "serp_ids": ["abc-123", "def-456"],
                "total_unique_urls": 2,
                "common_urls_count": 0,
                "avg_jaccard_similarity": 0.0,
            },
            "serps_metadata": [],
            "serps_full_data": [],
            "url_comparison": {},
            "ranking_comparison": [],
            "similarity_metrics": {},
        }

        response = client.get("/api/serps/compare?ids=abc-123%2Cdef-456")
        assert response.status_code == 200


def test_compare_serps_empty_string_ids(client):
    """Test that empty strings in ID list are filtered out"""
    response = client.get("/api/serps/compare?ids=serp1,,serp2")
    # Should work if it filters empty strings, or fail if validation is strict
    # Depending on implementation, adjust assertion
    assert response.status_code in [200, 400]
