import pytest
from unittest.mock import patch, AsyncMock

import app.services.aql_service as aql


# Utility: fake ES response
def es_response(hits):
    return {"hits": {"hits": hits}}


# Utility: create mocked ES client
def mock_es(return_value):
    client = AsyncMock()
    client.search.return_value = return_value
    return client


# ---------------------------------------------------------
# 1. search_basic
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_basic():
    fake_hits = [{"a": 1}]

    with patch(
        "app.services.aql_service.get_es_client",
        return_value=mock_es(es_response(fake_hits)),
    ) as mock_get:
        results = await aql.search_basic("test", size=5)

        mock_get.assert_called_once()
        assert results == fake_hits


# ---------------------------------------------------------
# 2. search_providers
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_providers():
    fake_hits = [{"provider": "x"}]

    with patch(
        "app.services.aql_service.get_es_client",
        return_value=mock_es(es_response(fake_hits)),
    ) as mock_get:
        results = await aql.search_providers("abc", size=3)

        mock_get.assert_called_once()
        assert results == fake_hits


# ---------------------------------------------------------
# 3. search_advanced – test full filter combination
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_advanced_all_filters():
    fake_hits = [{"hit": 1}]

    mock_client = mock_es(es_response(fake_hits))

    with patch("app.services.aql_service.get_es_client", return_value=mock_client):
        results = await aql.search_advanced(
            query="foo", provider_id="p123", year=2020, status_code=404, size=7
        )

        # Verify ES client was called with correct query body
        mock_client.search.assert_awaited_once()
        args, kwargs = mock_client.search.call_args

        assert kwargs["index"] == "aql_serps"

        body = kwargs["body"]

        # Must match structure
        assert body["size"] == 7
        assert {"match": {"url_query": "foo"}} in body["query"]["bool"]["must"]

        filters = body["query"]["bool"]["filter"]
        assert {"term": {"provider.id": "p123"}} in filters
        assert {"term": {"capture.status_code": 404}} in filters

        # Range filter for year
        assert any("range" in f for f in filters)

        assert results == fake_hits


# ---------------------------------------------------------
# 4. search_advanced – test minimal filters
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_advanced_minimal():
    fake_hits = [{"hit": 99}]
    mock_client = mock_es(es_response(fake_hits))

    with patch("app.services.aql_service.get_es_client", return_value=mock_client):
        results = await aql.search_advanced(query="x")

        mock_client.search.assert_awaited_once()
        body = mock_client.search.call_args.kwargs["body"]

        # no filters except must
        assert body["query"]["bool"]["filter"] == []
        assert results == fake_hits


# ---------------------------------------------------------
# 5. autocomplete_providers
# ---------------------------------------------------------
# @pytest.mark.asyncio
# async def test_autocomplete_providers():
#    fake_hits = [{"_source": {"name": "Alpha"}}, {"_source": {"name": "Beta"}}]
#    mock_client = mock_es(es_response(fake_hits))

#    with patch("app.services.aql_service.get_es_client", return_value=mock_client):
#        results = await aql.autocomplete_providers("a", size=2)
#
#        mock_client.search.assert_awaited_once()
#        assert results == ["Alpha", "Beta"]


# ---------------------------------------------------------
# 6. search_by_year – test delegating
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_search_by_year_calls_advanced():
    with patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=[1, 2]),
    ) as mock_adv:
        results = await aql.search_by_year("foo", 2022, size=5)

        mock_adv.assert_awaited_once_with(query="foo", year=2022, size=5)
        assert results == [1, 2]


# ---------------------------------------------------------
# 7. get_serp_by_id
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_by_id_success():
    """Test get_serp_by_id with real Elasticsearch mock"""
    mock_es_response = {
        "_id": "test-id",
        "_source": {"url_query": "test"},
        "found": True,
    }

    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.return_value = mock_es_response
        mock_get_client.return_value = mock_es

        result = await aql.get_serp_by_id("test-id")

        assert result == mock_es_response
        mock_es.get.assert_called_once_with(index="aql_serps", id="test-id")


@pytest.mark.asyncio
async def test_get_serp_by_id_exception():
    """Test get_serp_by_id when Elasticsearch raises exception"""
    with patch("app.services.aql_service.get_es_client") as mock_get_client:
        mock_es = AsyncMock()
        mock_es.get.side_effect = Exception("ES error")
        mock_get_client.return_value = mock_es

        result = await aql.get_serp_by_id("test-id")

        assert result is None


