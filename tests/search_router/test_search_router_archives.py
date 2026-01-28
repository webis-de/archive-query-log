"""Tests for Archives endpoints (/api/archives and /api/archive/{id})"""


def test_get_all_archives(client):
    response = client.get("/api/archives")
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "results" in data
    assert isinstance(data["results"], list)
    assert data["count"] == len(data["results"])  # simple consistency check


def test_get_all_archives_with_size_limit(client):
    response = client.get("/api/archives?size=1")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["results"]) == 1
