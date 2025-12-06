"""
Service module for Archive Query Log (AQL) Elasticsearch operations.

Contains all functions used by the search router:
- Basic SERP search
- Provider search
- Advanced search
- Autocomplete providers
- Search by year
"""

from typing import List, Optional, Any, Dict
from app.core.elastic import get_es_client
from app.utils.url_cleaner import remove_tracking_parameters


# ---------------------------------------------------------
# 1. Basic SERP Search
# ---------------------------------------------------------
async def search_basic(query: str, size: int = 10) -> dict:
    """
    Simple full-text search in SERPs by query string.

    Returns:
        dict with keys:
            - hits: List of search results
            - total: Total number of results found
    """
    es = get_es_client()
    body = {"query": {"match": {"url_query": query}}, "size": size}
    response = await es.search(index="aql_serps", body=body)
    hits: List[Any] = response["hits"]["hits"]
    total = response["hits"]["total"]

    # Handle both old and new Elasticsearch response formats
    if isinstance(total, dict):
        total_count = total.get("value", 0)
    else:
        total_count = total

    return {"hits": hits, "total": total_count}


# ---------------------------------------------------------
# 2. Provider Search
# ---------------------------------------------------------
async def search_providers(name: str, size: int = 10) -> List[Any]:
    """
    Search for providers by name.
    """
    es = get_es_client()
    body = {"query": {"match": {"name": name}}, "size": size}
    response = await es.search(index="aql_providers", body=body)
    hits: List[Any] = response["hits"]["hits"]
    return hits


# ---------------------------------------------------------
# 3. Advanced SERP Search
# ---------------------------------------------------------
async def search_advanced(
    query: str,
    provider_id: Optional[str] = None,
    year: Optional[int] = None,
    status_code: Optional[int] = None,
    size: int = 10,
) -> dict:
    """
    Perform advanced search on SERPs with optional filters:
    - provider_id: filter by provider
    - year: filter by capture year
    - status_code: filter by HTTP status code

    Returns:
        dict with keys:
            - hits: List of search results
            - total: Total number of results found
    """
    es = get_es_client()

    bool_query: Dict[str, Any] = {
        "must": [{"match": {"url_query": query}}],
        "filter": [],
    }

    if provider_id:
        bool_query["filter"].append({"term": {"provider.id": provider_id}})
    if year:
        bool_query["filter"].append(
            {
                "range": {
                    "capture.timestamp": {
                        "gte": f"{year}-01-01T00:00:00+00:00",
                        "lt": f"{year + 1}-01-01T00:00:00+00:00",
                    }
                }
            }
        )
    if status_code:
        bool_query["filter"].append({"term": {"capture.status_code": status_code}})

    body = {"query": {"bool": bool_query}, "size": size}
    response = await es.search(index="aql_serps", body=body)
    hits: List[Any] = response["hits"]["hits"]
    total = response["hits"]["total"]

    # Handle both old and new Elasticsearch response formats
    if isinstance(total, dict):
        total_count = total.get("value", 0)
    else:
        total_count = total

    return {"hits": hits, "total": total_count}


# ---------------------------------------------------------
# 4. Autocomplete Providers
# ---------------------------------------------------------
async def autocomplete_providers(q: str, size: int = 10) -> List[Any]:
    """
    Autocomplete provider names by prefix (case-insensitive).
    Returns a list of provider names.
    """
    es = get_es_client()
    body = {"query": {"prefix": {"name": q.lower()}}, "_source": ["name"], "size": size}
    response = await es.search(index="aql_providers", body=body)
    suggestions = [hit["_source"]["name"] for hit in response["hits"]["hits"]]
    return suggestions


# ---------------------------------------------------------
# 5. Search SERPs by Year
# ---------------------------------------------------------
async def search_by_year(query: str, year: int, size: int = 10) -> dict:
    """
    Search SERPs containing a keyword in a specific year.
    """
    return await search_advanced(query=query, year=year, size=size)


