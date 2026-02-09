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
    TransportError,
    RequestError,
)

from archive_query_log.browser.services import aql_service
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
    direct_links = "direct_links"
    unbranded = "unbranded"


# -------------------- Helper function --------------------
async def safe_search(coro, allow_empty=False):
    """Handle common Elasticsearch exceptions

    Args:
        coro: Coroutine to execute
        allow_empty: If True, empty results won't raise 404
    """
    try:
        results = await coro

    except RequestError:
        raise HTTPException(status_code=400, detail="Invalid request to Elasticsearch")

    except ConnectionError:
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")

    except TransportError:
        raise HTTPException(status_code=503, detail="Elasticsearch transport error")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    if not results and not allow_empty:
        raise HTTPException(status_code=404, detail="No results found")

    return results


async def safe_search_paginated(coro):
    """Handle common Elasticsearch exceptions for paginated endpoints (allows empty results)"""
    try:
        results = await coro

    except RequestError:
        raise HTTPException(status_code=400, detail="Invalid request to Elasticsearch")

    except ConnectionError:
        raise HTTPException(status_code=503, detail="Elasticsearch connection failed")

    except TransportError:
        raise HTTPException(status_code=503, detail="Elasticsearch transport error")

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

    return results


# ---------------------------------------------------------
# UNIFIED SEARCH ENDPOINT
# ---------------------------------------------------------
@router.get("/serps")
@limiter.limit("60/minute")
async def unified_search(
    request: Request,
    query: str = Query(..., description="Search term"),
    page_size: int = Query(10, description="Results per page (10, 20, or 50)"),
    page: int = Query(1, description="Page number (starting at 1)"),
    provider_id: Optional[str] = Query(None, description="Filter by provider ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    status_code: Optional[int] = Query(None, description="Filter by HTTP status code"),
    advanced_mode: bool = Query(
        False,
        description=(
            "Enable advanced search with boolean operators (AND, OR), "
            "phrase search (quotes), and wildcards (*, ?)"
        ),
    ),
    fuzzy: bool = Query(
        False,
        description=(
            "Enable fuzzy matching to find similar queries and handle typos. "
            "Matches queries with up to 2 character differences."
        ),
    ),
    fuzziness: str = Query(
        "AUTO",
        description=(
            "Control fuzzy matching tolerance. Options: AUTO (default), 0 (exact), 1, 2. "
            "AUTO uses 0 for 1-2 chars, 1 for 3-5 chars,"
            "2 for 6+ chars. Only applies when fuzzy=true."
        ),
    ),
    expand_synonyms: bool = Query(
        False,
        description=(
            "Enable synonym-based query expansion to find related terms. "
            "Example: 'climate' also matches 'global warming', 'climate change'."
        ),
    ),
):
    """
    Unified search endpoint for SERPs with pagination.

    Examples:
    - Basic search: /api/serps?query=climate+change
    - With page size: /api/serps?query=climate&page_size=20
    - Advanced search: /api/serps?query=climate&year=2024&provider_id=google&page_size=50
    - Advanced mode: /api/serps?query="climate change" AND renewable&advanced_mode=true
    - Wildcard search: /api/serps?query=climat*&advanced_mode=true
    - Boolean search: /api/serps?query=(renewable OR solar) AND energy&advanced_mode=true
    """
    # Validate page_size and page
    valid_sizes = [10, 20, 50, 100, 1000]
    if page_size not in valid_sizes:
        raise HTTPException(
            status_code=400, detail=f"page_size must be one of {valid_sizes}"
        )
    if page <= 0:
        raise HTTPException(status_code=400, detail="page must be a positive integer")

    # Validate fuzziness parameter
    valid_fuzziness = ["AUTO", "0", "1", "2"]
    if fuzziness not in valid_fuzziness:
        raise HTTPException(
            status_code=400, detail=f"fuzziness must be one of {valid_fuzziness}"
        )

    # compute ES offset
    from_ = (page - 1) * page_size

    # Perform search
    if provider_id or year or status_code:
        search_result = await safe_search_paginated(
            aql_service.search_advanced(
                query=query,
                provider_id=provider_id,
                year=year,
                status_code=status_code,
                size=page_size,
                from_=from_,
                advanced_mode=advanced_mode,
                fuzzy=fuzzy,
                fuzziness=fuzziness,
                expand_synonyms=expand_synonyms,
            )
        )
    else:
        search_result = await safe_search_paginated(
            aql_service.search_basic(
                query=query,
                size=page_size,
                from_=from_,
                advanced_mode=advanced_mode,
                fuzzy=fuzzy,
                fuzziness=fuzziness,
                expand_synonyms=expand_synonyms,
            )
        )

    # Extract results and total count
    hits = search_result["hits"]
    total_count = search_result["total"]
    suggestions = search_result.get("suggestions", [])

    # Calculate pagination info
    total_pages = (total_count + page_size - 1) // page_size  # Ceiling division

    response = {
        "query": query,
        "count": len(hits),
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "advanced_mode": advanced_mode,
        "fuzzy": fuzzy,
        "fuzziness": fuzziness if fuzzy else None,
        "expand_synonyms": expand_synonyms,
        "pagination": {
            "current_results": len(hits),
            "total_results": total_count,
            "results_per_page": page_size,
            "total_pages": total_pages,
            "current_page": page,
        },
        "results": hits,
    }

    # Add suggestions if available
    if suggestions:
        response["did_you_mean"] = suggestions

    return response


# ---------------------------------------------------------
# SUGGESTIONS ENDPOINT
# ---------------------------------------------------------
@router.get("/suggestions")
@limiter.limit("60/minute")
async def suggestions(
    request: Request,
    prefix: str = Query(..., description="Search query prefix"),
    size: int = Query(10, description="Number of suggestions", ge=1, le=50),
    last_n_months: int | None = Query(36, description="Limit to last N months"),
):
    """Return popular search suggestions based on prefix."""
    result = await safe_search(
        aql_service.search_suggestions(prefix, last_n_months, size)
    )
    return result


# ---------------------------------------------------------
# PREVIEW / SUGGESTIONS ENDPOINT
# ---------------------------------------------------------
@router.get("/serps/preview")
@limiter.limit("60/minute")
async def serps_preview(
    request: Request,
    query: str = Query(..., description="Search term for preview"),
    top_n_queries: int = Query(10, description="Number of top query suggestions"),
    interval: str = Query("month", description="Histogram interval (day, week, month)"),
    top_providers: int = Query(5, description="Number of top providers to return"),
    top_archives: int = Query(5, description="Number of top archives to return"),
    last_n_months: int | None = Query(
        36, description="Limit histogram to last N months (optional)"
    ),
):
    """Return preview/summary statistics for a given query (lightweight aggregations)."""
    result = await safe_search_paginated(
        aql_service.preview_search(
            query=query,
            top_n_queries=top_n_queries,
            interval=interval,
            top_providers=top_providers,
            top_archives=top_archives,
            last_n_months=last_n_months,
        )
    )
    return result


# ---------------------------------------------------------
# TIMELINE ENDPOINT
# ---------------------------------------------------------
@router.get("/serps/timeline")
@limiter.limit("60/minute")
async def serps_timeline(
    request: Request,
    query: str = Query(..., description="Search term for timeline"),
    provider_id: Optional[str] = Query(None, description="Filter by provider ID"),
    archive_id: Optional[str] = Query(
        None, description="Filter by archive memento_api_url"
    ),
    interval: str = Query("month", description="Histogram interval (day, week, month)"),
    last_n_months: int | None = Query(
        36, description="Limit histogram to last N months (optional)"
    ),
):
    """Return a date histogram (counts only) for the given query,
    optionally filtered by provider and archive."""
    # Validate interval
    valid_intervals = {"day", "week", "month"}
    if interval.lower() not in valid_intervals:
        raise HTTPException(
            status_code=400, detail=f"interval must be one of {sorted(valid_intervals)}"
        )

    # Validate last_n_months
    if last_n_months is not None and last_n_months < 0:
        raise HTTPException(
            status_code=400, detail="last_n_months must be >= 0 or null"
        )

    result = await safe_search_paginated(
        aql_service.serps_timeline(
            query=query,
            provider_id=provider_id,
            archive_id=archive_id,
            interval=interval,
            last_n_months=last_n_months,
        )
    )
    return result


# ---------------------------------------------------------
# SERP COMPARISON ENDPOINT
# ---------------------------------------------------------
@router.get("/serps/compare")
@limiter.limit("60/minute")
async def compare_serps(
    request: Request,
    ids: str = Query(
        ...,
        description="Comma-separated list of SERP IDs to compare (2-5 IDs)",
        examples=["id1,id2,id3"],
    ),
):
    """
    Compare multiple SERPs side by side.

    Returns detailed comparison including:
    - Full SERP data for each ID
    - Common and unique URLs across SERPs
    - Ranking differences for common URLs
    - Similarity metrics (Jaccard similarity, Spearman correlation)
    - Provider, timestamp, and query comparison
    - Statistical summary

    Examples:
    - Compare 2 SERPs: /api/serps/compare?ids=abc123,def456
    - Compare 3 SERPs: /api/serps/compare?ids=abc,def,ghi
    - Compare 5 SERPs: /api/serps/compare?ids=id1,id2,id3,id4,id5
    """
    # Parse and validate IDs
    serp_ids = [id.strip() for id in ids.split(",") if id.strip()]

    if len(serp_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 SERP IDs are required for comparison",
        )

    if len(serp_ids) > 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum 5 SERPs can be compared at once",
        )

    # Check for duplicate IDs
    if len(serp_ids) != len(set(serp_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate SERP IDs are not allowed",
        )

    # Perform comparison
    result = await safe_search(aql_service.compare_serps(serp_ids))

    return result


# GET ALL PROVIDERS ENDPOINT
# ---------------------------------------------------------
@router.get("/providers")
@limiter.limit("60/minute")
async def get_all_providers(
    request: Request,
    size: int = Query(0, description="Number of providers to return (0 = all)"),
):
    """
    Get a list of (all) available search providers.

    Example:
    - Get all providers: /api/providers or /api/providers?size=0
    - Limit results: /api/providers?size=uint
    """
    if size < 0:
        raise HTTPException(
            status_code=400, detail="Size must be 0 (for all) or a positive integer"
        )

    results = await safe_search(
        aql_service.get_all_providers(size=size), allow_empty=True
    )
    return {"count": len(results), "results": results}


# ---------------------------------------------------------
# GET PROVIDER BY ID ENDPOINT
# ---------------------------------------------------------
@router.get("/providers/{provider_id}")
@limiter.limit("60/minute")
async def get_provider_by_id(request: Request, provider_id: str):
    """
    Get a single provider document by its ID.

    Example:
    - Get provider: /api/provider/google
    """
    result = await safe_search(aql_service.get_provider_by_id(provider_id))
    # Return the raw ES document to stay consistent with other detail endpoints
    return {"provider_id": result.get("_id"), "provider": result}


# ---------------------------------------------------------
# PROVIDER STATISTICS ENDPOINT
# ---------------------------------------------------------
@router.get("/providers/{provider_id}/statistics")
@limiter.limit("60/minute")
async def get_provider_statistics(
    request: Request,
    provider_id: str,
    interval: str = Query("month", description="Histogram interval (day, week, month)"),
    last_n_months: int | None = Query(
        36, description="Limit histogram to last N months (optional)"
    ),
):
    """
    Get descriptive statistics for a search provider.

    Returns statistics about SERPs captured from this provider, including:
    - Total number of archived SERPs
    - Number of unique queries
    - Date range of captures
    - Top web archives used by this provider
    - Date histogram of captures over time

    Example:
    - /api/providers/google/statistics
    - /api/providers/google/statistics?interval=week&last_n_months=12
    """
    result = await safe_search(
        aql_service.get_provider_statistics(
            provider_id=provider_id,
            interval=interval,
            last_n_months=last_n_months,
        )
    )
    return result


# ---------------------------------------------------------
# ARCHIVE STATISTICS ENDPOINT (must be before general archive detail endpoint)
# ---------------------------------------------------------
@router.get("/archives/{archive_id:path}/statistics")
@limiter.limit("60/minute")
async def get_archive_statistics(
    request: Request,
    archive_id: str,
    interval: str = Query("month", description="Histogram interval (day, week, month)"),
    last_n_months: int | None = Query(
        36, description="Limit histogram to last N months (optional)"
    ),
):
    """
    Get descriptive statistics for a web archive.

    Returns statistics about SERPs in this archive, including:
    - Total number of archived SERPs
    - Number of unique queries
    - Date range of captures
    - Top search providers in this archive
    - Date histogram of captures over time

    Example:
    - /api/archives/https://web.archive.org/web/statistics
    - /api/archives/https://web.archive.org/web/statistics?interval=week&last_n_months=12
    """
    result = await safe_search(
        aql_service.get_archive_statistics(
            archive_id=archive_id,
            interval=interval,
            last_n_months=last_n_months,
        )
    )
    return result


# New canonical archive detail endpoint using the same ID as the list
@router.get("/archives/{archive_id:path}")
@limiter.limit("60/minute")
async def get_archive_by_memento_url(request: Request, archive_id: str):
    """
    Get archive metadata by its canonical ID (memento_api_url), matching the
    `id` field returned by /api/archives.

    This enables stable deep-links without relying on ES internal document IDs.
    Example: /api/archives/https://web.archive.org/web
    """
    result = await safe_search(aql_service.get_archive_metadata(archive_id))
    return result


# ---------------------------------------------------------
# UNIFIED SERP DETAIL ENDPOINT
# ---------------------------------------------------------
@router.get("/serps/{serp_id}")
@limiter.limit("60/minute")
async def get_serp_unified(
    request: Request,
    serp_id: str,
    view: Optional[str] = Query(
        None,
        description="View mode: raw (default), unbranded, or snapshot. "
        "Use /api/serps/{id}/views to see available options.",
    ),
    include: Optional[str] = Query(
        None,
        description="Comma-separated list of fields: original_url, memento_url, "
        "related, unfurl, direct_links, unbranded",
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
    Get SERP by ID with optional additional fields and view modes.

    View modes:
    - raw (default): Full SERP data
    - unbranded: Normalized provider-agnostic view
    - snapshot: Redirect to web archive memento

    Examples:
    - Basic: /api/serp/123
    - Unbranded view: /api/serp/123?view=unbranded
    - Snapshot redirect: /api/serp/123?view=snapshot
    - With original URL: /api/serp/123?include=original_url
    - With tracking removed: /api/serp/123?include=original_url&remove_tracking=true
    - With direct links: /api/serp/123?include=direct_links
    - Multiple fields: /api/serp/123?include=memento_url,related,unfurl,direct_links,unbranded
    - Related SERPs: /api/serp/123?include=related&related_size=5&same_provider=true
    """
    from archive_query_log.browser.schemas.aql import SERPViewType
    from fastapi.responses import RedirectResponse

    if related_size <= 0:
        raise HTTPException(
            status_code=400, detail="related_size must be a positive integer"
        )

    # Handle view parameter
    if view:
        view = view.lower()

        # Validate view type
        valid_views = {v.value for v in SERPViewType}
        if view not in valid_views:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid view type: {view}. Valid options: {', '.join(valid_views)}",
            )

        # Handle unbranded view
        if view == SERPViewType.unbranded.value:
            unbranded_data = await safe_search(aql_service.get_serp_unbranded(serp_id))
            return {
                "serp_id": serp_id,
                "view": SERPViewType.unbranded.value,
                "data": unbranded_data,
            }

        # Handle snapshot view - redirect to web archive memento
        elif view == SERPViewType.snapshot.value:
            memento_data = await safe_search(aql_service.get_serp_memento_url(serp_id))
            memento_url = memento_data.get("memento_url")
            if not memento_url:
                raise HTTPException(
                    status_code=404,
                    detail="Memento URL not available for this SERP",
                )
            return RedirectResponse(url=memento_url)

        # view == 'raw' falls through to normal processing

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

    if IncludeField.direct_links.value in include_fields:
        direct_links_data = await safe_search(
            aql_service.get_serp_direct_links(serp_id)
        )
        response["direct_links_count"] = direct_links_data.get("direct_links_count")
        response["direct_links"] = direct_links_data.get("direct_links")

    if IncludeField.unbranded.value in include_fields:
        unbranded_data = await safe_search(aql_service.get_serp_unbranded(serp_id))
        response["unbranded"] = unbranded_data

    return response


# ---------------------------------------------------------
# SERP VIEW SWITCHER ENDPOINT
# ---------------------------------------------------------
@router.get("/serps/{serp_id}/views")
@limiter.limit("60/minute")
async def get_serp_views(request: Request, serp_id: str):
    """
    Get available view options for a SERP to enable easy switching between views.

    Returns metadata about available views:
    - Raw (full data) - always available
    - Unbranded (normalized) - available if results exist
    - Snapshot (web archive) - available if memento URL can be constructed

    This endpoint helps researchers switch between different SERP representations,
    similar to switching between "plain text" and "full HTML" views.

    Examples:
    - /api/serps/123/views
    """
    result = await safe_search(aql_service.get_serp_view_options(serp_id))
    return result


# ---------------------------------------------------------
# ARCHIVE DETAIL ENDPOINTS
# ---------------------------------------------------------
@router.get("/archives")
@limiter.limit("60/minute")
async def list_archives(
    request: Request,
    limit: int = Query(
        100, description="Maximum number of archives to return", ge=1, le=1000
    ),
    size: Optional[int] = Query(
        None, description="Alias for limit (for backwards compatibility)"
    ),
):
    """
    List all available web archives in the dataset.

    Returns archive metadata including:
    - Archive name
    - Memento API URL
    - CDX API URL
    - Homepage URL
    - Number of SERPs in this archive

    Example:
    - /api/archives
    - /api/archives?limit=50
    """
    # Support legacy "size" param as alias for limit
    effective_limit = limit
    if size is not None:
        # Validate legacy size value similarly to limit
        if size < 1 or size > 1000:
            raise HTTPException(status_code=422, detail="Invalid size parameter")
        effective_limit = size

    svc_result = await safe_search_paginated(
        aql_service.list_all_archives(size=effective_limit)
    )
    # Enforce limit/size at router layer as a safety net
    archives_list = list(svc_result.get("archives", []))[:effective_limit]

    return {
        "total": svc_result.get("total", 0),
        "archives": archives_list,
    }
