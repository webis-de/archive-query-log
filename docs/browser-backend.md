# AQL Browser Backend

This document describes the endpoints and usage of the FastAPI backend for the AQL Browser project.
Refer to the [main README](../README.md) for development or deployment instructions.

## Core Endpoints

| Method | Endpoint  | Description                  |
| ------ | --------- | ---------------------------- |
| GET    | `/`       | Root endpoint (Health Check) |
| GET    | `/health` | Health Check                 |
| GET    | `/docs`   | Swagger UI                   |
| GET    | `/redoc`  | ReDoc UI                     |

## Search Endpoints

| Method | Endpoint                                                | Description                                  |
| ------ | ------------------------------------------------------- | -------------------------------------------- |
| GET    | `/api/serps?query=climate+change`                       | Basic SERP search                            |
| GET    | `/api/serps?query=climate&year=2024&provider_id=google` | Advanced SERP search                         |
| GET    | `/api/serps?query=%22climate%20change%22%20AND%20renewable&advanced_mode=true` | Advanced search mode with boolean operators |
| GET    | `/api/serps?query=clmate&fuzzy=true`                    | Fuzzy search to handle typos and misspellings |
| GET    | `/api/suggestions?prefix=the`                           | Get search query suggestions (autocomplete)  |
| GET    | `/api/serps/preview?query=climate`                      | Preview aggregations / suggestions for query |
| GET    | `/api/serps/compare?ids=id1,id2`                        | Compare multiple SERPs (2-5)                 |

Query Parameters for Search Endpoint:

- `query` (required) - Search term
- `page_size` - Results per page (default: 10, options: 10, 20, 50, 100, 1000)
- `page` - Page number (1-based). Use together with `page_size` to navigate pages, e.g. `?query=climate&page_size=20&page=2`.
- `provider_id` - Filter by provider ID (optional)
- `year` - Filter by year (optional)
- `status_code` - Filter by HTTP status code (optional)
- `advanced_mode` - Enable advanced search mode with boolean operators, phrase search, and wildcards (default: false)
- `fuzzy` - Enable fuzzy search to match similar queries and handle typos (default: false)
- `fuzziness` - Control fuzzy matching tolerance: AUTO (default), 0 (exact), 1, 2 (only applies when fuzzy=true)
- `expand_synonyms` - Enable enhanced relevance scoring and broader matching (default: false)

### Spelling Correction Search Mode

When `fuzzy=true`, the search uses fuzzy matching to handle typos and misspellings.

Fuzziness Levels:

- `AUTO` (default): 0 edits for 1-2 chars, 1 edit for 3-5 chars, 2 edits for 6+ chars
- `0`: Exact match only
- `1`: Up to 1 character difference
- `2`: Up to 2 character differences

Features:

1. Typos and Misspellings:
   - Example: `clmate` matches `climate`, `tehnology` matches `technology`

2. Common Mistakes   :
   - Transposed characters: `climaet` → `climate`
   - Missing characters: `climat` → `climate`
   - Extra characters: `climatee` → `climate`
   - Wrong characters: `climite` → `climate`

3. "Did You Mean?" Suggestions:
   - When fuzzy search is enabled, the API may return a `did_you_mean` field with suggested corrections
   - Based on more popular terms in the database
   - Example response: `"did_you_mean": [{"text": "climate", "score": 0.85, "freq": 12345}]`

Fuzzy Search Examples:

```shell
# Basic fuzzy search - handle typo in "climate"
curl "http://localhost:8000/api/serps?query=clmate&fuzzy=true"

# Fuzzy search with custom fuzziness level
curl "http://localhost:8000/api/serps?query=clmate&fuzzy=true&fuzziness=1"

# Fuzzy search with filters - find misspelled queries from 2023
curl "http://localhost:8000/api/serps?query=renwable&fuzzy=true&year=2023"

# Fuzzy search with pagination
curl "http://localhost:8000/api/serps?query=tehnology&fuzzy=true&page_size=20&page=1"
```

### Improved Relevance Scoring with Query Expansion

When `expand_synonyms=true`, the search uses multi-layer matching to improve result relevance.

Overall Ranking:

- Multi-layered Scoring: Results are scored using multiple matching strategies simultaneously
  - Exact token matches (highest boost)
  - Phrase matches (medium boost)
  - Fuzzy matches when combined with `fuzzy=true` (lower boost)
- Better Ranking: Documents matching on multiple layers get significantly higher scores
- No true synonyms: This does NOT find semantically related terms (e.g., "climate" will not match "global warming")

Query Expansion Examples:

