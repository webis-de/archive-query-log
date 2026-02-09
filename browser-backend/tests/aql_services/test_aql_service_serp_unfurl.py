import pytest
from unittest.mock import AsyncMock, patch
import archive_query_log.browser.services.aql_service as aql


# ---------------------------------------------------------
# Standardfall: simple URL
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_success():
    mock_serp = {
        "_id": "test-unfurl-123",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=python+tutorial&hl=en&start=10"
            }
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-unfurl-123")

        parsed = result["parsed"]
        assert result["serp_id"] == "test-unfurl-123"
        assert parsed["scheme"] == "https"
        assert parsed["netloc"] == "google.com"
        assert parsed["path"] == "/search"
        assert parsed["path_segments"] == ["search"]
        assert parsed["query_parameters"]["q"] == "python tutorial"
        assert parsed["query_parameters"]["hl"] == "en"
        assert parsed["query_parameters"]["start"] == "10"


# ---------------------------------------------------------
# URL with subdomain
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_with_subdomain():
    mock_serp = {
        "_id": "test-subdomain",
        "_source": {
            "capture": {"url": "https://scholar.google.com/scholar?q=machine+learning"}
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-subdomain")
        domain_parts = result["parsed"]["domain_parts"]
        assert domain_parts["subdomain"] == "scholar"
        assert domain_parts["domain"] == "google"
        assert domain_parts["suffix"] == "com"
        assert result["parsed"]["netloc"] == "scholar.google.com"


# ---------------------------------------------------------
# URL with port
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_with_port():
    mock_serp = {
        "_id": "test-port",
        "_source": {"capture": {"url": "https://example.com:8443/search?q=test"}},
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-port")
        assert result["parsed"]["port"] == 8443
        assert result["parsed"]["netloc"] == "example.com:8443"


# ---------------------------------------------------------
# URL with multiple path segments
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_path_segments():
    mock_serp = {
        "_id": "test-path",
        "_source": {
            "capture": {"url": "https://example.com/search/advanced/results?q=test"}
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-path")
        assert result["parsed"]["path"] == "/search/advanced/results"
        assert result["parsed"]["path_segments"] == ["search", "advanced", "results"]


# ---------------------------------------------------------
# URL with encoded parameters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_encoded_params():
    mock_serp = {
        "_id": "test-encoded",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=%E3%83%86%E3%82%B9%E3%83%88&source=web"
            }
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-encoded")
        assert "テスト" in result["parsed"]["query_parameters"]["q"]
        assert result["parsed"]["query_parameters"]["source"] == "web"


# ---------------------------------------------------------
# URL with fragment
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_with_fragment():
    mock_serp = {
        "_id": "test-fragment",
        "_source": {"capture": {"url": "https://example.com/search?q=test#results"}},
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-fragment")
        assert result["parsed"]["fragment"] == "results"
        assert result["parsed"]["query_parameters"]["q"] == "test"


# ---------------------------------------------------------
# URL without query parameters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_no_query_params():
    mock_serp = {
        "_id": "test-no-params",
        "_source": {"capture": {"url": "https://example.com/search"}},
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-no-params")
        assert result["parsed"]["query_parameters"] == {}
        assert result["parsed"]["path_segments"] == ["search"]


# ---------------------------------------------------------
# URL with multiple values for a parameter
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_multiple_values():
    mock_serp = {
        "_id": "test-multi",
        "_source": {
            "capture": {
                "url": "https://example.com/search?tag=python&tag=programming&q=test"
            }
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-multi")
        tags = result["parsed"]["query_parameters"]["tag"]
        assert isinstance(tags, list)
        assert "python" in tags
        assert "programming" in tags
        assert result["parsed"]["query_parameters"]["q"] == "test"


# ---------------------------------------------------------
# URL with complex TLD
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_complex_tld():
    mock_serp = {
        "_id": "test-complex-tld",
        "_source": {"capture": {"url": "https://www.google.co.uk/search?q=test"}},
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-complex-tld")
        domain_parts = result["parsed"]["domain_parts"]
        assert domain_parts["subdomain"] == "www"
        assert domain_parts["domain"] == "google"
        assert domain_parts["suffix"] == "co.uk"
        assert domain_parts["registered_domain"] == "google.co.uk"


# ---------------------------------------------------------
# SERP not found
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_serp_not_found():
    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_unfurl("nonexistent-id")
        assert result is None


# ---------------------------------------------------------
# URL with special characters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_special_chars():
    mock_serp = {
        "_id": "test-special",
        "_source": {
            "capture": {"url": "https://google.com/search?q=how+to+use+%26+operator"}
        },
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-special")
        assert result["parsed"]["query_parameters"]["q"] == "how to use & operator"


# ---------------------------------------------------------
# URL with empty path
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_empty_path():
    mock_serp = {
        "_id": "test-empty-path",
        "_source": {"capture": {"url": "https://example.com/?q=test"}},
    }

    with patch(
        "archive_query_log.browser.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-empty-path")
        assert result["parsed"]["path"] == "/"
        assert result["parsed"]["path_segments"] == []
