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
# 🔹 Elasticsearch Mock Fixture
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
                    "total": {"value": 2, "relation": "eq"},
                    "hits": [
                        {
                            "_id": "1",
                            "_source": {"name": "Google", "domain": "google.com"},
                        },
                        {
                            "_id": "2",
                            "_source": {"name": "Bing", "domain": "bing.com"},
                        },
                    ],
                }
            }
        else:
            # Check for archive aggregation queries
            aggs = kwargs.get("body", {}).get("aggs", {})
            if "unique_archives" in aggs:
                # Return aggregation data for archives
                return {
                    "hits": {"total": {"value": 100, "relation": "eq"}, "hits": []},
                    "aggregations": {
                        "unique_archives": {
                            "buckets": [
                                {"key": "https://web.archive.org/web", "doc_count": 80},
                                {"key": "https://archive.example.org", "doc_count": 20},
                            ]
                        }
                    },
                }

            # Check for archive match/term query used by get_archive_metadata()
            query_clause = kwargs.get("body", {}).get("query", {})
            # Normalize to get the requested archive id
            requested_id = None

            # Handle simple match query
            if (
                "match" in query_clause
                and "archive.memento_api_url" in query_clause["match"]
            ):
                requested_id = query_clause["match"]["archive.memento_api_url"]
            # Handle term query
            elif (
                "term" in query_clause
                and "archive.memento_api_url" in query_clause["term"]
            ):
                requested_id = query_clause["term"]["archive.memento_api_url"]
            # Handle bool query with must clause (new format with hidden filter)
            elif "bool" in query_clause:
                bool_query = query_clause["bool"]
                must_clauses = bool_query.get("must", [])
                for clause in must_clauses:
                    if (
                        "match" in clause
                        and "archive.memento_api_url" in clause["match"]
                    ):
                        requested_id = clause["match"]["archive.memento_api_url"]
                        break

            if requested_id is not None:
                # Simulate found/not found with counts aligned to aggregation mock
                if requested_id == "https://web.archive.org/web":
                    serp_count = 80
                elif requested_id == "https://archive.example.org":
                    serp_count = 20
                else:
                    serp_count = 0

                return {
                    "hits": {
                        "total": {"value": serp_count, "relation": "eq"},
                        "hits": (
                            [
                                {
                                    "_id": "doc-1",
                                    "_source": {
                                        "archive": {
                                            "memento_api_url": requested_id,
                                            "cdx_api_url": (
                                                "https://web.archive.org/cdx/search/csv"
                                                if requested_id.startswith(
                                                    "https://web.archive.org"
                                                )
                                                else None
                                            ),
                                        }
                                    },
                                }
                            ]
                            if serp_count > 0
                            else []
                        ),
                    }
                }

            # Default mock data for SERP searches
            return {
                "hits": {
                    "total": {"value": 2, "relation": "eq"},
                    "hits": [
                        {
                            "_id": "1",
                            "_source": {"url_query": "halloween", "provider": "Google"},
                        },
                        {
                            "_id": "2",
                            "_source": {"url_query": "pumpkin", "provider": "Google"},
                        },
                    ],
                }
            }

    class MockESClient:
        async def search(self, *args, **kwargs):
            return await mock_search(*args, **kwargs)

        async def get(self, index=None, id=None):
            """Mock get method for single document retrieval"""
            return {
                "_id": id or "test-id",
                "_source": {
                    "url_query": "test query",
                    "capture": {
                        "url": "https://google.com/search?q=test",
                        "timestamp": "2021-01-01T00:00:00+00:00",
                        "status_code": 200,
                    },
                    "provider": {"id": "google", "domain": "google.com"},
                    "archive": {"memento_api_url": "https://web.archive.org/web"},
                    "results": [
                        {
                            "url": "https://example.com/1",
                            "title": "Result 1",
                            "snippet": "First result snippet",
                        },
                        {
                            "url": "https://example.com/2",
                            "title": "Result 2",
                            "description": "Second result description",
                        },
                    ],
                },
                "found": True,
            }

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
