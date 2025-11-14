"""Tests for Hello Router"""


def test_hello_world(client):
    """Test basic hello world endpoint"""
    response = client.get("/api/hello")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, World!"}


def test_hello_with_name(client):
    """Test personalized greeting endpoint"""
    name = "Alice"
    response = client.get(f"/api/hello/{name}")
    assert response.status_code == 200
    assert response.json() == {"message": f"Hello, {name}!"}


def test_hello_with_special_characters(client):
    """Test greeting with URL-encoded special characters"""
    name = "Max Müller"
    response = client.get(f"/api/hello/{name}")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert name in data["message"]
