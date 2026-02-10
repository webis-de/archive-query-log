"""Tests for Archives endpoints (/archives and /archive/{id})"""


def test_get_all_archives(client):
    response = client.get("/archives")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "archives" in data
    assert isinstance(data["archives"], list)


def test_get_all_archives_with_size_limit(client):
    response = client.get("/archives?size=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data["archives"]) == 1
