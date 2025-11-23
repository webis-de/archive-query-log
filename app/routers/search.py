"""
Routers for AQL Search API endpoints with global rate-limiting and error handling.

Provides FastAPI routes for:
- Basic SERP search
- Provider search
- Advanced search (with filters)
- Autocomplete (providers)
- Search by year
"""

from fastapi import APIRouter, Query, HTTPException, Request
from typing import Optional

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


# -------------------- Helper function --------------------
async def safe_search(coro):
    try:
        results = await coro

    except ConnectionError:
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")

    except ApiError:
        raise HTTPException(status_code=503, detail="Elasticsearch transport error")

    except BadRequestError:
        raise HTTPException(status_code=400, detail="Invalid request to Elasticsearch")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    if not results:
        raise HTTPException(status_code=404, detail="No results found")

    return results


# ---------------------------------------------------------
# 1. Basic Search
# ---------------------------------------------------------
@router.get("/search/basic")
@limiter.limit("10/minute")
async def search_basic(
    request: Request,
    query: str = Query(..., description="Search term for SERPs"),
    size: int = Query(10, description="Number of results to return"),
):
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")

    results = await safe_search(aql_service.search_serps_basic(query=query, size=size))
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 2. Search Providers
# ---------------------------------------------------------
@router.get("/search/providers")
@limiter.limit("10/minute")
async def search_providers(
    request: Request,
    name: str = Query(..., description="Provider name to search for"),
    size: int = Query(10, description="Number of results to return"),
):
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")

    results = await safe_search(aql_service.search_providers(name=name, size=size))
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 3. Advanced Search
# ---------------------------------------------------------
@router.get("/search/advanced")
@limiter.limit("10/minute")
async def search_advanced(
    request: Request,
    query: str = Query(..., description="Search term"),
    provider_id: Optional[str] = Query(None, description="Filter by provider ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    size: int = Query(10, description="Number of results to return"),
):
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")

    results = await safe_search(
        aql_service.search_serps_advanced(
            query=query,
            provider_id=provider_id,
            year=year,
            status_code=status_code,
            size=size,
        )
    )
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 4. Autocomplete Providers
# ---------------------------------------------------------
@router.get("/autocomplete/providers")
@limiter.limit("10/minute")
async def autocomplete_providers(
    request: Request,
    q: str = Query(..., min_length=2, description="Prefix for provider name"),
    size: int = Query(10, description="Number of suggestions to return"),
):
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")

    results = await safe_search(aql_service.autocomplete_providers(q=q, size=size))
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 5. Search by Year
# ---------------------------------------------------------
@router.get("/search/by-year")
@limiter.limit("10/minute")
async def search_by_year(
    request: Request,
    query: str = Query(..., description="Search term"),
    year: int = Query(..., description="Year to filter results by"),
    size: int = Query(10, description="Number of results to return"),
):
    if size <= 0:
        raise HTTPException(status_code=400, detail="Size must be a positive integer")

    results = await safe_search(
        aql_service.search_by_year(query=query, year=year, size=size)
    )
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 6. Search SERPs by ID
# ---------------------------------------------------------
@router.get("/serp/{serp_id}")
@limiter.limit("20/minute")
async def get_serp(request: Request, serp_id: str):
    print(f"[DEBUG] Fetching SERP ID: {serp_id}")
    result = await safe_search(aql_service.get_serp_by_id(serp_id))
    return result


# ---------------------------------------------------------
# 7. Get original URL
# ---------------------------------------------------------
@router.get("/serp/{serp_id}/original-url")
@limiter.limit("20/minute")
async def get_original_url(
    request: Request,
    serp_id: str,
    remove_tracking: bool = Query(
        False, description="Remove tracking parameters (utm_*, fbclid, etc.)"
    ),
):
    result = await safe_search(
        aql_service.get_serp_original_url(serp_id, remove_tracking)
    )
    return result


# ---------------------------------------------------------
# 7. Get memento URL
# ---------------------------------------------------------
@router.get("/serp/{serp_id}/memento-url")
@limiter.limit("20/minute")
async def get_memento_url(request: Request, serp_id: str):
    result = await safe_search(aql_service.get_serp_memento_url(serp_id))
    return result
