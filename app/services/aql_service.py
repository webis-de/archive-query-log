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
from app.utils.advanced_search_parser import parse_advanced_query


# ---------------------------------------------------------
# Helper: Add hidden filter to Elasticsearch queries
# ---------------------------------------------------------
def _add_hidden_filter(filter_list: list[dict]) -> None:
    """
    Add a filter to exclude hidden SERPs from results.

    This filters out SERPs marked as hidden (e.g., spam, porn, problematic content).
    Uses must_not to maintain backwards compatibility: accepts both False and missing hidden field.

    Filter logic: hidden != True (i.e., False or doesn't exist)
    """
    filter_list.append({"bool": {"must_not": [{"term": {"hidden": True}}]}})


# ---------------------------------------------------------
# 1. Basic SERP Search
# ---------------------------------------------------------
async def search_basic(
    query: str,
    size: int = 10,
    from_: int = 0,
    advanced_mode: bool = False,
    fuzzy: bool = False,
    fuzziness: str = "AUTO",
    expand_synonyms: bool = False,
) -> dict:
    """
    Simple full-text search in SERPs by query string.

    Args:
        query: Search query string
        size: Number of results to return
        from_: Offset for pagination
        advanced_mode: If True, parse query for boolean operators, phrases, wildcards
        fuzzy: If True, enable fuzzy matching to handle typos
        fuzziness: Control fuzzy tolerance (AUTO, 0, 1, 2)
        expand_synonyms: If True, use multi_match to search across multiple fields with synonyms

    Returns:
        dict with keys:
            - hits: List of search results
            - total: Total number of results found
            - suggestions: Optional "did you mean?" suggestions
    """
    es = get_es_client()

    # Build query with hidden filter
    filter_clause: list[dict] = []
    _add_hidden_filter(filter_clause)

    # Choose query type based on advanced_mode, fuzzy, and expand_synonyms
    if advanced_mode:
        # Parse query with advanced syntax (boolean operators, wildcards, etc.)
        query_match = parse_advanced_query(query)
    elif expand_synonyms:
        # Multi-match query for broader matching (simulates synonym expansion)
        # Uses phrase and partial matching for query expansion effect
        query_match = {
            "bool": {
                "should": [
                    {
                        "match": {"url_query": {"query": query, "boost": 3.0}}
                    },  # Exact match highest
                    {
                        "match_phrase": {"url_query": {"query": query, "boost": 2.0}}
                    },  # Phrase match
                    {
                        "match": {
                            "url_query": {
                                "query": query,
                                "fuzziness": fuzziness if fuzzy else "0",
                                "boost": 1.0,
                            }
                        }
                    },  # Fuzzy/expanded
                ],
                "minimum_should_match": 1,
            }
        }
    elif fuzzy:
        # Fuzzy match query with configurable fuzziness
        query_match = {"match": {"url_query": {"query": query, "fuzziness": fuzziness}}}
    else:
        # Simple match query
        query_match = {"match": {"url_query": query}}

    query_clause = {"bool": {"must": [query_match], "filter": filter_clause}}

    body = {
        "query": query_clause,
        "size": size,
        "from": from_,
        "track_total_hits": True,
    }

    # Add term suggester for "Did you mean?" functionality
    if fuzzy or expand_synonyms:
        body["suggest"] = {
            "did_you_mean": {
                "text": query,
                "term": {
                    "field": "url_query",
                    "suggest_mode": "popular",  # Only suggest more popular terms
                    "min_word_length": 3,  # Don't suggest for very short words
                },
            }
        }

    response = await es.search(index="aql_serps", body=body)
    hits: List[Any] = response["hits"]["hits"]
    total = response["hits"]["total"]

    # Handle both old and new Elasticsearch response formats
    if isinstance(total, dict):
        total_count = total.get("value", 0)
    else:
        total_count = total

    # Extract suggestions if available
    suggestions = []
    if "suggest" in response and "did_you_mean" in response["suggest"]:
        for suggestion in response["suggest"]["did_you_mean"]:
            for option in suggestion.get("options", []):
                if option["text"] != suggestion["text"]:  # Only include if different
                    suggestions.append(
                        {
                            "text": option["text"],
                            "score": option["score"],
                            "freq": option["freq"],
                        }
                    )

    result = {"hits": hits, "total": total_count}
    if suggestions:
        result["suggestions"] = suggestions

    return result


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
    advanced_mode: bool = False,
    fuzzy: bool = False,
    fuzziness: str = "AUTO",
    expand_synonyms: bool = False,
) -> dict:
    """
    Perform advanced search on SERPs with optional filters:
    - provider_id: filter by provider
    - year: filter by capture year
    - status_code: filter by HTTP status code
    - advanced_mode: enable boolean operators, phrase search, wildcards
    - fuzzy: enable fuzzy matching to handle typos
    - fuzziness: control fuzzy tolerance (AUTO, 0, 1, 2)
    - expand_synonyms: enable synonym-based query expansion

    Returns:
        dict with keys:
            - hits: List of search results
            - total: Total number of results found
            - suggestions: Optional "did you mean?" suggestions
    """
    es = get_es_client()

    bool_query: Dict[str, Any] = {
        "must": [],
        "filter": [],
    }

    # Choose query type based on advanced_mode, fuzzy, and expand_synonyms
    if advanced_mode:
        # Parse query with advanced syntax
        query_match = parse_advanced_query(query)
    elif expand_synonyms:
        # Multi-match query for broader matching (simulates synonym expansion)
        query_match = {
            "bool": {
                "should": [
                    {
                        "match": {"url_query": {"query": query, "boost": 3.0}}
                    },  # Exact match highest
                    {
                        "match_phrase": {"url_query": {"query": query, "boost": 2.0}}
                    },  # Phrase match
                    {
                        "match": {
                            "url_query": {
                                "query": query,
                                "fuzziness": fuzziness if fuzzy else "0",
                                "boost": 1.0,
                            }
                        }
                    },  # Fuzzy/expanded
                ],
                "minimum_should_match": 1,
            }
        }
    elif fuzzy:
        # Fuzzy match query with configurable fuzziness
        query_match = {"match": {"url_query": {"query": query, "fuzziness": fuzziness}}}
    else:
        # Simple match query
        query_match = {"match": {"url_query": query}}

    bool_query["must"].append(query_match)

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

    # Add hidden filter
    _add_hidden_filter(bool_query["filter"])

    body = {
        "query": {"bool": bool_query},
        "size": size,
        "from": from_,
        "track_total_hits": True,
    }

    # Add term suggester for "Did you mean?" functionality
    if fuzzy or expand_synonyms:
        body["suggest"] = {
            "did_you_mean": {
                "text": query,
                "term": {
                    "field": "url_query",
                    "suggest_mode": "popular",
                    "min_word_length": 3,
                },
            }
        }

    response = await es.search(index="aql_serps", body=body)
    hits: List[Any] = response["hits"]["hits"]
    total = response["hits"]["total"]

    # Handle both old and new Elasticsearch response formats
    if isinstance(total, dict):
        total_count = total.get("value", 0)
    else:
        total_count = total

    # Extract suggestions if available
    suggestions = []
    if "suggest" in response and "did_you_mean" in response["suggest"]:
        for suggestion in response["suggest"]["did_you_mean"]:
            for option in suggestion.get("options", []):
                if option["text"] != suggestion["text"]:
                    suggestions.append(
                        {
                            "text": option["text"],
                            "score": option["score"],
                            "freq": option["freq"],
                        }
                    )

    result = {"hits": hits, "total": total_count}
    if suggestions:
        result["suggestions"] = suggestions

    return result


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

    # Search for all SERPs using this archive (excluding hidden),
    # and get one example to extract metadata
    filter_clause: list[dict] = []
    _add_hidden_filter(filter_clause)

    body = {
        "query": {
            "bool": {
                "must": [{"match": {"archive.memento_api_url": archive_id}}],
                "filter": filter_clause,
            }
        },
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
    Excludes hidden SERPs from the count.

    Args:
        size: Maximum number of archives to return (default: 100)

    Returns:
        dict with:
            - total: Number of unique archives found
            - archives: List of ArchiveMetadata dicts
    """
    es = get_es_client()

    # Add hidden filter to aggregation query
    filter_clause: list[dict] = []
    _add_hidden_filter(filter_clause)

    body = {
        "query": {"bool": {"must": [{"match_all": {}}], "filter": filter_clause}},
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


# ---------------------------------------------------------
# 15. Get All Providers
# ---------------------------------------------------------
async def get_all_providers(size: int = 100) -> List[Any]:
    """
    Retrieve all available search providers from Elasticsearch.
    Returns a list of all providers.
    """
    es = get_es_client()

    # First query to get total count
    count_body = {"query": {"match_all": {}}, "size": 0, "track_total_hits": True}
    count_response = await es.search(index="aql_providers", body=count_body)
    total_info = count_response.get("hits", {}).get("total", 0)
    total = total_info.get("value", 0) if isinstance(total_info, dict) else total_info

    # Use the smaller of requested size or total count
    actual_size = min(size, total) if size > 0 else total

    # Fetch all providers
    body = {"query": {"match_all": {}}, "size": actual_size}
    response = await es.search(index="aql_providers", body=body)
    hits: List[Any] = response.get("hits", {}).get("hits", [])
    return hits


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
    Excludes hidden SERPs from suggestions.

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

    # Add hidden filter
    _add_hidden_filter(filter_clause)

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


# ---------------------------------------------------------
# 6c. Preview Search (aggregations + fallbacks)
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
    Lightweight preview aggregations for a query.

    Excludes hidden SERPs from all aggregations and counts.

    Returns:
        dict with keys:
            - query: str
            - total_hits: int (only counting visible SERPs)
            - top_queries: List[{query, count}]
            - date_histogram: List[{date, count}]
            - top_providers: List[{provider, count}]
            - top_archives: List[{archive, count}]
    """
    es = get_es_client()

    # Build base query with optional time filter
    must_clause: list[dict] = [{"match": {"url_query": query}}]
    filter_clause: list[dict] = []
    if last_n_months is not None and last_n_months > 0:
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30 * last_n_months)
        start_iso = start.replace(microsecond=0).isoformat()
        filter_clause.append({"range": {"capture.timestamp": {"gte": start_iso}}})

    # Add hidden filter
    _add_hidden_filter(filter_clause)

    if filter_clause:
        query_clause: dict[str, Any] = {
            "bool": {"must": must_clause, "filter": filter_clause}
        }
    else:
        query_clause = must_clause[0]

    # Map interval to ES calendar_interval
    interval = interval.lower()
    if interval not in {"day", "week", "month"}:
        interval = "month"

    # Initial aggregations (prefer stable keyword fields)
    agg_body = {
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
                }
            },
            "top_providers": {
                # Use provider.domain for readable output (e.g., "google.com", "bing.com")
                "terms": {"field": "provider.domain", "size": top_providers}
            },
            "top_archives": {
                "terms": {
                    "field": "archive.memento_api_url",
                    "size": top_archives,
                }
            },
        },
    }

    try:
        agg_resp = await es.search(index="aql_serps", body=agg_body)
    except Exception:
        # On any error, return empty structure
        return {
            "query": query,
            "total_hits": 0,
            "top_queries": [],
            "date_histogram": [],
            "top_providers": [],
            "top_archives": [],
        }

    # Total hits handling (dict or int)
    total_obj = agg_resp.get("hits", {}).get("total", 0)
    total_hits = (
        total_obj.get("value", total_obj) if isinstance(total_obj, dict) else total_obj
    )

    aggs = agg_resp.get("aggregations", {}) or {}

    # Extract initial aggregations
    top_queries_buckets = aggs.get("top_queries", {}).get("buckets", [])
    by_time_buckets = aggs.get("by_time", {}).get("buckets", [])
    top_providers_buckets = aggs.get("top_providers", {}).get("buckets", [])
    top_archives_buckets = aggs.get("top_archives", {}).get("buckets", [])

    # Convert to output structures
    top_queries_out: list[dict] = [
        {"query": b.get("key"), "count": b.get("doc_count", 0)}
        for b in top_queries_buckets
    ]
    date_histogram_out: list[dict] = [
        {"date": b.get("key_as_string"), "count": b.get("doc_count", 0)}
        for b in by_time_buckets
    ]
    top_providers_out: list[dict] = [
        {"provider": b.get("key"), "count": b.get("doc_count", 0)}
        for b in top_providers_buckets
    ]
    top_archives_out: list[dict] = [
        {"archive": b.get("key"), "count": b.get("doc_count", 0)}
        for b in top_archives_buckets
    ]

    # Fallback: compute top_queries from a sample if aggregation empty
    if not top_queries_out:
        # Sample size scales with requested top N (bounded)
        sample_size = max(top_n_queries * 100, 200)
        sample_size = min(sample_size, 10000)

        sample_body = {
            "query": query_clause,
            "size": sample_size,
            "_source": ["url_query"],
            "sort": ["_score"],
        }
        try:
            sample_resp = await es.search(index="aql_serps", body=sample_body)
            counts: dict[str, int] = {}
            for hit in sample_resp.get("hits", {}).get("hits", []):
                q = (hit.get("_source", {}) or {}).get("url_query")
                if q:
                    counts[q] = counts.get(q, 0) + 1
            top_queries_out = [
                {"query": q, "count": c}
                for q, c in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[
                    :top_n_queries
                ]
            ]
        except Exception:
            top_queries_out = []

    # Fallbacks for providers if empty
    if not top_providers_out:
        try:
            # 1) Fallback to provider.id (UUIDs as last resort)
            prov_fallback_body = {
                "query": query_clause,
                "size": 0,
                "aggs": {
                    "top_providers": {
                        "terms": {"field": "provider.id", "size": top_providers}
                    }
                },
            }
            prov_resp = await es.search(index="aql_serps", body=prov_fallback_body)
            fb_buckets = (
                prov_resp.get("aggregations", {})
                .get("top_providers", {})
                .get("buckets", [])
            )
            top_providers_out = [
                {"provider": b.get("key"), "count": b.get("doc_count", 0)}
                for b in fb_buckets
            ]
        except Exception:
            pass

    if not top_providers_out:
        try:
            # 2) Last resort: use provider.domain.keyword if available
            prov_fallback_body2 = {
                "query": query_clause,
                "size": 0,
                "aggs": {
                    "top_providers": {
                        "terms": {
                            "field": "provider.domain.keyword",
                            "size": top_providers,
                        }
                    }
                },
            }
            prov_resp2 = await es.search(index="aql_serps", body=prov_fallback_body2)
            fb_buckets2 = (
                prov_resp2.get("aggregations", {})
                .get("top_providers", {})
                .get("buckets", [])
            )
            top_providers_out = [
                {"provider": b.get("key"), "count": b.get("doc_count", 0)}
                for b in fb_buckets2
            ]
        except Exception:
            pass

    return {
        "query": query,
        "total_hits": total_hits or 0,
        "top_queries": top_queries_out,
        "date_histogram": date_histogram_out,
        "top_providers": top_providers_out,
        "top_archives": top_archives_out,
    }