# ---------------------------------------------------------
# 8. get_serp_original_url
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_original_url_success():
    """Test get_serp_original_url returns correct URL"""
    mock_serp = {
        "_id": "test-uuid-1234",
        "_source": {
            "capture": {"url": "https://google.com/search?q=test&utm_source=tracking"}
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_original_url("test-uuid-1234")

        assert result == {
            "serp_id": "test-uuid-1234",
            "original_url": "https://google.com/search?q=test&utm_source=tracking",
        }


@pytest.mark.asyncio
async def test_get_serp_original_url_with_tracking_removal():
    """Test get_serp_original_url with tracking parameter removal"""
    mock_serp = {
        "_id": "test-id",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=test&utm_source=email&fbclid=123"
            }
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_original_url("test-id", remove_tracking=True)

        assert result["serp_id"] == "test-id"
        assert (
            result["original_url"]
            == "https://google.com/search?q=test&utm_source=email&fbclid=123"
        )
        assert "url_without_tracking" in result
        assert "utm_source" not in result["url_without_tracking"]
        assert "fbclid" not in result["url_without_tracking"]
        assert "q=test" in result["url_without_tracking"]


@pytest.mark.asyncio
async def test_get_serp_original_url_serp_not_found():
    """Test get_serp_original_url when SERP doesn't exist"""
    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_original_url("nonexistent-id")

        assert result is None


# ---------------------------------------------------------
# 9. get_serp_memento_url
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_memento_url_success():
    """Test get_serp_memento_url constructs correct Memento URL"""
    mock_serp = {
        "_id": "test-uuid-5678",
        "_source": {
            "archive": {"memento_api_url": "https://web.archive.org/web"},
            "capture": {
                "url": "https://google.com/search?q=python",
                "timestamp": "2021-06-15T14:30:45+00:00",
            },
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_memento_url("test-uuid-5678")

        assert result["serp_id"] == "test-uuid-5678"
        assert (
            result["memento_url"]
            == "https://web.archive.org/web/20210615143045/https://google.com/search?q=python"
        )


@pytest.mark.asyncio
async def test_get_serp_memento_url_different_timestamp():
    """Test memento URL with different timestamp format"""
    mock_serp = {
        "_id": "test-id-999",
        "_source": {
            "archive": {"memento_api_url": "https://archive.example.org"},
            "capture": {
                "url": "https://bing.com/search?q=test",
                "timestamp": "2020-01-01T00:00:00+00:00",
            },
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_memento_url("test-id-999")

        assert result["serp_id"] == "test-id-999"
        assert (
            result["memento_url"]
            == "https://archive.example.org/20200101000000/https://bing.com/search?q=test"
        )


@pytest.mark.asyncio
async def test_get_serp_memento_url_serp_not_found():
    """Test get_serp_memento_url when SERP doesn't exist"""
    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_memento_url("nonexistent-id")

        assert result is None


# ---------------------------------------------------------
# 10. get_related_serps
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_related_serps_success():
    """Test get_related_serps returns SERPs with same query"""
    mock_serp = {
        "_id": "serp-123",
        "_source": {
            "url_query": "python tutorial",
            "provider": {"id": "provider-1"},
        },
    }

    mock_related = [
        {"_id": "serp-123", "_source": {"url_query": "python tutorial"}},
        {"_id": "serp-456", "_source": {"url_query": "python tutorial"}},
        {"_id": "serp-789", "_source": {"url_query": "python tutorial"}},
    ]

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ) as mock_search:
        result = await aql.get_related_serps("serp-123", size=10)

        # Should call search_advanced with correct query
        mock_search.assert_awaited_once_with(
            query="python tutorial", provider_id=None, size=11
        )

        # Should exclude the original SERP (serp-123)
        assert len(result) == 2
        assert all(hit["_id"] != "serp-123" for hit in result)
        assert result[0]["_id"] == "serp-456"
        assert result[1]["_id"] == "serp-789"


@pytest.mark.asyncio
async def test_get_related_serps_with_same_provider():
    """Test get_related_serps with same_provider filter"""
    mock_serp = {
        "_id": "serp-abc",
        "_source": {
            "url_query": "machine learning",
            "provider": {"id": "google-provider"},
        },
    }

    mock_related = [
        {"_id": "serp-def", "_source": {"url_query": "machine learning"}},
    ]

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ) as mock_search:
        result = await aql.get_related_serps("serp-abc", size=5, same_provider=True)

        # Should call with provider_id
        mock_search.assert_awaited_once_with(
            query="machine learning", provider_id="google-provider", size=6
        )

        assert len(result) == 1
        assert result[0]["_id"] == "serp-def"


@pytest.mark.asyncio
async def test_get_related_serps_excludes_current_serp():
    """Test that current SERP is excluded from results"""
    mock_serp = {
        "_id": "current-serp",
        "_source": {
            "url_query": "test query",
            "provider": {"id": "provider-x"},
        },
    }

    # Mock returns 3 results including the current SERP
    mock_related = [
        {"_id": "current-serp", "_source": {}},  # Should be filtered out
        {"_id": "related-1", "_source": {}},
        {"_id": "related-2", "_source": {}},
    ]

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ):
        result = await aql.get_related_serps("current-serp", size=2)

        # Current SERP should be filtered out
        assert len(result) == 2
        assert not any(hit["_id"] == "current-serp" for hit in result)
        assert result[0]["_id"] == "related-1"
        assert result[1]["_id"] == "related-2"


@pytest.mark.asyncio
async def test_get_related_serps_respects_size_limit():
    """Test that size parameter is respected after filtering"""
    mock_serp = {
        "_id": "serp-main",
        "_source": {
            "url_query": "test",
            "provider": {"id": "p1"},
        },
    }

    # Mock returns 6 results (size+1)
    mock_related = [{"_id": f"serp-{i}", "_source": {}} for i in range(6)]

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ):
        result = await aql.get_related_serps("serp-main", size=5)

        # Should return exactly 5 results (size parameter)
        assert len(result) == 5


@pytest.mark.asyncio
async def test_get_related_serps_serp_not_found():
    """Test get_related_serps when original SERP doesn't exist"""
    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_related_serps("nonexistent-id")

        # Should return empty list
        assert result == []


@pytest.mark.asyncio
async def test_get_related_serps_no_related_found():
    """Test when no related SERPs exist (only current SERP returned)"""
    mock_serp = {
        "_id": "lonely-serp",
        "_source": {
            "url_query": "very unique query",
            "provider": {"id": "p1"},
        },
    }

    # Only the current SERP is returned
    mock_related = [
        {"_id": "lonely-serp", "_source": {}},
    ]

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ):
        result = await aql.get_related_serps("lonely-serp", size=10)

        # After filtering out current SERP, should return empty list
        assert result == []


@pytest.mark.asyncio
async def test_get_related_serps_custom_size():
    """Test get_related_serps with custom size parameter"""
    mock_serp = {
        "_id": "serp-x",
        "_source": {
            "url_query": "test",
            "provider": {"id": "p1"},
        },
    }

    mock_related = [{"_id": f"serp-{i}", "_source": {}} for i in range(21)]

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ), patch(
        "app.services.aql_service.search_advanced",
        new=AsyncMock(return_value=mock_related),
    ) as mock_search:
        result = await aql.get_related_serps("serp-x", size=20)

        # Should request size+1 to account for filtering
        mock_search.assert_awaited_once_with(query="test", provider_id=None, size=21)

        # Should return exactly 20 results
        assert len(result) == 20


