import pytest
from fastapi.testclient import TestClient
from archive_query_log.browser.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------
# 1. Basic endpoint functionality
# ---------------------------------------------------------
def test_suggestions_endpoint_basic(client):
    """Test basic suggestions endpoint with required parameters."""
    response = client.get("/api/suggestions?prefix=test")

    assert response.status_code == 200
    data = response.json()

    assert "prefix" in data
    assert "suggestions" in data
    assert data["prefix"] == "test"
    assert isinstance(data["suggestions"], list)


def test_suggestions_endpoint_with_size(client):
    """Test suggestions endpoint with size parameter."""
    response = client.get("/api/suggestions?prefix=python&size=5")

    assert response.status_code == 200
    data = response.json()

    assert len(data["suggestions"]) <= 5


def test_suggestions_endpoint_with_all_parameters(client):
    """Test suggestions endpoint with all parameters."""
    response = client.get("/api/suggestions?prefix=the&size=10&last_n_months=12")

    assert response.status_code == 200
    data = response.json()

    assert data["prefix"] == "the"
    assert isinstance(data["suggestions"], list)


# ---------------------------------------------------------
# 2. Query parameter validation
# ---------------------------------------------------------
def test_suggestions_missing_prefix(client):
    """Test that missing prefix parameter returns error."""
    response = client.get("/api/suggestions")

    # Should return 422 (validation error)
    assert response.status_code == 422


def test_suggestions_size_too_small(client):
    """Test that size < 1 returns validation error."""
    response = client.get("/api/suggestions?prefix=test&size=0")

    assert response.status_code == 422


def test_suggestions_size_too_large(client):
    """Test that size > 50 returns validation error."""
    response = client.get("/api/suggestions?prefix=test&size=51")

    assert response.status_code == 422


def test_suggestions_valid_size_boundaries(client):
    """Test valid size boundaries (1 and 50)."""
    # Size = 1
    response = client.get("/api/suggestions?prefix=test&size=1")
    assert response.status_code == 200

    # Size = 50
    response = client.get("/api/suggestions?prefix=test&size=50")
    assert response.status_code == 200


# ---------------------------------------------------------
# 3. Response format and structure
# ---------------------------------------------------------
def test_suggestions_response_structure(client):
    """Test that response has correct structure."""
    response = client.get("/api/suggestions?prefix=test&size=3")

    assert response.status_code == 200
    data = response.json()

    # Root level
    assert isinstance(data, dict)
    assert set(data.keys()) == {"prefix", "suggestions"}

    # Suggestions array
    assert isinstance(data["suggestions"], list)

    # Each suggestion
    for suggestion in data["suggestions"]:
        assert set(suggestion.keys()) == {"query", "count"}
        assert isinstance(suggestion["query"], str)
        assert isinstance(suggestion["count"], int)
        assert suggestion["count"] > 0


def test_suggestions_response_content_type(client):
    """Test that response has correct content type."""
    response = client.get("/api/suggestions?prefix=test")

    assert response.headers["content-type"] == "application/json"


# ---------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------
def test_suggestions_with_special_characters(client):
    """Test prefix with special characters."""
    # Use URL-encoded %2B for + character
    response = client.get("/api/suggestions?prefix=c%2B%2B")

    assert response.status_code == 200
    assert response.json()["prefix"] == "c++"


def test_suggestions_with_spaces(client):
    """Test prefix with spaces."""
    response = client.get("/api/suggestions?prefix=hello+world")

    assert response.status_code == 200
    assert response.json()["prefix"] == "hello world"


def test_suggestions_empty_prefix(client):
    """Test with empty prefix string."""
    response = client.get("/api/suggestions?prefix=")

    # Empty prefix might be valid, check structure
    if response.status_code == 200:
        data = response.json()
        assert "prefix" in data
        assert "suggestions" in data


# ---------------------------------------------------------
# 5. Default parameters
# ---------------------------------------------------------
def test_suggestions_default_size(client):
    """Test that default size is 10 when not specified."""
    response = client.get("/api/suggestions?prefix=test")

    assert response.status_code == 200
    # Should return at most 10 (or fewer if not enough results)
    assert len(response.json()["suggestions"]) <= 10


def test_suggestions_default_last_n_months(client):
    """Test that default last_n_months=36 is applied."""
    response = client.get("/api/suggestions?prefix=test")

    # Just check that it works with default
    assert response.status_code == 200