# ---------------------------------------------------------
# 6d. SERPs Timeline (date histogram counts, excluding hidden)
# ---------------------------------------------------------
async def serps_timeline(
    query: str,
    provider_id: Optional[str] = None,
    archive_id: Optional[str] = None,
    interval: str = "month",
    last_n_months: int | None = 36,
) -> dict:
    """
    Build a date histogram for captures of the same query, optionally
    filtered by provider and archive. Returns counts per time bucket.

    Hidden SERPs are excluded via a must_not filter.

    Args:
        query: Query string to match in SERPs
        provider_id: Optional provider id filter (e.g., "google")
        archive_id: Optional archive filter (memento_api_url)
        interval: One of {day, week, month} (default: month)
        last_n_months: Limit to last N months (None/0 = no filter)

    Returns:
        dict with keys:
            - query, provider_id, archive_id, interval, last_n_months
            - total_hits
            - date_histogram: List[{date, count}] with date as YYYY-MM-DD
    """
    es = get_es_client()

    # Build query clauses
    must_clause: list[dict] = [{"match": {"url_query": query}}]
    filter_clause: list[dict] = []

    if provider_id:
        filter_clause.append({"term": {"provider.id": provider_id}})
    if archive_id:
        filter_clause.append({"term": {"archive.memento_api_url": archive_id}})
    if last_n_months is not None and last_n_months > 0:
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30 * last_n_months)
        start_iso = start.replace(microsecond=0).isoformat()
        filter_clause.append({"range": {"capture.timestamp": {"gte": start_iso}}})

    # Exclude hidden SERPs
    _add_hidden_filter(filter_clause)

    if filter_clause:
        query_clause: dict[str, Any] = {
            "bool": {"must": must_clause, "filter": filter_clause}
        }
    else:
        query_clause = must_clause[0]

    # Normalize interval
    interval = (interval or "month").lower()
    if interval not in {"day", "week", "month"}:
        interval = "month"

    body = {
        "query": query_clause,
        "size": 0,
        "aggs": {
            "by_time": {
                "date_histogram": {
                    "field": "capture.timestamp",
                    "calendar_interval": interval,
                }
            }
        },
    }

    try:
        resp = await es.search(index="aql_serps", body=body)
    except Exception:
        return {
            "query": query,
            "provider_id": provider_id,
            "archive_id": archive_id,
            "interval": interval,
            "last_n_months": last_n_months,
            "total_hits": 0,
            "date_histogram": [],
        }

    total_obj = resp.get("hits", {}).get("total", 0)
    total_hits = (
        total_obj.get("value", total_obj) if isinstance(total_obj, dict) else total_obj
    )

    buckets = (resp.get("aggregations", {}) or {}).get("by_time", {}).get("buckets", [])
    date_histogram_out: list[dict] = []
    for b in buckets:
        key_str = b.get("key_as_string")
        # Remove time component if present (e.g., 2025-01-01T00:00:00Z -> 2025-01-01)
        if isinstance(key_str, str) and "T" in key_str:
            key_str = key_str.split("T", 1)[0]
        date_histogram_out.append({"date": key_str, "count": b.get("doc_count", 0)})

    return {
        "query": query,
        "provider_id": provider_id,
        "archive_id": archive_id,
        "interval": interval,
        "last_n_months": last_n_months,
        "total_hits": total_hits or 0,
        "date_histogram": date_histogram_out,
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
# 13. Get Available Views for a SERP
# ---------------------------------------------------------
async def get_serp_view_options(serp_id: str) -> dict | None:
    """
    Get available view options for switching between different SERP representations.

    Returns metadata about which views are available for this SERP:
    - Raw view: Full original data
    - Unbranded view: Normalized, provider-agnostic view
    - Snapshot view: Web archive memento link

    Args:
        serp_id: The SERP document ID

    Returns:
        dict with keys:
            - serp_id: The SERP document ID
            - views: List of available view options with metadata
    """
    from app.schemas.aql import SERPViewType

    serp = await get_serp_by_id(serp_id)
    if not serp:
        return None

    source = serp["_source"]
    capture_info = source.get("capture", {})

    views = []

    # Raw view - always available
    views.append(
        {
            "type": SERPViewType.raw.value,
            "label": "Full Data",
            "description": "Complete SERP data as archived, including all metadata",
            "available": True,
            "url": f"/api/serps/{serp_id}",
        }
    )

    # Unbranded view - always available (shows empty results if no data)
    # The unbranded function handles missing results gracefully
    views.append(
        {
            "type": SERPViewType.unbranded.value,
            "label": "Unbranded View",
            "description": "Provider-agnostic normalized view of search results",
            "available": True,
            "url": f"/api/serps/{serp_id}?view=unbranded",
        }
    )

    # Snapshot view - available if memento URL can be constructed
    has_memento = bool(
        capture_info.get("url")
        and capture_info.get("timestamp")
        and source.get("archive", {}).get("memento_api_url")
    )

    memento_url = None
    if has_memento:
        archive_base = source.get("archive", {}).get("memento_api_url")
        timestamp = capture_info.get("timestamp")
        original_url = capture_info.get("url")
        memento_url = f"{archive_base}/{timestamp}/{original_url}"

    views.append(
        {
            "type": SERPViewType.snapshot.value,
            "label": "Web Archive Snapshot",
            "description": "View original SERP in web archive memento interface",
            "available": has_memento,
            "url": memento_url,
            "reason": (
                None
                if has_memento
                else "Memento URL cannot be constructed from available data"
            ),
        }
    )

    return {"serp_id": serp["_id"], "views": views}


# ---------------------------------------------------------
# 14. Get Provider by ID
# ---------------------------------------------------------
async def get_provider_by_id(provider_id: str) -> Any | None:
    """Fetch a single provider by ID from Elasticsearch."""
    es = get_es_client()
    try:
        response = await es.get(index="aql_providers", id=provider_id)
        return response
    except Exception:
        return None


# ---------------------------------------------------------
# (removed) Get All Archives via aql_archives index
# Note: Use list_all_archives() which aggregates over aql_serps and
# returns enriched metadata. The former duplicate implementation that
# directly queried the dedicated aql_archives index was unused and
# has been removed to avoid confusion.


# ---------------------------------------------------------
# 16. Get Archive by ID
# ---------------------------------------------------------
async def get_archive_by_id(archive_id: str) -> Any | None:
    """Fetch a single archive by ID from Elasticsearch."""
    es = get_es_client()
    try:
        response = await es.get(index="aql_archives", id=archive_id)
        return response
    except Exception:
        return None


# ---------------------------------------------------------
# 17. Compare SERPs
# ---------------------------------------------------------
async def compare_serps(serp_ids: List[str]) -> dict | None:
    """
    Compare multiple SERPs and return detailed comparison data.

    Compares 2-5 SERPs and returns:
    - Full SERP data for each ID
    - Common and unique URLs across SERPs
    - Ranking differences for common URLs
    - Similarity metrics (Jaccard similarity, ranking correlation)
    - Provider, timestamp, and query comparison
    - Statistical summary

    Args:
        serp_ids: List of SERP IDs to compare (2-5 items)

    Returns:
        Dict with comparison data or None if any SERP not found
    """
    if not serp_ids or len(serp_ids) < 2:
        return None

    # Fetch all SERPs
    serps_data = []
    for serp_id in serp_ids:
        serp = await get_serp_by_id(serp_id)
        if not serp:
            return None
        serps_data.append(serp)

    # Extract metadata and results from each SERP
    serps_metadata = []
    serps_results = []

    for serp in serps_data:
        source = serp["_source"]

        # Extract metadata
        metadata = {
            "serp_id": serp["_id"],
            "query": source.get("url_query", ""),
            "provider_id": source.get("provider", {}).get("id"),
            "provider_name": source.get("provider", {}).get("name"),
            "timestamp": source.get("capture", {}).get("timestamp"),
            "status_code": source.get("capture", {}).get("status_code"),
            "archive": source.get("archive", {}).get("memento_api_url"),
        }
        serps_metadata.append(metadata)

        # Extract search results (URLs with positions)
        results = []
        if "results" in source:
            for idx, result in enumerate(source["results"]):
                results.append(
                    {
                        "position": idx + 1,
                        "url": result.get("url"),
                        "title": result.get("title"),
                        "snippet": result.get("snippet") or result.get("description"),
                    }
                )
        serps_results.append(results)

    # Compute URL-based comparisons
    url_sets = [set(r["url"] for r in results if r["url"]) for results in serps_results]

    # Find common and unique URLs
    common_urls = set.intersection(*url_sets) if url_sets else set()
    all_urls = set.union(*url_sets) if url_sets else set()
    unique_per_serp = [urls - common_urls for urls in url_sets]

    # Calculate Jaccard similarity for each pair
    def jaccard_similarity(set1: set, set2: set) -> float:
        if not set1 and not set2:
            return 1.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    pairwise_similarities = []
    for i in range(len(url_sets)):
        for j in range(i + 1, len(url_sets)):
            similarity = jaccard_similarity(url_sets[i], url_sets[j])
            pairwise_similarities.append(
                {
                    "serp_1": serp_ids[i],
                    "serp_2": serp_ids[j],
                    "jaccard_similarity": round(similarity, 4),
                }
            )

    # Calculate average Jaccard similarity
    if pairwise_similarities:
        total_similarity = sum(
            p["jaccard_similarity"]
            for p in pairwise_similarities
            if isinstance(p["jaccard_similarity"], (int, float))
        )
        avg_similarity = total_similarity / len(pairwise_similarities)
    else:
        avg_similarity = 0.0

    # Calculate ranking differences for common URLs
    ranking_comparison = []
    for url in common_urls:
        positions = {}
        for idx, results in enumerate(serps_results):
            for result in results:
                if result["url"] == url:
                    positions[serp_ids[idx]] = result["position"]
                    break

        # Calculate position variance
        position_values = list(positions.values())
        if len(position_values) > 1:
            mean_position = sum(position_values) / len(position_values)
            variance = sum((p - mean_position) ** 2 for p in position_values) / len(
                position_values
            )
            std_dev = variance**0.5
        else:
            std_dev = 0.0

        ranking_comparison.append(
            {
                "url": url,
                "positions": positions,
                "min_position": min(positions.values()),
                "max_position": max(positions.values()),
                "position_difference": max(positions.values())
                - min(positions.values()),
                "std_dev": round(std_dev, 2),
            }
        )

    # Sort by position difference (descending)
    ranking_comparison.sort(key=lambda x: x["position_difference"], reverse=True)

    # Calculate Spearman correlation for each pair (if applicable)
    def spearman_correlation(results1: List[dict], results2: List[dict]) -> float:
        """Calculate Spearman rank correlation for common URLs."""
        # Get common URLs with their positions
        url_positions1 = {r["url"]: r["position"] for r in results1 if r["url"]}
        url_positions2 = {r["url"]: r["position"] for r in results2 if r["url"]}
        common = set(url_positions1.keys()) & set(url_positions2.keys())

        if len(common) < 2:
            return 0.0

        # Calculate rank differences
        rank_diffs_squared = sum(
            (url_positions1[url] - url_positions2[url]) ** 2 for url in common
        )
        n = len(common)
        correlation = 1 - (6 * rank_diffs_squared) / (n * (n**2 - 1))
        return float(correlation)

    pairwise_correlations = []
    for i in range(len(serps_results)):
        for j in range(i + 1, len(serps_results)):
            correlation = spearman_correlation(serps_results[i], serps_results[j])
            pairwise_correlations.append(
                {
                    "serp_1": serp_ids[i],
                    "serp_2": serp_ids[j],
                    "spearman_correlation": round(correlation, 4),
                }
            )

    # Build response
    return {
        "comparison_summary": {
            "serp_count": len(serp_ids),
            "serp_ids": serp_ids,
            "total_unique_urls": len(all_urls),
            "common_urls_count": len(common_urls),
            "avg_jaccard_similarity": round(avg_similarity, 4),
        },
        "serps_metadata": serps_metadata,
        "serps_full_data": [
            {"serp_id": serp["_id"], "data": serp} for serp in serps_data
        ],
        "url_comparison": {
            "common_urls": list(common_urls),
            "unique_per_serp": [
                {"serp_id": serp_ids[idx], "unique_urls": list(urls)}
                for idx, urls in enumerate(unique_per_serp)
            ],
            "url_counts": [
                {"serp_id": serp_ids[idx], "total_urls": len(url_sets[idx])}
                for idx in range(len(url_sets))
            ],
        },
        "ranking_comparison": ranking_comparison[:50],  # Limit to top 50
        "similarity_metrics": {
            "pairwise_jaccard": pairwise_similarities,
            "pairwise_spearman": pairwise_correlations,
        },
    }


# ---------------------------------------------------------
# 18. Get Provider Statistics
# ---------------------------------------------------------
async def get_provider_statistics(
    provider_id: str,
    interval: str = "month",
    last_n_months: int | None = 36,
) -> dict | None:
    """
    Get descriptive statistics for a search provider.

    Aggregates information from all SERPs captured from this provider.
    Excludes hidden SERPs from all statistics.

    Args:
        provider_id: Provider ID (e.g., 'google')
        interval: Histogram interval (day, week, month)
        last_n_months: Limit histogram to last N months (None/0 = no filter)

    Returns:
        dict with:
            - provider_id: str
            - serp_count: int (total visible SERPs)
            - unique_queries_count: int
            - date_range: {earliest, latest} or None if no data
            - top_archives: List[{archive, count}]
            - date_histogram: List[{date, count}] (optional based on interval)
    """
    es = get_es_client()

    # Build query with filter
    filter_clause: list[dict] = [{"term": {"provider.id": provider_id}}]

    if last_n_months is not None and last_n_months > 0:
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30 * last_n_months)
        start_iso = start.replace(microsecond=0).isoformat()
        filter_clause.append({"range": {"capture.timestamp": {"gte": start_iso}}})

    # Add hidden filter
    _add_hidden_filter(filter_clause)

    query_clause: dict[str, Any] = {
        "bool": {"must": [{"match_all": {}}], "filter": filter_clause}
    }

    # Normalize interval
    interval = (interval or "month").lower()
    if interval not in {"day", "week", "month"}:
        interval = "month"

    # Aggregations for statistics
    # Get basic stats (these are more robust)
    # Note: Using terms aggregation with high size limit instead of cardinality
    # because url_query field is text-based and doesn't support cardinality aggregations
    # without enabling fielddata (which is memory-intensive).
    # size: 100000 covers most practical scenarios while staying memory-efficient
    basic_agg_body = {
        "query": query_clause,
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "unique_queries": {
                "terms": {
                    "field": "url_query.keyword",
                    "size": 100000,
                }
            },
            "top_archives": {
                "terms": {
                    "field": "archive.memento_api_url",
                    "size": 5,
                }
            },
        },
    }

    try:
        resp = await es.search(index="aql_serps", body=basic_agg_body)
    except Exception:
        return None

    # Extract total hits
    total_obj = resp.get("hits", {}).get("total", 0)
    serp_count = (
        total_obj.get("value", total_obj) if isinstance(total_obj, dict) else total_obj
    )

    if serp_count == 0:
        return None

    aggs = resp.get("aggregations", {}) or {}

    # Extract unique queries count from terms aggregation buckets
    unique_queries_buckets = aggs.get("unique_queries", {}).get("buckets", [])
    unique_queries = len(unique_queries_buckets)

    # Fallback: if aggregation returned no buckets, fetch and count manually
    # Reason: url_query.keyword sub-field may not be indexed/populated in some cases.
    # Solution: Sample documents (adaptive size: min 1000, max 10000) and count unique
    # values in-memory via dictionary deduplication. This is memory-efficient and avoids
    # fielddata overhead while still providing accurate unique query counts for large datasets.
    if not unique_queries_buckets:
        try:
            # Fetch a sample of documents and count unique queries
            sample_size = min(10000, max(serp_count, 1000))  # Adaptive sample size
            fallback_body = {
                "query": query_clause,
                "size": sample_size,
                "_source": ["url_query"],
            }
            fallback_resp = await es.search(index="aql_serps", body=fallback_body)
            query_counts: dict[str, int] = {}
            for hit in fallback_resp.get("hits", {}).get("hits", []):
                q = (hit.get("_source", {}) or {}).get("url_query")
                if q:
                    query_counts[q] = query_counts.get(q, 0) + 1
            unique_queries = len(query_counts)
        except Exception:
            unique_queries = 0

    # Try to get date histogram (may fail on documents with malformed timestamps)
    # Note: Only use date_histogram, NOT stats aggregation - stats fails on corrupted timestamps
    date_histogram_out: list[dict] = []
    try:
        histogram_agg_body = {
            "query": query_clause,
            "size": 0,
            "aggs": {
                "by_time": {
                    "date_histogram": {
                        "field": "capture.timestamp",
                        "calendar_interval": interval,
                    }
                },
            },
        }
        hist_resp = await es.search(index="aql_serps", body=histogram_agg_body)
        hist_aggs = hist_resp.get("aggregations", {}) or {}

        # Extract date histogram
        by_time_buckets = hist_aggs.get("by_time", {}).get("buckets", [])
        for b in by_time_buckets:
            key_str = b.get("key_as_string")
            if isinstance(key_str, str) and "T" in key_str:
                key_str = key_str.split("T", 1)[0]
            date_histogram_out.append({"date": key_str, "count": b.get("doc_count", 0)})
    except Exception:
        # If histogram fails, continue with what we have
        pass

    # Extract top archives
    top_archives_buckets = aggs.get("top_archives", {}).get("buckets", [])
    top_archives_out: list[dict] = [
        {"archive": b.get("key"), "count": b.get("doc_count", 0)}
        for b in top_archives_buckets
    ]

    return {
        "provider_id": provider_id,
        "serp_count": serp_count,
        "unique_queries_count": unique_queries,
        "top_archives": top_archives_out,
        "date_histogram": date_histogram_out if date_histogram_out else None,
    }


