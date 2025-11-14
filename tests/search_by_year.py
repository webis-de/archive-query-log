def test_search_by_year(client):
    response = client.get("/api/search/by-year?query=halloween&year=2025")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