```shell
# Enhanced relevance scoring
curl "http://localhost:8000/api/serps?query=climate&expand_synonyms=true"
# Top result score: ~85 vs ~14 without expansion

# Combine with fuzzy matching for best results
curl "http://localhost:8000/api/serps?query=climat&expand_synonyms=true&fuzzy=true&fuzziness=1"

# Compare scores with and without expansion
curl "http://localhost:8000/api/serps?query=climate&expand_synonyms=false"
curl "http://localhost:8000/api/serps?query=climate&expand_synonyms=true"
```

Note: When both `advanced_mode=true` and `fuzzy=true` are set, `advanced_mode` takes precedence.

### Advanced Search Mode

When `advanced_mode=true`, the search query supports:

1. Boolean Operators (case-insensitive):
   - `AND` - Both terms must be present
   - `OR` - Either term must be present
   - Example: `climate AND change` or `solar OR wind`

2. Phrase Search (exact match):
   - Use double quotes for exact phrases
   - Example: `"climate change"` matches only exact phrase

3. Wildcards:
   - `*` - Matches zero or more characters
   - `?` - Matches exactly one character
   - Example: `climat*` matches climate, climatic, climatology, etc.
   - Example: `cl?mate` matches climate, clamate, etc.

4. Grouping with Parentheses:
   - Use `()` to group expressions and control operator precedence
   - Example: `(renewable OR solar) AND energy`

Advanced Search Examples:

```shell
# Boolean AND - find SERPs with both terms
curl "http://localhost:8000/api/serps?query=climate%20AND%20change&advanced_mode=true"

# Boolean OR - find SERPs with either term
curl "http://localhost:8000/api/serps?query=solar%20OR%20wind&advanced_mode=true"

# Exact phrase search
curl "http://localhost:8000/api/serps?query=%22climate%20change%22&advanced_mode=true"

# Wildcard search - find variations
curl "http://localhost:8000/api/serps?query=climat*&advanced_mode=true"

# Complex boolean query with grouping
curl "http://localhost:8000/api/serps?query=(renewable%20OR%20solar)%20AND%20energy&advanced_mode=true"

# Combine with filters
curl "http://localhost:8000/api/serps?query=%22renewable%20energy%22%20AND%20policy&advanced_mode=true&year=2023"

# Multiple boolean operators
curl "http://localhost:8000/api/serps?query=climate%20AND%20change%20AND%20policy&advanced_mode=true"

# Phrase with wildcard
curl "http://localhost:8000/api/serps?query=%22climate%20change%22%20OR%20climat*&advanced_mode=true"
```

Note: In simple mode (`advanced_mode=false`, default), operators like "AND" and "OR" are treated as literal search terms.

### Search Preview Endpoint

- `query` (required) - Search term for aggregation
- `top_n_queries` - Number of top queries to return (default: 10)
- `interval` - Histogram interval: `day`, `week`, `month` (default: `month`)
- `top_providers` - Number of top providers to return (default: 5)
- `top_archives` - Number of top archives to return (default: 5)
- `last_n_months` - Limit histogram to last N months (optional, default: 36)

Example Preview Requests:

```shell
# Get overview statistics for a query
curl http://localhost:8000/api/serps/preview?query=climate

# Get statistics with custom intervals and limits
curl http://localhost:8000/api/serps/preview?query=climate&interval=week&top_providers=10&last_n_months=12

# Get top 20 queries with daily histogram
curl http://localhost:8000/api/serps/preview?query=python&top_n_queries=20&interval=day
```

### Suggestions Endpoint

- `prefix` (required) - Query prefix to search for suggestions
- `size` - Number of suggestions to return (default: 10, range: 1-50)
- `last_n_months` - Filter to last N months of data (default: 36, can be None to disable)

Example Suggestions Requests:

```bash
# Get top 5 suggestions for "python"
curl http://localhost:8000/api/suggestions?prefix=python&size=5

# Get suggestions for "the" from last 12 months
curl http://localhost:8000/api/suggestions?prefix=the&last_n_months=12

# Get suggestions with all parameters
curl http://localhost:8000/api/suggestions?prefix=test&size=20&last_n_months=24
```

## SERP Comparison Endpoint

- `ids` (required) - Comma-separated list of SERP IDs (2-5 IDs)

Example Compare Requests:

```shell
# Compare 2 SERPs
curl "http://localhost:8000/api/serps/compare?ids=abc123,def456"

# Compare 3 SERPs
curl "http://localhost:8000/api/serps/compare?ids=id1,id2,id3"

# Compare 5 SERPs (maximum)
curl "http://localhost:8000/api/serps/compare?ids=id1,id2,id3,id4,id5"
```

Compare Response contents:

- Comparison summary (total unique URLs, common URLs count, average similarity)
- Full metadata for each SERP (query, provider, timestamp, status)
- URL comparison (common URLs, unique URLs per SERP)
- Ranking comparison (position differences for common URLs)
- Similarity metrics (Jaccard similarity and Spearman correlation for each pair)

## SERPs Timeline Endpoint