# ---------------------------------------------------------
# 19. Get Archive Statistics
# ---------------------------------------------------------
async def get_archive_statistics(
    archive_id: str,
    interval: str = "month",
    last_n_months: int | None = 36,
) -> dict | None:
    """
    Get descriptive statistics for a web archive.

    Aggregates information from all SERPs in this archive.
    Excludes hidden SERPs from all statistics.

    Args:
        archive_id: Memento API URL of the archive
        interval: Histogram interval (day, week, month)
        last_n_months: Limit histogram to last N months (None/0 = no filter)

    Returns:
        dict with:
            - archive_id: str
            - serp_count: int (total visible SERPs, already in metadata)
            - unique_queries_count: int
            - date_range: {earliest, latest} or None if no data
            - top_providers: List[{provider, count}]
            - date_histogram: List[{date, count}]
    """
    es = get_es_client()

    # Build query with filter
    filter_clause: list[dict] = [{"term": {"archive.memento_api_url": archive_id}}]

    if last_n_months is not None and last_n_months > 0:
        from datetime import datetime, timezone, timedelta

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30 * last_n_months)
        start_iso = start.replace(microsecond=0).isoformat()
        filter_clause.append({"range": {"capture.timestamp": {"gte": start_iso}}})

    # Add hidden filter
    _add_hidden_filter(filter_clause)

    query_clause: dict[str, Any] = {
        "bool": {"must": [{"match_all": {}}], "filter": filter_clause}
    }

    # Normalize interval
    interval = (interval or "month").lower()
    if interval not in {"day", "week", "month"}:
        interval = "month"

    # Aggregations for statistics
    # Get basic stats (these are more robust)
    # Note: Using terms aggregation with high size limit instead of cardinality
    # because url_query field is text-based and doesn't support cardinality aggregations
    # without enabling fielddata (which is memory-intensive).
    # size: 100000 covers most practical scenarios while staying memory-efficient
    basic_agg_body = {
        "query": query_clause,
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "unique_queries": {
                "terms": {
                    "field": "url_query.keyword",
                    "size": 100000,
                }
            },
            "top_providers": {
                "terms": {
                    "field": "provider.id",
                    "size": 5,
                }
            },
        },
    }

    try:
        resp = await es.search(index="aql_serps", body=basic_agg_body)
    except Exception:
        return None

    # Extract total hits
    total_obj = resp.get("hits", {}).get("total", 0)
    serp_count = (
        total_obj.get("value", total_obj) if isinstance(total_obj, dict) else total_obj
    )

    if serp_count == 0:
        return None

    aggs = resp.get("aggregations", {}) or {}

    # Extract unique queries count from terms aggregation buckets
    unique_queries_buckets = aggs.get("unique_queries", {}).get("buckets", [])
    unique_queries = len(unique_queries_buckets)

    # Fallback: if aggregation returned no buckets, fetch and count manually
    # Reason: url_query.keyword sub-field may not be indexed/populated in some cases.
    # Solution: Sample documents (adaptive size: min 1000, max 10000) and count unique
    # values in-memory via dictionary deduplication. This is memory-efficient and avoids
    # fielddata overhead while still providing accurate unique query counts for large datasets.
    if not unique_queries_buckets:
        try:
            # Fetch a sample of documents and count unique queries
            sample_size = min(10000, max(serp_count, 1000))  # Adaptive sample size
            fallback_body = {
                "query": query_clause,
                "size": sample_size,
                "_source": ["url_query"],
            }
            fallback_resp = await es.search(index="aql_serps", body=fallback_body)
            query_counts: dict[str, int] = {}
            for hit in fallback_resp.get("hits", {}).get("hits", []):
                q = (hit.get("_source", {}) or {}).get("url_query")
                if q:
                    query_counts[q] = query_counts.get(q, 0) + 1
            unique_queries = len(query_counts)
        except Exception:
            unique_queries = 0

    # Try to get date histogram (may fail on documents with malformed timestamps)
    # Note: Only use date_histogram, NOT stats aggregation - stats fails on corrupted timestamps
    date_histogram_out: list[dict] = []
    try:
        histogram_agg_body = {
            "query": query_clause,
            "size": 0,
            "aggs": {
                "by_time": {
                    "date_histogram": {
                        "field": "capture.timestamp",
                        "calendar_interval": interval,
                    }
                },
            },
        }
        hist_resp = await es.search(index="aql_serps", body=histogram_agg_body)
        hist_aggs = hist_resp.get("aggregations", {}) or {}

        # Extract date histogram
        by_time_buckets = hist_aggs.get("by_time", {}).get("buckets", [])
        for b in by_time_buckets:
            key_str = b.get("key_as_string")
            if isinstance(key_str, str) and "T" in key_str:
                key_str = key_str.split("T", 1)[0]
            date_histogram_out.append({"date": key_str, "count": b.get("doc_count", 0)})
    except Exception:
        # If histogram fails, continue with what we have
        pass

    # Extract top providers
    top_providers_buckets = aggs.get("top_providers", {}).get("buckets", [])
    top_providers_out: list[dict] = [
        {"provider": b.get("key"), "count": b.get("doc_count", 0)}
        for b in top_providers_buckets
    ]

    return {
        "archive_id": archive_id,
        "serp_count": serp_count,
        "unique_queries_count": unique_queries,
        "top_providers": top_providers_out,
        "date_histogram": date_histogram_out if date_histogram_out else None,
    }