# ---------------------------------------------------------
# 6. Get SERP by ID
# ---------------------------------------------------------
async def get_serp_by_id(serp_id: str) -> Any | None:
    """Fetch a single SERP by ID from Elasticsearch."""
    es = get_es_client()
    try:
        response = await es.get(index="aql_serps", id=serp_id)
        return response
    except Exception:
        return None


# ---------------------------------------------------------
# 7. Get original URL
# ---------------------------------------------------------
async def get_serp_original_url(
    serp_id: str, remove_tracking: bool = False
) -> dict | None:
    """Get the original SERP URL from a SERP by ID."""
    serp = await get_serp_by_id(serp_id)
    if not serp:
        return None

    original_url = serp["_source"]["capture"]["url"]
    response = {"serp_id": serp["_id"], "original_url": original_url}

    if remove_tracking:
        response["url_without_tracking"] = remove_tracking_parameters(original_url)

    return response


# ---------------------------------------------------------
# 8. Get memento URL
# ---------------------------------------------------------
async def get_serp_memento_url(serp_id: str) -> dict | None:
    """Get the memento SERP URL from a SERP by ID."""
    from datetime import datetime

    serp = await get_serp_by_id(serp_id)
    if not serp:
        return None

    base_url = serp["_source"]["archive"]["memento_api_url"]
    timestamp_str = serp["_source"]["capture"]["timestamp"]
    capture_url = serp["_source"]["capture"]["url"]

    timestamp = datetime.fromisoformat(timestamp_str.replace("+00:00", "+00:00"))
    formatted_timestamp = timestamp.strftime("%Y%m%d%H%M%S")
    memento_url = f"{base_url}/{formatted_timestamp}/{capture_url}"

    return {"serp_id": serp["_id"], "memento_url": memento_url}


# ---------------------------------------------------------
# 9. Get related SERPs
# ---------------------------------------------------------
async def get_related_serps(
    serp_id: str, size: int = 10, same_provider: bool = False
) -> List[Any]:
    """Get related SERPs by ID."""

    serp = await get_serp_by_id(serp_id)
    if not serp:
        return []
    query = serp["_source"]["url_query"]
    provider_id = serp["_source"]["provider"]["id"] if same_provider else None

    # add 1 to size for the original serp
    results = await search_advanced(query=query, size=size + 1, provider_id=provider_id)

    # only use results that are not the original serp
    related = [hit for hit in results if hit["_id"] != serp_id]
    return related[:size]


# ---------------------------------------------------------
# 10. Unfurl SERP URL
# ---------------------------------------------------------
async def get_serp_unfurl(serp_id: str) -> dict | None:
    """
    Parse and unfurl the SERP URL into its components.

    Returns structured breakdown of URL with:
    - Decoded query parameters
    - Domain parts (subdomain, domain, TLD)
    - Path segments
    - Port (if present)
    """
    from app.utils.url_unfurler import unfurl

    serp = await get_serp_by_id(serp_id)
    if not serp:
        return None

    original_url = serp["_source"]["capture"]["url"]
    unfurled_url = unfurl(original_url)

    return {
        "serp_id": serp["_id"],
        "original_url": original_url,
        "parsed": unfurled_url,
    }


# ---------------------------------------------------------
# 11. Get direct links from SERP
# ---------------------------------------------------------
async def get_serp_direct_links(serp_id: str) -> dict | None:
    """
    Extract direct links/results from a SERP.

    Returns all search result links from the SERP with:
    - URL of each result
    - Title/snippet (if available)
    - Position in SERP
    """
    serp = await get_serp_by_id(serp_id)
    if not serp:
        return None

    source = serp["_source"]
    direct_links = []

    # Extract direct links from results if they exist in the SERP data
    if "results" in source:
        for idx, result in enumerate(source["results"]):
            direct_links.append(
                {
                    "position": idx + 1,
                    "url": result.get("url"),
                    "title": result.get("title"),
                    "snippet": result.get("snippet", result.get("description")),
                }
            )

    return {
        "serp_id": serp["_id"],
        "direct_links_count": len(direct_links),
        "direct_links": direct_links,
    }
