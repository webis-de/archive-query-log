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
from elasticsearch import BadRequestError
from app.core.elastic import get_es_client
from app.utils.url_cleaner import remove_tracking_parameters


# ---------------------------------------------------------
# 1. Basic SERP Search
# ---------------------------------------------------------
async def search_basic(query: str, size: int = 10, from_: int = 0) -> dict:
    """
    Simple full-text search in SERPs by query string.

    Returns:
        dict with keys:
            - hits: List of search results
            - total: Total number of results found
    """
    es = get_es_client()
    body = {"query": {"match": {"url_query": query}}, "size": size, "from": from_}
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
    from_: int = 0,
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

    body = {"query": {"bool": bool_query}, "size": size, "from": from_}
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
# 6. Preview search (aggregations for suggestions / preview)
# ---------------------------------------------------------
async def preview_search(
    query: str,
    top_n_queries: int = 10,
    interval: str = "month",
    top_providers: int = 5,
    top_archives: int = 5,
    last_n_months: int | None = 36,
) -> dict:
    """
    Return summary statistics and top-matching queries for a lightweight preview.

    Aggregations returned:
      - total_hits
      - top_queries (terms on url_query.keyword)
      - date_histogram (by capture.timestamp)
      - top_providers (terms on provider.id)
      - top_archives (terms on archive.memento_api_url)
    """
    es = get_es_client()

    # build query with optional recent range filter
    must_clause = [{"match_phrase_prefix": {"url_query": query}}]
    filter_clause: list[dict] = []
    if last_n_months is not None and last_n_months > 0:
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        # approximate month as 30 days for simplicity
        start = now - timedelta(days=30 * last_n_months)
        # strip microseconds to match index mapping (strict_date_time_no_millis)
        start_iso = start.replace(microsecond=0).isoformat()
        filter_clause.append({"range": {"capture.timestamp": {"gte": start_iso}}})

    query_clause: dict[str, Any]
    if filter_clause:
        query_clause = {"bool": {"must": must_clause, "filter": filter_clause}}
    else:
        query_clause = must_clause[0]

    body = {
        "query": query_clause,
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "top_queries": {
                "terms": {"field": "url_query.keyword", "size": top_n_queries}
            },
            "by_time": {
                "date_histogram": {
                    "field": "capture.timestamp",
                    "calendar_interval": interval,
                    "min_doc_count": 1,
                }
            },
            "top_providers": {
                "terms": {"field": "provider.id.keyword", "size": top_providers}
            },
            "top_archives": {
                "terms": {
                    "field": "archive.memento_api_url.keyword",
                    "size": top_archives,
                }
            },
        },
    }

    response = await es.search(index="aql_serps", body=body)

    # total hits
    total = response.get("hits", {}).get("total", 0)
    if isinstance(total, dict):
        total_count = total.get("value", 0)
    else:
        total_count = total

    aggs = response.get("aggregations", {})

    top_queries = [
        {"query": b.get("key"), "count": b.get("doc_count")}
        for b in aggs.get("top_queries", {}).get("buckets", [])
    ]

    # Fallback: Extract top queries from sample documents if aggregation fails
    if not top_queries:
        try:
            # Dynamically adjust sample size based on total hits and requested top_n
            # Use min(10000, total_count) to balance accuracy vs performance
            sample_size = min(10000, max(1000, top_n_queries * 100))

            sample_body_adjusted = {
                "query": query_clause,
                "size": sample_size,
                "_source": ["url_query"],
            }
            sample_response = await es.search(
                index="aql_serps", body=sample_body_adjusted
            )
            hits = sample_response.get("hits", {}).get("hits", [])

            # Count occurrences of each unique query
            query_counts: dict[str, int] = {}
            for hit in hits:
                source = hit.get("_source", {})
                q = source.get("url_query", "")
                if q:
                    query_counts[q] = query_counts.get(q, 0) + 1

            # Sort by count and get top N
            sorted_queries = sorted(
                query_counts.items(), key=lambda x: x[1], reverse=True
            )
            top_queries = [
                {"query": query, "count": count}
                for query, count in sorted_queries[:top_n_queries]
            ]
        except (BadRequestError, Exception):
            top_queries = []

    date_histogram = [
        {
            "key_as_string": b.get("key_as_string", b.get("key")),
            "count": b.get("doc_count"),
        }
        for b in aggs.get("by_time", {}).get("buckets", [])
    ]

    top_providers_list = [
        {"id": b.get("key"), "count": b.get("doc_count")}
        for b in aggs.get("top_providers", {}).get("buckets", [])
    ]

    # Fallback: if keyword-based aggregation returned empty buckets, try non-keyword field
    if not top_providers_list:
        fallback_body = dict(body)
        fallback_body["aggs"] = {
            "top_providers": {"terms": {"field": "provider.id", "size": top_providers}}
        }
        try:
            fallback_resp = await es.search(index="aql_serps", body=fallback_body)
            fallback_aggs = fallback_resp.get("aggregations", {})
            top_providers_list = [
                {"id": b.get("key"), "count": b.get("doc_count")}
                for b in fallback_aggs.get("top_providers", {}).get("buckets", [])
            ]
        except (BadRequestError, Exception):
            top_providers_list = []

    top_archives_list = [
        {"archive": b.get("key"), "count": b.get("doc_count")}
        for b in aggs.get("top_archives", {}).get("buckets", [])
    ]

    # Fallback: if keyword-based aggregation returned empty buckets, try non-keyword field
    if not top_archives_list:
        fallback_body = dict(body)
        fallback_body["aggs"] = {
            "top_archives": {
                "terms": {"field": "archive.memento_api_url", "size": top_archives}
            }
        }
        try:
            fallback_resp = await es.search(index="aql_serps", body=fallback_body)
            fallback_aggs = fallback_resp.get("aggregations", {})
            top_archives_list = [
                {"archive": b.get("key"), "count": b.get("doc_count")}
                for b in fallback_aggs.get("top_archives", {}).get("buckets", [])
            ]
        except (BadRequestError, Exception):
            top_archives_list = []

    return {
        "query": query,
        "total_hits": total_count,
        "top_queries": top_queries,
        "date_histogram": date_histogram,
        "top_providers": top_providers_list,
        "top_archives": top_archives_list,
    }


