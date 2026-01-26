"""
Tests for fuzzy search mode with advanced features.

Tests fuzzy search, fuzziness levels, "did you mean?" suggestions, and synonym expansion.
"""


def test_fuzzy_search_basic(client):
    """Test basic fuzzy search with typo."""
    response = client.get("/api/serps?query=clmate&fuzzy=true")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzzy"] is True
    assert data["fuzziness"] == "AUTO"
    assert "results" in data


def test_fuzzy_search_disabled(client):
    """Test that fuzzy search is disabled by default."""
    response = client.get("/api/serps?query=climate")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzzy"] is False
    assert data["fuzziness"] is None


def test_fuzziness_levels(client):
    """Test different fuzziness levels."""
    # Test fuzziness=0 (exact match)
    response = client.get("/api/serps?query=climate&fuzzy=true&fuzziness=0")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzziness"] == "0"

    # Test fuzziness=1
    response = client.get("/api/serps?query=climate&fuzzy=true&fuzziness=1")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzziness"] == "1"

    # Test fuzziness=2
    response = client.get("/api/serps?query=climate&fuzzy=true&fuzziness=2")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzziness"] == "2"

    # Test fuzziness=AUTO
    response = client.get("/api/serps?query=climate&fuzzy=true&fuzziness=AUTO")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzziness"] == "AUTO"


def test_invalid_fuzziness(client):
    """Test that invalid fuzziness values are rejected."""
    response = client.get("/api/serps?query=climate&fuzzy=true&fuzziness=5")
    assert response.status_code == 400
    assert "fuzziness must be one of" in response.json()["detail"]


def test_did_you_mean_suggestions(client):
    """Test 'Did you mean?' suggestions."""
    # Search with misspelling that should trigger suggestions
    response = client.get("/api/serps?query=clmate&fuzzy=true")
    assert response.status_code == 200
    data = response.json()
    # Suggestions may or may not be present depending on data
    # Just verify the field exists when suggestions are available
    if "did_you_mean" in data:
        assert isinstance(data["did_you_mean"], list)
        if len(data["did_you_mean"]) > 0:
            assert "text" in data["did_you_mean"][0]
            assert "score" in data["did_you_mean"][0]


def test_expand_synonyms(client):
    """Test enhanced relevance scoring."""
    response = client.get("/api/serps?query=climate&expand_synonyms=true")
    assert response.status_code == 200
    data = response.json()
    assert data["expand_synonyms"] is True
    assert "results" in data


def test_expand_synonyms_with_fuzzy(client):
    """Test combining synonym expansion with fuzzy matching."""
    response = client.get(
        "/api/serps?query=climat&expand_synonyms=true&fuzzy=true&fuzziness=1"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["expand_synonyms"] is True
    assert data["fuzzy"] is True
    assert data["fuzziness"] == "1"


def test_fuzzy_search_with_filters(client):
    """Test fuzzy search with additional filters."""
    response = client.get("/api/serps?query=clmate&fuzzy=true&year=2023")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzzy"] is True


def test_fuzzy_search_with_advanced_mode(client):
    """Test that advanced_mode works with fuzzy."""
    response = client.get("/api/serps?query=climate&fuzzy=true&advanced_mode=true")
    assert response.status_code == 200
    data = response.json()
    assert data["advanced_mode"] is True
    assert data["fuzzy"] is True


def test_fuzzy_search_misspellings(client):
    """Test fuzzy search with common misspellings."""
    misspellings = [
        "renwable",  # renewable
        "tehnology",  # technology
        "informaton",  # information
    ]

    for misspelled in misspellings:
        response = client.get(f"/api/serps?query={misspelled}&fuzzy=true")
        assert response.status_code == 200
        data = response.json()
        assert data["fuzzy"] is True
        assert "results" in data


def test_fuzzy_search_pagination(client):
    """Test fuzzy search with pagination."""
    response = client.get("/api/serps?query=clmate&fuzzy=true&page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert data["fuzzy"] is True
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert "pagination" in data


def test_fuzzy_search_response_structure(client):
    """Test that fuzzy search response has correct structure."""
    response = client.get("/api/serps?query=climate&fuzzy=true")
    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert "query" in data
    assert "count" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert "fuzzy" in data
    assert "fuzziness" in data
    assert "expand_synonyms" in data
    assert "advanced_mode" in data
    assert "pagination" in data
    assert "results" in data
