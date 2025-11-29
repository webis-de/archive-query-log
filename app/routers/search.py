# Neue vereinheitlichte Router-Datei
"""
Unified AQL Search API endpoints with global rate-limiting and error handling.

Provides FastAPI routes for:
- Unified search endpoint for SERPs and providers
- Unified SERP detail endpoint with flexible includes
"""

from fastapi import APIRouter, Query, HTTPException, Request
from typing import Optional
from enum import Enum

# Elasticsearch Exceptions
from elasticsearch import (
    ConnectionError,
    ApiError,
    BadRequestError,
)

from app.services import aql_service
from slowapi.util import get_remote_address
from slowapi.extension import Limiter

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# -------------------- Enums --------------------
class SearchType(str, Enum):
    """Type of search to perform"""

    serps = "serps"
    providers = "providers"


class IncludeField(str, Enum):
    """Fields that can be included in SERP response"""

    original_url = "original_url"
    memento_url = "memento_url"
    related = "related"
    unfurl = "unfurl"


# -------------------- Helper function --------------------
async def safe_search(coro):
    """Handle common Elasticsearch exceptions"""
    try:
        results = await coro

    except BadRequestError:
        raise HTTPException(status_code=400, detail="Invalid request to Elasticsearch")

    except ConnectionError:
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")

    except ApiError:
        raise HTTPException(status_code=503, detail="Elasticsearch transport error")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    if not results:
        raise HTTPException(status_code=404, detail="No results found")

    return results


# ---------------------------------------------------------
# UNIFIED SEARCH ENDPOINT
# ---------------------------------------------------------
@router.get("/serps")
@limiter.limit("10/minute")
async def unified_search(
    request: Request,
    query: str = Query(..., description="Search term"),
    size: int = Query(10, description="Number of results to return"),
    provider_id: Optional[str] = Query(None, description="Filter by provider ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
):
    """
    Unified search endpoint for SERPs and providers.

    Examples:
    - Basic search: /api/serps?query=climate+change
    - Advanced search: /api/serps?query=climate&year=2024&provider_id=google
    """
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")

    # if type == SearchType.providers:
    #    if autocomplete:
    #        results = await safe_search(
    #            aql_service.autocomplete_providers(q=query, size=size)
    #        )
    #        return {"count": len(results), "results": results, "autocomplete": True}
    #    else:
    #        results = await safe_search(
    #            aql_service.search_providers(name=query, size=size)
    #        )
    #        return {"count": len(results), "results": results}

    # elif type == SearchType.serps:
    # if autocomplete:
    #    raise HTTPException(
    #        status_code=400,
    #        detail="Autocomplete is not supported for SERP search. Use type=providers instead.",
    #    )

    if provider_id or year or status_code:
        results = await safe_search(
            aql_service.search_advanced(
                query=query,
                provider_id=provider_id,
                year=year,
                status_code=status_code,
                size=size,
            )
        )
    else:
        results = await safe_search(aql_service.search_basic(query=query, size=size))

    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# UNIFIED SERP DETAIL ENDPOINT
# ---------------------------------------------------------
@router.get("/serp/{serp_id}")
@limiter.limit("20/minute")
async def get_serp_unified(
    request: Request,
    serp_id: str,
    include: Optional[str] = Query(
        None,
        description="Comma-separated list of fields: original_url, memento_url, related, unfurl",
    ),
    remove_tracking: bool = Query(
        False,
        description="Remove tracking parameters from original URL (requires include=original_url)",
    ),
    related_size: int = Query(
        10, description="Number of related SERPs to return (requires include=related)"
    ),
    same_provider: bool = Query(
        False,
        description="Only return related SERPs from same provider (requires include=related)",
    ),
):
    """
    Get SERP by ID with optional additional fields.

    Examples:
    - Basic: /api/serp/123
    - With original URL: /api/serp/123?include=original_url
    - With tracking removed: /api/serp/123?include=original_url&remove_tracking=true
    - Multiple fields: /api/serp/123?include=original_url,memento_url,related,unfurl
    - Related SERPs: /api/serp/123?include=related&related_size=5&same_provider=true
    """
    if related_size <= 0:
        raise HTTPException(
            status_code=400, detail="related_size must be a positive integer"
        )

    serp_data = await safe_search(aql_service.get_serp_by_id(serp_id))

    include_fields = set()
    if include:
        include_fields = set(field.strip() for field in include.split(","))

        valid_fields = {field.value for field in IncludeField}
        invalid_fields = include_fields - valid_fields
        if invalid_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid include fields: {', '.join(invalid_fields)}. Valid options: {', '.join(valid_fields)}",  # noqa: E501
            )

    response = {
        "serp_id": serp_data["_id"],
        "serp": serp_data,
    }

    if IncludeField.original_url.value in include_fields:
        url_data = await safe_search(
            aql_service.get_serp_original_url(serp_id, remove_tracking)
        )
        response["original_url"] = url_data.get("original_url")
        if remove_tracking and "url_without_tracking" in url_data:
            response["url_without_tracking"] = url_data["url_without_tracking"]

    if IncludeField.memento_url.value in include_fields:
        memento_data = await safe_search(aql_service.get_serp_memento_url(serp_id))
        response["memento_url"] = memento_data.get("memento_url")

    if IncludeField.related.value in include_fields:
        related_serps = await safe_search(
            aql_service.get_related_serps(serp_id, related_size, same_provider)
        )
        response["related"] = {"count": len(related_serps), "serps": related_serps}

    if IncludeField.unfurl.value in include_fields:
        unfurl_data = await safe_search(aql_service.get_serp_unfurl(serp_id))
        response["unfurl"] = unfurl_data.get("parsed")
        response["unfurl_web"] = (
            "https://dfir.blog/unfurl/?"
            + f"url={serp_data['_source']['capture']['url']}"
        )

    return response


