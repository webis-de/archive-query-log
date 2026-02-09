# TODO: Re-enable or delete.
# def test_autocomplete_providers(client):
#    response = client.get("/api/autocomplete/providers?q=goo&size=2")
#    assert response.status_code == 200
#    data = response.json()
#
#    assert "results" in data
#    assert isinstance(data["results"], list)
#    assert len(data["results"]) == 2
#
#    # Verify that we get provider names as strings
#    for provider_name in data["results"]:
#        assert isinstance(provider_name, str)
#        assert len(provider_name) > 0
