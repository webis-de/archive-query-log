def test_search_basic(client):
    response = client.get("/api/search/basic", params={"query": "halloween", "size": 5})
    assert response.status_code == 200

    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0

    for hit in data["results"]:
        url_query = hit["_source"]["url_query"]
        assert url_query is not None
        assert "halloween" in url_query.lower()