# ---------------------------------------------------------
# 6b. Search suggestions
# ---------------------------------------------------------
async def search_suggestions(
    prefix: str,
    last_n_months: int | None = 36,
    size: int = 10,
) -> dict:
    """
    Get popular search query suggestions based on prefix.

    Matches queries starting with the given prefix and returns the most
    popular (frequent) ones, ranked by document count.

    Performance Note:
    - Fetches size*20 documents to account for duplicates during deduplication
    - Uses match_phrase_prefix (faster than wildcard queries)
    - Time filtering reduces result set before aggregation

    Args:
        prefix: Query prefix to search for
        last_n_months: Filter to last N months (None/0 = no filter)
        size: Number of suggestions to return (1-50)

    Returns:
        Dict with "prefix" and "suggestions" list
    """
    es = get_es_client()

    # Build query with optional time filter
    must_clause = [{"match_phrase_prefix": {"url_query": prefix}}]
    filter_clause: list[dict] = []

    if last_n_months is not None and last_n_months > 0:
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30 * last_n_months)
        start_iso = start.replace(microsecond=0).isoformat()
        filter_clause.append({"range": {"capture.timestamp": {"gte": start_iso}}})

    query_clause: dict[str, Any]
    if filter_clause:
        query_clause = {"bool": {"must": must_clause, "filter": filter_clause}}
    else:
        query_clause = must_clause[0]

    # Get matched documents and deduplicate by url_query
    body = {
        "query": query_clause,
        "size": min(size * 20, 1000),  # Cap at 1000 to prevent excessive memory use
        "_source": ["url_query"],
        "sort": ["_score"],
    }

    try:
        response = await es.search(index="aql_serps", body=body)

        # Deduplicate and count occurrences
        suggestion_counts: dict[str, int] = {}
        for hit in response["hits"]["hits"]:
            query = hit["_source"].get("url_query")
            if query:
                suggestion_counts[query] = suggestion_counts.get(query, 0) + 1

        # Sort by count (descending) and take top N
        suggestions = [
            {"query": q, "count": c}
            for q, c in sorted(suggestion_counts.items(), key=lambda x: (-x[1], x[0]))[
                :size
            ]
        ]
    except Exception:
        suggestions = []

    return {
        "prefix": prefix,
        "suggestions": suggestions,
    }


