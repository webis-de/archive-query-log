def test_search_basic(client):
    response = client.get("/api/serps", params={"query": "halloween", "size": 5})
    assert response.status_code == 200

    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    assert len(data["results"]) > 0

    # Verify each result has the required structure
    for hit in data["results"]:
        assert "_source" in hit
        assert "url_query" in hit["_source"]
        assert hit["_source"]["url_query"] is not None
