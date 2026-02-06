import pytest
import app.services.aql_service as aql


# ---------------------------------------------------------
# autocomplete_providers
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_autocomplete_providers():
    """
    Testet, dass die Autocomplete-Funktion für Provider korrekt Namen zurückgibt.
    Nutzt den globalen Elasticsearch-Mock aus conftest.py.
    """
    results = await aql.autocomplete_providers("a", size=2)

    # Result should contain the names from the mock
    assert isinstance(results, list)
    assert "Google" in results
    assert "Bing" in results
    # Size of the result corresponds to the requested size
    assert len(results) == 2
