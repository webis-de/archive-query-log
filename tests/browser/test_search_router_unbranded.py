"""Tests for the unbranded SERP view functionality.

Tests the unified, provider-agnostic view of SERP contents
that normalizes query and result data across providers.
"""


def test_get_serp_unbranded_basic(client):
    """Test basic unbranded view for a SERP."""
    response = client.get("/serps/1?include=unbranded")
    assert response.status_code == 200

    data = response.json()
    assert "unbranded" in data

    unbranded = data["unbranded"]
    assert "serp_id" in unbranded
    assert "query" in unbranded
    assert "results" in unbranded
    assert "metadata" in unbranded


def test_unbranded_query_structure(client):
    """Test that unbranded view has correct query structure."""
    response = client.get("/serps/1?include=unbranded")
    assert response.status_code == 200

    unbranded = response.json()["unbranded"]
    query = unbranded["query"]

    assert "raw" in query
    assert "parsed" in query
    assert isinstance(query["raw"], str)


def test_unbranded_results_structure(client):
    """Test that unbranded results are normalized correctly."""
    response = client.get("/serps/1?include=unbranded")
    assert response.status_code == 200

    unbranded = response.json()["unbranded"]
    results = unbranded["results"]

    assert isinstance(results, list)
    assert len(results) > 0

    # Check result structure
    for idx, result in enumerate(results):
        assert "position" in result
        assert "url" in result
        assert "title" in result
        assert "snippet" in result
        assert result["position"] == idx + 1


def test_unbranded_metadata(client):
    """Test that metadata is included in unbranded view."""
    response = client.get("/serps/1?include=unbranded")
    assert response.status_code == 200

    unbranded = response.json()["unbranded"]
    metadata = unbranded["metadata"]

    assert "timestamp" in metadata
    assert "url" in metadata
    assert "status_code" in metadata


def test_unbranded_with_other_includes(client):
    """Test that unbranded can be combined with other include fields."""
    response = client.get("/serps/1?include=unbranded,original_url,direct_links")
    assert response.status_code == 200

    data = response.json()
    assert "unbranded" in data
    assert "original_url" in data
    assert "direct_links_count" in data
    assert "direct_links" in data


def test_unbranded_result_positions_correct(client):
    """Test that result positions are numbered correctly."""
    response = client.get("/serps/1?include=unbranded")
    assert response.status_code == 200

    unbranded = response.json()["unbranded"]
    results = unbranded["results"]

    for idx, result in enumerate(results, 1):
        assert result["position"] == idx