# 7. Get SERP by ID
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

    # extract hits from the returned dict (search_advanced returns {"hits": [...], "total": N})
    hits = results.get("hits", []) if isinstance(results, dict) else results

    # only use results that are not the original serp
    related = [hit for hit in hits if hit["_id"] != serp_id]
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


# ---------------------------------------------------------
# 12. Get unbranded SERP view
# ---------------------------------------------------------
async def get_serp_unbranded(serp_id: str) -> dict | None:
    """
    Get a unified, provider-agnostic view of SERP contents.

    Normalizes parsed query and result blocks across different search
    providers to present a clean, unbranded view of the SERP.

    Returns:
        dict with keys:
            - serp_id: The SERP document ID
            - query: Normalized parsed query information
            - results: Normalized list of search results
            - metadata: Capture metadata (timestamp, URL, status_code)
    """
    serp = await get_serp_by_id(serp_id)
    if not serp:
        return None

    source = serp["_source"]

    # Extract normalized query information
    query_data = {
        "raw": source.get("url_query", ""),
        "parsed": source.get("parsed_query", None),
    }

    # Extract normalized results
    results = []
    if "results" in source:
        for idx, result in enumerate(source["results"]):
            normalized_result = {
                "position": idx + 1,
                "url": result.get("url"),
                "title": result.get("title"),
                "snippet": result.get("snippet") or result.get("description"),
            }
            results.append(normalized_result)

    # Extract metadata
    capture_info = source.get("capture", {})
    metadata = {
        "timestamp": capture_info.get("timestamp"),
        "url": capture_info.get("url"),
        "status_code": capture_info.get("status_code"),
    }

    return {
        "serp_id": serp["_id"],
        "query": query_data,
        "results": results,
        "metadata": metadata,
    }


# ---------------------------------------------------------
# 13. Get Archive Metadata by ID
# ---------------------------------------------------------
async def get_archive_metadata(archive_id: str) -> dict | None:
    """
    Get metadata for a specific web archive.

    Archive ID is the Memento API URL (base URL without document path).
    Aggregates information from all SERPs using this archive.

    Returns:
        dict with:
            - id: Archive identifier (memento_api_url)
            - name: Human-readable archive name (derived from URL)
            - memento_api_url: Memento API base URL
            - cdx_api_url: CDX API URL (from archive data or derived)
            - homepage: Archive homepage URL (optional)
            - serp_count: Number of SERPs in this archive
    """
    es = get_es_client()

    # Search for all SERPs using this archive, and get one example to extract metadata
    body = {
        "query": {"match": {"archive.memento_api_url": archive_id}},
        "size": 1,
        "track_total_hits": True,
        "_source": ["archive"],
    }

    try:
        response = await es.search(index="aql_serps", body=body)
        total = response.get("hits", {}).get("total", 0)

        # Handle both old and new Elasticsearch response formats
        if isinstance(total, dict):
            serp_count = total.get("value", 0)
        else:
            serp_count = total

        if serp_count == 0:
            return None

        # Get archive metadata from a sample document if available
        hits = response.get("hits", {}).get("hits", [])
        archive_data = {}
        if hits:
            archive_data = hits[0].get("_source", {}).get("archive", {})

        # Derive archive name from URL
        archive_name = _derive_archive_name(archive_id)

        # Use CDX API URL from data if available, otherwise derive it
        cdx_api_url = archive_data.get("cdx_api_url") or _derive_cdx_url(archive_id)

        # Derive homepage from archive URL
        homepage = _derive_homepage(archive_id)

        return {
            "id": archive_id,
            "name": archive_name,
            "memento_api_url": archive_id,
            "cdx_api_url": cdx_api_url,
            "homepage": homepage,
            "serp_count": serp_count,
        }

    except Exception:
        return None