# ---------------------------------------------------------
# 11. get_serp_unfurl
# ---------------------------------------------------------
@pytest.mark.asyncio
async def test_get_serp_unfurl_success():
    """Test unfurling a SERP URL with query parameters"""
    mock_serp = {
        "_id": "test-unfurl-123",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=python+tutorial&hl=en&start=10"
            }
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-unfurl-123")

        assert result["serp_id"] == "test-unfurl-123"
        assert (
            result["original_url"]
            == "https://google.com/search?q=python+tutorial&hl=en&start=10"
        )

        parsed = result["parsed"]
        assert parsed["scheme"] == "https"
        assert parsed["netloc"] == "google.com"
        assert parsed["port"] is None
        assert parsed["path"] == "/search"
        assert parsed["path_segments"] == ["search"]
        assert parsed["domain_parts"]["domain"] == "google"
        assert parsed["domain_parts"]["suffix"] == "com"
        assert parsed["domain_parts"]["subdomain"] is None
        assert parsed["domain_parts"]["registered_domain"] == "google.com"
        assert parsed["query_parameters"]["q"] == "python tutorial"
        assert parsed["query_parameters"]["hl"] == "en"
        assert parsed["query_parameters"]["start"] == "10"


@pytest.mark.asyncio
async def test_get_serp_unfurl_with_subdomain():
    """Test unfurling URL with subdomain"""
    mock_serp = {
        "_id": "test-subdomain",
        "_source": {
            "capture": {"url": "https://scholar.google.com/scholar?q=machine+learning"}
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-subdomain")

        domain_parts = result["parsed"]["domain_parts"]
        assert domain_parts["subdomain"] == "scholar"
        assert domain_parts["domain"] == "google"
        assert domain_parts["suffix"] == "com"
        assert domain_parts["registered_domain"] == "google.com"
        assert result["parsed"]["netloc"] == "scholar.google.com"


@pytest.mark.asyncio
async def test_get_serp_unfurl_with_port():
    """Test unfurling URL with explicit port"""
    mock_serp = {
        "_id": "test-port",
        "_source": {"capture": {"url": "https://example.com:8443/search?q=test"}},
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-port")

        assert result["parsed"]["port"] == 8443
        assert result["parsed"]["netloc"] == "example.com:8443"


@pytest.mark.asyncio
async def test_get_serp_unfurl_path_segments():
    """Test unfurling URL with multiple path segments"""
    mock_serp = {
        "_id": "test-path",
        "_source": {
            "capture": {"url": "https://example.com/search/advanced/results?q=test"}
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-path")

        assert result["parsed"]["path"] == "/search/advanced/results"
        assert result["parsed"]["path_segments"] == ["search", "advanced", "results"]


@pytest.mark.asyncio
async def test_get_serp_unfurl_encoded_params():
    """Test unfurling URL with URL-encoded parameters"""
    mock_serp = {
        "_id": "test-encoded",
        "_source": {
            "capture": {
                "url": "https://google.com/search?q=%E3%83%86%E3%82%B9%E3%83%88&source=web"
            }
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-encoded")

        # URL-encoded Japanese characters should be decoded
        assert "テスト" in result["parsed"]["query_parameters"]["q"]
        assert result["parsed"]["query_parameters"]["source"] == "web"


@pytest.mark.asyncio
async def test_get_serp_unfurl_with_fragment():
    """Test unfurling URL with fragment identifier"""
    mock_serp = {
        "_id": "test-fragment",
        "_source": {"capture": {"url": "https://example.com/search?q=test#results"}},
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-fragment")

        assert result["parsed"]["fragment"] == "results"
        assert result["parsed"]["query_parameters"]["q"] == "test"


@pytest.mark.asyncio
async def test_get_serp_unfurl_no_query_params():
    """Test unfurling URL without query parameters"""
    mock_serp = {
        "_id": "test-no-params",
        "_source": {"capture": {"url": "https://example.com/search"}},
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-no-params")

        assert result["parsed"]["scheme"] == "https"
        assert result["parsed"]["netloc"] == "example.com"
        assert result["parsed"]["path"] == "/search"
        assert result["parsed"]["query_parameters"] == {}
        assert result["parsed"]["path_segments"] == ["search"]


@pytest.mark.asyncio
async def test_get_serp_unfurl_multiple_values():
    """Test unfurling URL with multiple values for same parameter"""
    mock_serp = {
        "_id": "test-multi",
        "_source": {
            "capture": {
                "url": "https://example.com/search?tag=python&tag=programming&q=test"
            }
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-multi")

        # Multiple values should be returned as list
        assert isinstance(result["parsed"]["query_parameters"]["tag"], list)
        assert "python" in result["parsed"]["query_parameters"]["tag"]
        assert "programming" in result["parsed"]["query_parameters"]["tag"]
        assert result["parsed"]["query_parameters"]["q"] == "test"


@pytest.mark.asyncio
async def test_get_serp_unfurl_complex_tld():
    """Test unfurling URL with complex TLD like co.uk"""
    mock_serp = {
        "_id": "test-complex-tld",
        "_source": {"capture": {"url": "https://www.google.co.uk/search?q=test"}},
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-complex-tld")

        domain_parts = result["parsed"]["domain_parts"]
        assert domain_parts["subdomain"] == "www"
        assert domain_parts["domain"] == "google"
        assert domain_parts["suffix"] == "co.uk"
        assert domain_parts["registered_domain"] == "google.co.uk"


@pytest.mark.asyncio
async def test_get_serp_unfurl_serp_not_found():
    """Test unfurling when SERP doesn't exist"""
    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=None)
    ):
        result = await aql.get_serp_unfurl("nonexistent-id")

        assert result is None


@pytest.mark.asyncio
async def test_get_serp_unfurl_special_chars():
    """Test unfurling URL with special characters in query"""
    mock_serp = {
        "_id": "test-special",
        "_source": {
            "capture": {"url": "https://google.com/search?q=how+to+use+%26+operator"}
        },
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-special")

        # & should be decoded from %26
        assert result["parsed"]["query_parameters"]["q"] == "how to use & operator"


@pytest.mark.asyncio
async def test_get_serp_unfurl_empty_path():
    """Test unfurling URL with root path"""
    mock_serp = {
        "_id": "test-empty-path",
        "_source": {"capture": {"url": "https://example.com/?q=test"}},
    }

    with patch(
        "app.services.aql_service.get_serp_by_id", new=AsyncMock(return_value=mock_serp)
    ):
        result = await aql.get_serp_unfurl("test-empty-path")

        assert result["parsed"]["path"] == "/"
        assert result["parsed"]["path_segments"] == []
