def test_search_advanced_with_provider(client):
    response = client.get(
        "/api/search/advanced?query=test&provider_id=f205fc44-d918-4b79-9a7f-c1373a6ff9f2"
    )
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
