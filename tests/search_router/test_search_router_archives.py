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


def test_get_archive_by_id(client):
    # Use an arbitrary id; MockESClient returns the id in response
    archive_id = "arch-123"
    response = client.get(f"/api/archive/{archive_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["archive_id"] == archive_id
    assert "archive" in data
    assert data["archive"]["_id"] == archive_id