# ---------------------------------------------------------
# LEGACY ENDPOINTS (DEPRECATED - for backwards compatibility)
# ---------------------------------------------------------
# Keep old endpoints but mark as deprecated
@router.get("/search/basic", deprecated=True)
@limiter.limit("10/minute")
async def search_basic_legacy(
    request: Request,
    query: str = Query(..., description="Search term for SERPs"),
    size: int = Query(10, description="Number of results to return"),
):
    """[DEPRECATED] Legacy basic SERP search"""
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")
    results = await safe_search(aql_service.search_basic(query=query, size=size))
    return {"count": len(results), "results": results}


@router.get("/search/providers", deprecated=True)
@limiter.limit("10/minute")
async def search_providers_legacy(
    request: Request,
    name: str = Query(..., description="Provider name to search for"),
    size: int = Query(10, description="Number of results to return"),
):
    """[DEPRECATED] Legacy provider search"""
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")
    results = await safe_search(aql_service.search_providers(name=name, size=size))
    return {"count": len(results), "results": results}


@router.get("/search/advanced", deprecated=True)
@limiter.limit("10/minute")
async def search_advanced_legacy(
    request: Request,
    query: str = Query(..., description="Search term"),
    provider_id: Optional[str] = Query(None, description="Filter by provider ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    size: int = Query(10, description="Number of results to return"),
):
    """[DEPRECATED] Legacy advanced SERP search"""
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")
    results = await safe_search(
        aql_service.search_advanced(
            query=query,
            provider_id=provider_id,
            year=year,
            status_code=status_code,
            size=size,
        )
    )
    return {"count": len(results), "results": results}


@router.get("/search/by-year", deprecated=True)
@limiter.limit("10/minute")
async def search_by_year_legacy(
    request: Request,
    query: str = Query(..., description="Search term"),
    year: int = Query(..., description="Year to filter results by"),
    size: int = Query(10, description="Number of results to return"),
):
    """[DEPRECATED] Legacy year-filtered SERP search"""
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")
    results = await safe_search(
        aql_service.search_by_year(query=query, year=year, size=size)
    )
    return {"count": len(results), "results": results}


@router.get("/autocomplete/providers", deprecated=True)
@limiter.limit("10/minute")
async def autocomplete_providers_legacy(
    request: Request,
    q: str = Query(..., min_length=2, description="Prefix for provider name"),
    size: int = Query(10, description="Number of suggestions to return"),
):
    """[DEPRECATED] Legacy providers autocomplete"""
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")
    results = await safe_search(aql_service.autocomplete_providers(q=q, size=size))
    return {"count": len(results), "results": results, "autocomplete": True}


@router.get("/serp/{serp_id}/original-url", deprecated=True)
@limiter.limit("20/minute")
async def get_original_url_legacy(
    request: Request,
    serp_id: str,
    remove_tracking: bool = Query(False, description="Remove tracking parameters"),
):
    """[DEPRECATED] Use /api/serp/{id}?include=original_url&remove_tracking=true instead"""
    result = await safe_search(
        aql_service.get_serp_original_url(serp_id, remove_tracking)
    )
    return result


@router.get("/serp/{serp_id}/memento-url", deprecated=True)
@limiter.limit("20/minute")
async def get_memento_url_legacy(request: Request, serp_id: str):
    """[DEPRECATED] Use /api/serp/{id}?include=memento_url instead"""
    result = await safe_search(aql_service.get_serp_memento_url(serp_id))
    return result


@router.get("/serp/{serp_id}/related", deprecated=True)
@limiter.limit("20/minute")
async def get_related_serps_legacy(
    request: Request,
    serp_id: str,
    size: int = Query(10, description="Number of related SERPs to return"),
    same_provider: bool = Query(
        False, description="Only return SERPs from the same provider"
    ),
):
    """[DEPRECATED] Use /api/serp/{id}?include=related&related_size=...&same_provider=... instead"""
    result = await safe_search(
        aql_service.get_related_serps(serp_id, size, same_provider)
    )
    return {"count": len(result), "results": result}


@router.get("/serp/{serp_id}/unfurl", deprecated=True)
@limiter.limit("20/minute")
async def get_serp_unfurl_legacy(request: Request, serp_id: str):
    """[DEPRECATED] Use /api/serp/{id}?include=unfurl instead"""
    result = await safe_search(aql_service.get_serp_unfurl(serp_id))
    return result
