"""Test Configuration and Fixtures

This module contains pytest fixtures and configuration that can be
shared across all test modules.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app

    Usage in tests:
        def test_something(client):
            response = client.get("/")
            assert response.status_code == 200
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_data():
    """Example fixture for test data

    You can create fixtures for database connections,
    mock data, authentication tokens, etc.
    """
    return {"name": "Test User", "email": "test@example.com"}


# -------------------------------------------------------------------
# 🔹 Elasticsearch Mock Fixture (wird automatisch für alle Tests aktiviert)
# -------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_elasticsearch(monkeypatch):
    """
    Automatically mock the Elasticsearch client for all tests.

    This avoids real network calls (e.g., VPN or Kibana access)
    and provides predictable dummy data for test assertions.
    """

    async def mock_search(*args, **kwargs):
        # Simulate a realistic Elasticsearch search result
        return {
            "hits": {
                "hits": [
                    {
                        "_id": "1",
                        "_source": {"url_query": "halloween", "provider": "Google"},
                    },
                    {
                        "_id": "2",
                        "_source": {"url_query": "pumpkin", "provider": "Google"},
                    },
                ]
            }
        }

    class MockESClient:
        async def search(self, *args, **kwargs):
            return await mock_search(*args, **kwargs)

        async def close(self):
            pass

    # Override the real get_es_client function from app.core.elastic
    monkeypatch.setattr("app.core.elastic.get_es_client", lambda: MockESClient())
