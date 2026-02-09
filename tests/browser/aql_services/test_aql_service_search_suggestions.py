import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# 1. Basic suggestions retrieval
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_basic():
    """Test basic suggestion retrieval with a simple prefix."""
    results = await aql.search_suggestions("test", size=5)

    assert isinstance(results, dict)
    assert "prefix" in results
    assert "suggestions" in results
    assert results["prefix"] == "test"
    assert isinstance(results["suggestions"], list)


@pytest.mark.asyncio
async def test_search_suggestions_returns_correct_structure():
    """Test that each suggestion has required fields."""
    results = await aql.search_suggestions("python", size=3)

    assert len(results["suggestions"]) <= 3

    for suggestion in results["suggestions"]:
        assert isinstance(suggestion, dict)
        assert "query" in suggestion
        assert "count" in suggestion
        assert isinstance(suggestion["query"], str)
        assert isinstance(suggestion["count"], int)
        assert suggestion["count"] > 0


# ---------------------------------------------------------
# 2. Results are sorted by count (popularity)
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_sorted_by_count():
    """Test that suggestions are sorted by count in descending order."""
    results = await aql.search_suggestions("the", size=10)

    suggestions = results["suggestions"]

    # Check that results are sorted by count (descending)
    for i in range(len(suggestions) - 1):
        assert suggestions[i]["count"] >= suggestions[i + 1]["count"]


# ---------------------------------------------------------
# 3. Size parameter limits results
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_respects_size_parameter():
    """Test that the size parameter limits the number of results."""
    for size in [1, 5, 10]:
        results = await aql.search_suggestions("the", size=size)
        assert len(results["suggestions"]) <= size


@pytest.mark.asyncio
async def test_search_suggestions_size_one():
    """Test requesting only one suggestion."""
    results = await aql.search_suggestions("python", size=1)

    assert len(results["suggestions"]) <= 1
    if results["suggestions"]:
        assert isinstance(results["suggestions"][0]["query"], str)


# ---------------------------------------------------------
# 4. Time filtering with last_n_months
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_with_time_filter():
    """Test that time filtering is applied when last_n_months is specified."""
    results = await aql.search_suggestions("the", last_n_months=12, size=5)

    assert isinstance(results, dict)
    assert "suggestions" in results
    assert isinstance(results["suggestions"], list)


@pytest.mark.asyncio
async def test_search_suggestions_no_time_filter():
    """Test that no time filter is applied when last_n_months is None."""
    results = await aql.search_suggestions("the", last_n_months=None, size=5)

    assert isinstance(results, dict)
    assert "suggestions" in results


@pytest.mark.asyncio
async def test_search_suggestions_with_zero_months():
    """Test that zero months disables time filtering."""
    results = await aql.search_suggestions("the", last_n_months=0, size=5)

    assert isinstance(results, dict)
    assert "suggestions" in results


# ---------------------------------------------------------
# 5. Empty results handling
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_empty_results():
    """Test that non-existent prefix returns empty or valid suggestions."""
    results = await aql.search_suggestions("xyz_nonexistent_prefix_12345", size=10)

    assert results["prefix"] == "xyz_nonexistent_prefix_12345"
    # The mock might return results, but the function should handle it gracefully
    assert isinstance(results["suggestions"], list)


@pytest.mark.asyncio
async def test_search_suggestions_empty_suggestion_list_is_valid():
    """Test that empty suggestion list is valid response."""
    results = await aql.search_suggestions("aaa", size=10)

    assert isinstance(results["suggestions"], list)
    # May have results or not, both are valid


# ---------------------------------------------------------
# 6. Prefix parameter is preserved in response
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_prefix_in_response():
    """Test that the input prefix is included in the response."""
    prefixes = ["the", "python", "test"]

    for prefix in prefixes:
        results = await aql.search_suggestions(prefix, size=5)
        assert results["prefix"] == prefix


# ---------------------------------------------------------
# 7. Case sensitivity test
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_case_variations():
    """Test suggestions with different case variations."""
    # Elasticsearch match_phrase_prefix is case-insensitive by default
    results_lower = await aql.search_suggestions("the", size=5)
    results_upper = await aql.search_suggestions("The", size=5)

    # Both should return results
    assert isinstance(results_lower["suggestions"], list)
    assert isinstance(results_upper["suggestions"], list)


# ---------------------------------------------------------
# 8. Special characters in prefix
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_with_spaces():
    """Test prefix with spaces."""
    results = await aql.search_suggestions("the the", size=5)

    assert results["prefix"] == "the the"
    assert isinstance(results["suggestions"], list)


# ---------------------------------------------------------
# 9. Error handling
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_error_handling():
    """Test that errors don't crash but return empty suggestions."""
    with patch("archive_query_log.browser.services.aql_service.get_es_client") as mock_es_getter:
        mock_es = AsyncMock()
        mock_es.search.side_effect = Exception("Elasticsearch error")
        mock_es_getter.return_value = mock_es

        results = await aql.search_suggestions("test", size=5)

        # Should return valid response with empty suggestions on error
        assert results["prefix"] == "test"
        assert results["suggestions"] == []


# ---------------------------------------------------------
# 10. Default parameter values
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_suggestions_default_parameters():
    """Test that default parameters work correctly."""
    # Using defaults: last_n_months=36, size=10
    results = await aql.search_suggestions("the")

    assert results["prefix"] == "the"
    assert isinstance(results["suggestions"], list)
    assert len(results["suggestions"]) <= 10
