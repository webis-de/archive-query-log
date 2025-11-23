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
async def search_serps_basic(query: str, size: int = 10) -> List[Any]:
    """
    Simple full-text search in SERPs by query string.
    """
    es = get_es_client()
    body = {"query": {"match": {"url_query": query}}, "size": size}
    response = await es.search(index="aql_serps", body=body)
    hits: List[Any] = response["hits"]["hits"]
    return hits


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
async def search_serps_advanced(
    query: str,
    provider_id: Optional[str] = None,
    year: Optional[int] = None,
    status_code: Optional[int] = None,
    size: int = 10,
) -> List[Any]:
    """
    Perform advanced search on SERPs with optional filters:
    - provider_id: filter by provider
    - year: filter by capture year
    - status_code: filter by HTTP status code
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
    return hits


# ---------------------------------------------------------
# 4. Autocomplete Providers
# ---------------------------------------------------------
async def autocomplete_providers(q: str, size: int = 10) -> List[Any]:
    """
    Autocomplete provider names by prefix (case-insensitive).
    """
    es = get_es_client()
    body = {"query": {"prefix": {"name": q.lower()}}, "_source": ["name"], "size": size}
    response = await es.search(index="aql_providers", body=body)
    suggestions = [hit["_source"]["name"] for hit in response["hits"]["hits"]]
    return suggestions


# ---------------------------------------------------------
# 5. Search SERPs by Year
# ---------------------------------------------------------
async def search_by_year(query: str, year: int, size: int = 10) -> List[Any]:
    """
    Search SERPs containing a keyword in a specific year.
    """
    return await search_serps_advanced(query=query, year=year, size=size)


# ---------------------------------------------------------
# 6. Search SERPs by ID
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
