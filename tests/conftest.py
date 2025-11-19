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
        # Simulate different Elasticsearch results based on the index
        index = kwargs.get("index", "")

        if "provider" in index:
            # Mock data for provider autocomplete
            return {
                "hits": {
                    "hits": [
                        {
                            "_id": "1",
                            "_source": {"name": "Google", "domain": "google.com"},
                        },
                        {
                            "_id": "2",
                            "_source": {"name": "Bing", "domain": "bing.com"},
                        },
                    ]
                }
            }
        else:
            # Default mock data for SERP searches
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

    # Create mock instance
    mock_client = MockESClient()

    # Override the get_es_client function to return our mock
    monkeypatch.setattr("app.core.elastic.get_es_client", lambda: mock_client)

    # Also patch the global es_client variable
    monkeypatch.setattr("app.core.elastic.es_client", mock_client)
    # Patch in services module too (in case it was already imported)
    monkeypatch.setattr("app.services.aql_service.get_es_client", lambda: mock_client)
