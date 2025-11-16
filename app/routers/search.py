"""
Routers for AQL Search API endpoints.

Provides FastAPI routes for:
- Basic SERP search
- Provider search
- Advanced search (with filters)
- Autocomplete (providers)
- Search by year
"""

from fastapi import APIRouter, Query, Request
from typing import Optional
from slowapi.util import get_remote_address
from slowapi.extension import Limiter
from app.services import aql_service

router = APIRouter()

# Limiter instance
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------
# 1. Basic Search
# ---------------------------------------------------------
@router.get("/search/basic")
@limiter.limit("10/minute")
async def search_basic(
    query: str = Query(..., description="Search term for SERPs"),
    size: int = Query(10, description="Number of results to return"),
    request: Optional[Request] = None,
):
    results = await aql_service.search_serps_basic(query=query, size=size)
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 2. Search Providers
# ---------------------------------------------------------
@router.get("/search/providers")
@limiter.limit("10/minute")
async def search_providers(
    name: str = Query(..., description="Provider name to search for"),
    size: int = Query(10, description="Number of results to return"),
    request: Optional[Request] = None,
):
    results = await aql_service.search_providers(name=name, size=size)
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 3. Advanced Search
# ---------------------------------------------------------
@router.get("/search/advanced")
@limiter.limit("10/minute")
async def search_advanced(
    query: str = Query(..., description="Search term"),
    provider_id: Optional[str] = Query(None, description="Filter by provider ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    size: int = Query(10, description="Number of results to return"),
    request: Optional[Request] = None,
):
    results = await aql_service.search_serps_advanced(
        query=query,
        provider_id=provider_id,
        year=year,
        status_code=status_code,
        size=size,
    )
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# 4. Autocomplete Providers
# ---------------------------------------------------------
@router.get("/autocomplete/providers")
@limiter.limit("10/minute")
async def autocomplete_providers(
    q: str = Query(..., min_length=2, description="Prefix for provider name"),
    size: int = Query(10, description="Number of suggestions to return"),
    request: Optional[Request] = None,
):
    suggestions = await aql_service.autocomplete_providers(q=q, size=size)
    return {"count": len(suggestions), "results": suggestions}


# ---------------------------------------------------------
# 5. Search by Year
# ---------------------------------------------------------
@router.get("/search/by-year")
@limiter.limit("10/minute")
async def search_by_year(
    query: str = Query(..., description="Search term"),
    year: int = Query(..., description="Year to filter results by"),
    size: int = Query(10, description="Number of results to return"),
    request: Optional[Request] = None,
):
    results = await aql_service.search_by_year(query=query, year=year, size=size)
    return {"count": len(results), "results": results}
