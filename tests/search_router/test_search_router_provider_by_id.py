import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers.search import router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_provider_by_id_success(client):
    fake_doc = {"_id": "google", "_source": {"name": "Google"}, "found": True}
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.return_value = fake_doc
        mock_get_client.return_value = mock_es

        resp = client.get("/api/provider/google")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "google"
        assert data["provider"]["_source"]["name"] == "Google"


# plural form test
def test_providers_by_id_success(client):
    fake_doc = {"_id": "google", "_source": {"name": "Google"}, "found": True}
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.return_value = fake_doc
        mock_get_client.return_value = mock_es

        resp = client.get("/api/providers/google")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider_id"] == "google"
        assert data["provider"]["_source"]["name"] == "Google"


def test_provider_by_id_not_found(client):
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.side_effect = Exception("ES error")
        mock_get_client.return_value = mock_es

        resp = client.get("/api/provider/unknown")
        assert resp.status_code == 404
        data = resp.json()
        assert data["detail"] == "No results found"