# ---------------------------------------------------------
# 14. List all Archives
# ---------------------------------------------------------
async def list_all_archives(size: int = 100) -> dict:
    """
    Get a list of all available web archives in the dataset.

    Returns all unique archives with their SERP counts, sorted by count.

    Args:
        size: Maximum number of archives to return (default: 100)

    Returns:
        dict with:
            - total: Number of unique archives found
            - archives: List of ArchiveMetadata dicts
    """
    es = get_es_client()

    body = {
        "query": {"match_all": {}},
        "size": 0,
        "aggs": {
            "unique_archives": {
                "terms": {
                    "field": "archive.memento_api_url",
                    "size": size,
                    "order": {"_count": "desc"},
                }
            }
        },
    }

    try:
        response = await es.search(index="aql_serps", body=body)
        aggs = response.get("aggregations", {})

        archives = []
        for bucket in aggs.get("unique_archives", {}).get("buckets", []):
            archive_id = bucket.get("key")
            serp_count = bucket.get("doc_count", 0)

            if not archive_id or serp_count == 0:
                continue

            archive_name = _derive_archive_name(archive_id)
            cdx_api_url = _derive_cdx_url(archive_id)
            homepage = _derive_homepage(archive_id)

            archives.append(
                {
                    "id": archive_id,
                    "name": archive_name,
                    "memento_api_url": archive_id,
                    "cdx_api_url": cdx_api_url,
                    "homepage": homepage,
                    "serp_count": serp_count,
                }
            )

        return {
            "total": len(archives),
            "archives": archives,
        }

    except Exception:
        return {"total": 0, "archives": []}


# ---------------------------------------------------------
# Helper Functions for Archive Metadata
# ---------------------------------------------------------
def _derive_archive_name(memento_api_url: str) -> str:
    """
    Derive a human-readable archive name from the Memento API URL.

    Examples:
    - https://web.archive.org/web -> Internet Archive
    - https://archive.example.org -> Archive Example
    """
    from urllib.parse import urlparse

    # Known archives mapping
    known_archives = {
        "https://web.archive.org/web": "Internet Archive (Wayback Machine)",
        "https://web.archive.org": "Internet Archive (Wayback Machine)",
        "https://archive.org": "Internet Archive",
    }

    if memento_api_url in known_archives:
        return known_archives[memento_api_url]

    # Generic fallback: extract domain from URL
    try:
        parsed = urlparse(memento_api_url)
        domain = parsed.netloc or parsed.path
        # Capitalize and make readable
        name = domain.replace("-", " ").replace(".org", "").title()
        return name if name else "Unknown Archive"
    except Exception:
        return "Unknown Archive"


def _derive_cdx_url(memento_api_url: str) -> str | None:
    """
    Derive CDX API URL from Memento API URL.

    Common patterns:
    - https://web.archive.org/web -> https://web.archive.org/cdx/search/csv
    - https://archive.example.org -> https://archive.example.org/cdx/search/csv
    """
    if not memento_api_url:
        return None

    # Known CDX URLs
    if memento_api_url.startswith("https://web.archive.org"):
        return "https://web.archive.org/cdx/search/csv"

    # Generic: append /cdx/search/csv to base URL
    base_url = memento_api_url.rstrip("/")
    return f"{base_url}/cdx/search/csv"


def _derive_homepage(memento_api_url: str) -> str | None:
    """
    Derive archive homepage from Memento API URL.

    Examples:
    - https://web.archive.org/web -> https://web.archive.org
    - https://archive.example.org -> https://archive.example.org
    """
    if not memento_api_url:
        return None

    # Known homepages
    if memento_api_url.startswith("https://web.archive.org"):
        return "https://web.archive.org"

    # Generic: return base URL without /web or /cdx paths
    from urllib.parse import urlparse

    try:
        parsed = urlparse(memento_api_url)
        # Remove /web or other path components
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        return base_url
    except Exception:
        return None