| Method | Endpoint              | Description                       |
| ------ | --------------------- | --------------------------------- |
| GET    | `/api/serps/timeline` | Date histogram counts for a query |

Query Parameters for Timeline Endpoint

- `query` (required) – Query string to match
- `provider_id` – Optional provider filter (e.g., `google`)
- `archive_id` – Optional archive filter (Memento API URL)
- `interval` – `day` | `week` | `month` (default: `month`)
- `last_n_months` – Limit to last N months (default: `36`, `null` to disable)

Note: The `date_histogram` `date` values are returned without time (format `YYYY-MM-DD`).

Example Timeline Requests:

```shell
# Basic timeline for a query
curl "http://localhost:8000/api/serps/timeline?query=climate"

# Timeline filtered by provider and archive
curl "http://localhost:8000/api/serps/timeline?query=climate&provider_id=google&archive_id=https://web.archive.org/web"

# Weekly timeline limited to last 12 months
curl "http://localhost:8000/api/serps/timeline?query=climate&interval=week&last_n_months=12"
```

## SERP Detail Endpoints

| Method | Endpoint                                               | Description                            |
| ------ | ------------------------------------------------------ | -------------------------------------- |
| GET    | `/api/serps/{serp_id}`                                 | Get a single SERP by ID                |
| GET    | `/api/serps/{serp_id}?include=original_url`            | Include original SERP URL              |
| GET    | `/api/serps/{serp_id}?include=memento_url`             | Include Memento SERP URL               |
| GET    | `/api/serps/{serp_id}?include=related&related_size=X`  | Include related SERPs                  |
| GET    | `/api/serps/{serp_id}?include=unfurl`                  | Include unfurled URL components        |
| GET    | `/api/serps/{serp_id}?include=direct_links`            | Include direct search result links     |
| GET    | `/api/serps/{serp_id}?include=unbranded`               | Include provider-agnostic unified view |
| GET    | `/api/serps/{serp_id}/views`                           | Get available view options for a SERP  |
| GET    | `/api/serps/{serp_id}?view=unbranded`                  | Get unbranded view of a SERP           |
| GET    | `/api/serps/{serp_id}?view=snapshot`                   | Redirect to web archive snapshot       |

Query Parameters for SERP Detail Endpoint:

- `view` - View mode: `raw` (default), `unbranded`, or `snapshot`
- `include` - Comma-separated fields: `original_url`, `memento_url`, `related`, `unfurl`, `direct_links`, `unbranded`
- `remove_tracking` - Remove tracking parameters from original URL (requires `include=original_url`)
- `related_size` - Number of related SERPs (requires `include=related`, default: 10)
- `same_provider` - Only return related SERPs from same provider (requires `include=related`)

### SERP View Switcher

The SERP detail endpoint supports different view modes to help researchers examine archived SERPs from different perspectives:

1. Raw View (`view=raw`, default):
   - Complete SERP data as stored in the database
   - Includes all metadata, results, and archive information
   - Always available

2. Unbranded View (`view=unbranded`):
   - Provider-agnostic, normalized view of search results
   - Strips provider-specific branding and formatting
   - Focuses on query and results in a standardized format
   - Available when parsed results exist

3. Snapshot View (`view=snapshot`):
   - Redirects to the web archive's memento interface
   - Shows the original SERP as it appeared in the archive
   - Available when memento URL can be constructed

### View Discovery:

Use `/api/serps/{serp_id}/views` to discover which views are available for a specific SERP. The response includes:

- View type and label
- Description of what the view provides
- Availability status
- Direct URL to access the view
- Reason if view is unavailable

Example View Switcher Requests:

```shell
# Discover available views for a SERP
curl http://localhost:8000/api/serps/abc123/views

# Get raw view (default, full data)
curl http://localhost:8000/api/serps/abc123
curl http://localhost:8000/api/serps/abc123?view=raw

# Get unbranded view (normalized, provider-agnostic)
curl http://localhost:8000/api/serps/abc123?view=unbranded

# Redirect to web archive snapshot
curl -L http://localhost:8000/api/serps/abc123?view=snapshot

# Combine view parameter with include fields (raw view only)
curl http://localhost:8000/api/serps/abc123?view=raw&include=related,unfurl
```

## Archive Endpoints

| Method | Endpoint                     | Description                                    |
| ------ | ---------------------------- | ---------------------------------------------- |
| GET    | `/api/archives`              | List all available web archives in the dataset |
| GET    | `/api/archives/{archive_id}` | Get metadata for a specific web archive        |

Query Parameters for Archives List Endpoint:

- `limit` - Maximum number of archives to return (default: 100, range: 1-1000)

Path Parameters for Archive Detail Endpoint:

- `archive_id` - Memento API URL of the archive (no encoding needed)

Archive Metadata Fields:

- `id` - Unique archive identifier (Memento API URL)
- `name` - Human-readable archive name (e.g., "Internet Archive (Wayback Machine)")
- `memento_api_url` - Memento API base URL
- `cdx_api_url` - CDX API URL (from archive data or derived)
- `homepage` - Archive homepage URL
- `serp_count` - Number of SERPs captured from this archive

Example Archive Requests:

```bash
# List all archives (default limit: 100)
curl http://localhost:8000/api/archives

# List archives with custom limit
curl http://localhost:8000/api/archives?limit=50

# Get specific archive metadata (Internet Archive)
curl "http://localhost:8000/api/archives/https://web.archive.org/web"

# Get arquivo.pt archive metadata
curl "http://localhost:8000/api/archives/https://arquivo.pt/wayback"
```

Example Response for Individual Archive:

```json
{
  "id": "https://web.archive.org/web",
  "name": "Internet Archive (Wayback Machine)",
  "memento_api_url": "https://web.archive.org/web",
  "cdx_api_url": "https://web.archive.org/cdx/search/cdx",
  "homepage": "https://web.archive.org",
  "serp_count": 551912265
}
```

### Archive Statistics Endpoints

| Method | Endpoint                                | Description                                    |
| ------ | --------------------------------------- | ---------------------------------------------- |
| GET    | `/api/archives/{archive_id}/statistics` | Get descriptive statistics for a web archive   |

Query Parameters for Archive Statistics Endpoint:

- `interval` - Histogram interval: `day`, `week`, `month` (default: `month`)
- `last_n_months` - Limit histogram to last N months (default: 36, can be None to disable)

Archive Statistics Response includes:

- Total number of archived SERPs
- Number of unique queries
- Date range of captures
- Top search providers in this archive
- Date histogram of captures over time

Example Archive Statistics Requests:

```bash
# Get statistics for Internet Archive
curl "http://localhost:8000/api/archives/https://web.archive.org/web/statistics"

# Get statistics with custom interval and time range
curl "http://localhost:8000/api/archives/https://web.archive.org/web/statistics?interval=week&last_n_months=12"

# Get daily statistics for arquivo.pt archive
curl "http://localhost:8000/api/archives/https://arquivo.pt/wayback/statistics?interval=day"
```

## Providers Endpoints

| Method | Endpoint                                   | Description                                         |
| ------ | ------------------------------------------ | --------------------------------------------------- |
| GET    | `/api/providers?size=uint`                 | Get all available search providers                  |
| GET    | `/api/providers/{provider_id}`             | Get metadata for a specific search provider         |
| GET    | `/api/providers/{provider_id}/statistics`  | Get descriptive statistics for a search provider    |

Provider Identifier Resolution:

Both provider endpoints accept either a **provider UUID** or a **provider name**:

- By name: `/api/providers/google`
- By UUID: `/api/providers/f205fc44-d918-4b79-9a7f-c1373a6ff9f2`

The API automatically resolves the identifier to the correct provider by:

1. First trying it as a UUID (direct lookup in `aql_providers` index)
2. If not found, searching by provider name
3. Returns 404 if neither lookup succeeds

Example Provider Requests:

```shell
# Get provider metadata by name
curl http://localhost:8000/api/providers/google

# Get provider metadata by UUID
curl http://localhost:8000/api/providers/f205fc44-d918-4b79-9a7f-c1373a6ff9f2
```

### Provider Statistics Endpoint

Query Parameters for Provider Statistics Endpoint:

- `interval` - Histogram interval: `day`, `week`, `month` (default: `month`)
- `last_n_months` - Limit histogram to last N months (default: 36, can be None to disable)

Provider Statistics Response includes:

- Total number of archived SERPs
- Number of unique queries
- Date range of captures
- Top web archives used by this provider
- Date histogram of captures over time

Example Provider Requests:

```shell
# Get statistics for a provider (by name)
curl http://localhost:8000/api/providers/google/statistics

# Get statistics with custom interval and time range (by name)
curl http://localhost:8000/api/providers/google/statistics?interval=week&last_n_months=12

# Get statistics by UUID
curl http://localhost:8000/api/providers/f205fc44-d918-4b79-9a7f-c1373a6ff9f2/statistics

# Get daily statistics for all available data
curl http://localhost:8000/api/providers/google/statistics?interval=day&last_n_months=null
```

## Content Filtering

The browser API is prepared to filter out certain SERPs (e.g., spam or other sensitive content) from all search results and aggregations.
All requests to the Elasticsearch indices have an additional filter clause that excludes documents where the `hidden` field is set to `True`.

Ongoing work will tackle the following tasks:

- Develop content filtering criteria and guidelines for identifying SERPs that should not be shown.
- Add the `hidden` boolean field to the SERPs in the `aql_serps` Elasticsearch index.
