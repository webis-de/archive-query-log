# FastAPI Starter Project

A minimal yet extensible FastAPI project with modern project structure, tests, Elasticsearch (AQL) integration, and Docker support.

## 📋 Table of Contents

- [FastAPI Starter Project](#fastapi-starter-project)
  - [📋 Table of Contents](#-table-of-contents)
  - [🚀 For Users (Deployment \& Usage)](#-for-users-deployment--usage)
    - [Requirements](#requirements)
    - [Installation \& Start with Docker](#installation--start-with-docker)
    - [Available Endpoints](#available-endpoints)
      - [✅ Core Endpoints](#-core-endpoints)
      - [✅ Search Endpoints](#-search-endpoints)
      - [✅ SERP Detail Endpoints](#-serp-detail-endpoints)
      - [✅ Archive Endpoints](#-archive-endpoints)
      - [✅ Providers Endpoints](#-providers-endpoints)
      - [✅ Archive Statistics Endpoints](#-archive-statistics-endpoints)
  - [⚙️ For Developers (Development)](#️-for-developers-development)
    - [Developer Requirements](#developer-requirements)
    - [Setting Up Local Development Environment](#setting-up-local-development-environment)
  - [📁 Project Structure](#-project-structure)
  - [📚 API Documentation](#-api-documentation)
  - [🔧 Extending the Project](#-extending-the-project)
    - [Add a New Router](#add-a-new-router)
    - [Add a Database](#add-a-database)
    - [Environment Variables](#environment-variables)
  - [🛠 CI/CD Pipeline](#-cicd-pipeline)
    - [Test Stage](#test-stage)
    - [Build Stage](#build-stage)
    - [Deploy Stage (Optional)](#deploy-stage-optional)
  - [⚡ Important Commands](#-important-commands)
  - [🤝 Contributing](#-contributing)
  - [📄 License](#-license)
  - [🔐 Content Filtering](#-content-filtering)

---

## 🚀 For Users (Deployment & Usage)

### Requirements

- Port 8000 available
- Docker (need to be logged in:)

  ```bash
  docker login git.uni-jena.de
  ```

### Installation & Start with Docker

1. **Start the container (be sure image is up2date):**

   ```bash
   docker pull git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/backend:latest
   ```

   ```bash
   docker run -p 8000:8000 git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/backend:latest
   ```

2. **Test the API:**

   ```bash
   curl http://localhost:8000/
   ```

   ... or open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser for the Swagger UI.

3. **Stop the containers:**

   ```bash
   docker container ls
   docker stop <container-name>
   ```

### Available Endpoints

**To access the Elasticsearch data, the endpoints require a VPN connection to `vpn.webis.de` (via OpenVPN Connect, see Issue #7).**

#### ✅ Core Endpoints

| Method | Endpoint  | Description                  |
| ------ | --------- | ---------------------------- |
| GET    | `/`       | Root endpoint (Health Check) |
| GET    | `/health` | Health Check                 |
| GET    | `/docs`   | Swagger UI                   |
| GET    | `/redoc`  | ReDoc UI                     |

#### ✅ Search Endpoints

| Method | Endpoint                                                | Description                                  |
| ------ | ------------------------------------------------------- | -------------------------------------------- |
| GET    | `/api/serps?query=climate+change`                       | Basic SERP search                            |
| GET    | `/api/serps?query=climate&year=2024&provider_id=google` | Advanced SERP search                         |
| GET    | `/api/serps?query=%22climate%20change%22%20AND%20renewable&advanced_mode=true` | Advanced search mode with boolean operators |
| GET    | `/api/serps?query=clmate&fuzzy=true`                    | Fuzzy search to handle typos and misspellings |
| GET    | `/api/suggestions?prefix=the`                           | Get search query suggestions (autocomplete)  |
| GET    | `/api/serps/preview?query=climate`                      | Preview aggregations / suggestions for query |
| GET    | `/api/serps/compare?ids=id1,id2`                        | Compare multiple SERPs (2-5)                 |

**Query Parameters for Search Endpoint:**

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

**Fuzzy Search Mode:**

When `fuzzy=true`, the search uses fuzzy matching to handle typos and misspellings.

**Fuzziness Levels:**
- `AUTO` (default): 0 edits for 1-2 chars, 1 edit for 3-5 chars, 2 edits for 6+ chars
- `0`: Exact match only
- `1`: Up to 1 character difference
- `2`: Up to 2 character differences

**Features:**

1. **Typos and Misspellings**:
   - Example: `clmate` matches `climate`, `tehnology` matches `technology`

2. **Common Mistakes**:
   - Transposed characters: `climaet` → `climate`
   - Missing characters: `climat` → `climate`
   - Extra characters: `climatee` → `climate`
   - Wrong characters: `climite` → `climate`

3. **"Did You Mean?" Suggestions**:
   - When fuzzy search is enabled, the API may return a `did_you_mean` field with suggested corrections
   - Based on more popular terms in the database
   - Example response: `"did_you_mean": [{"text": "climate", "score": 0.85, "freq": 12345}]`

**Fuzzy Search Examples:**

```bash
# Basic fuzzy search - handle typo in "climate"
curl "http://localhost:8000/api/serps?query=clmate&fuzzy=true"

# Fuzzy search with custom fuzziness level
curl "http://localhost:8000/api/serps?query=clmate&fuzzy=true&fuzziness=1"

# Fuzzy search with filters - find misspelled queries from 2023
curl "http://localhost:8000/api/serps?query=renwable&fuzzy=true&year=2023"

# Fuzzy search with pagination
curl "http://localhost:8000/api/serps?query=tehnology&fuzzy=true&page_size=20&page=1"
```

**Enhanced Relevance Scoring (Query Expansion):**

When `expand_synonyms=true`, the search uses multi-layer matching to improve result relevance.

**How it works:**
- **Multi-Layer Scoring**: Results are scored using multiple matching strategies simultaneously
  - Exact token matches (highest boost)
  - Phrase matches (medium boost)
  - Fuzzy matches when combined with `fuzzy=true` (lower boost)
- **Better Ranking**: Documents matching on multiple layers get significantly higher scores
- **No true synonyms**: This does NOT find semantically related terms (e.g., "climate" will not match "global warming")

**What you get:**
- More relevant results ranked higher (scores can increase 5-6x)
- Better sorting of search results
- Works best when combined with `fuzzy=true` for maximum flexibility

**Query Expansion Examples:**

```bash
# Enhanced relevance scoring
curl "http://localhost:8000/api/serps?query=climate&expand_synonyms=true"
# Top result score: ~85 vs ~14 without expansion

# Combine with fuzzy matching for best results
curl "http://localhost:8000/api/serps?query=climat&expand_synonyms=true&fuzzy=true&fuzziness=1"

# Compare scores with and without expansion
curl "http://localhost:8000/api/serps?query=climate&expand_synonyms=false"
curl "http://localhost:8000/api/serps?query=climate&expand_synonyms=true"
```

**Note:** When both `advanced_mode=true` and `fuzzy=true` are set, `advanced_mode` takes precedence.

**Advanced Search Mode:**

When `advanced_mode=true`, the search query supports:

1. **Boolean Operators** (case-insensitive):
   - `AND` - Both terms must be present
   - `OR` - Either term must be present
   - Example: `climate AND change` or `solar OR wind`

2. **Phrase Search** (exact match):
   - Use double quotes for exact phrases
   - Example: `"climate change"` matches only exact phrase

3. **Wildcards**:
   - `*` - Matches zero or more characters
   - `?` - Matches exactly one character
   - Example: `climat*` matches climate, climatic, climatology, etc.
   - Example: `cl?mate` matches climate, clamate, etc.

4. **Grouping with Parentheses**:
   - Use `()` to group expressions and control operator precedence
   - Example: `(renewable OR solar) AND energy`

**Advanced Search Examples:**

```bash
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

**Note:** In simple mode (`advanced_mode=false`, default), operators like "AND" and "OR" are treated as literal search terms.

**Query Parameters for Preview Endpoint:**

- `query` (required) - Search term for aggregation
- `top_n_queries` - Number of top queries to return (default: 10)
- `interval` - Histogram interval: `day`, `week`, `month` (default: `month`)
- `top_providers` - Number of top providers to return (default: 5)
- `top_archives` - Number of top archives to return (default: 5)
- `last_n_months` - Limit histogram to last N months (optional, default: 36)

**Example Preview Requests:**

```bash
# Get overview statistics for a query
curl http://localhost:8000/api/serps/preview?query=climate

# Get statistics with custom intervals and limits
curl http://localhost:8000/api/serps/preview?query=climate&interval=week&top_providers=10&last_n_months=12

# Get top 20 queries with daily histogram
curl http://localhost:8000/api/serps/preview?query=python&top_n_queries=20&interval=day
```

**Query Parameters for Suggestions Endpoint:**

- `prefix` (required) - Query prefix to search for suggestions
- `size` - Number of suggestions to return (default: 10, range: 1-50)
- `last_n_months` - Filter to last N months of data (default: 36, can be None to disable)

**Example Suggestions Requests:**

```bash
# Get top 5 suggestions for "python"
curl http://localhost:8000/api/suggestions?prefix=python&size=5

# Get suggestions for "the" from last 12 months
curl http://localhost:8000/api/suggestions?prefix=the&last_n_months=12

# Get suggestions with all parameters
curl http://localhost:8000/api/suggestions?prefix=test&size=20&last_n_months=24
```

**Query Parameters for Compare Endpoint:**

- `ids` (required) - Comma-separated list of SERP IDs (2-5 IDs)

**Example Compare Requests:**

```bash
# Compare 2 SERPs
curl "http://localhost:8000/api/serps/compare?ids=abc123,def456"

# Compare 3 SERPs
curl "http://localhost:8000/api/serps/compare?ids=id1,id2,id3"

# Compare 5 SERPs (maximum)
curl "http://localhost:8000/api/serps/compare?ids=id1,id2,id3,id4,id5"
```

**Compare Response includes:**

- Comparison summary (total unique URLs, common URLs count, average similarity)
- Full metadata for each SERP (query, provider, timestamp, status)
- URL comparison (common URLs, unique URLs per SERP)
- Ranking comparison (position differences for common URLs)
- Similarity metrics (Jaccard similarity and Spearman correlation for each pair)

#### ✅ Timeline Endpoint

| Method | Endpoint              | Description                       |
| ------ | --------------------- | --------------------------------- |
| GET    | `/api/serps/timeline` | Date histogram counts for a query |

**Query Parameters for Timeline Endpoint:**

- `query` (required) – Query string to match
- `provider_id` – Optional provider filter (e.g., `google`)
- `archive_id` – Optional archive filter (Memento API URL)
- `interval` – `day` | `week` | `month` (default: `month`)
- `last_n_months` – Limit to last N months (default: `36`, `null` to disable)

Note: The `date_histogram` `date` values are returned without time (format `YYYY-MM-DD`).

**Example Timeline Requests:**

```bash
# Basic timeline for a query
curl "http://localhost:8000/api/serps/timeline?query=climate"

# Timeline filtered by provider and archive
curl "http://localhost:8000/api/serps/timeline?query=climate&provider_id=google&archive_id=https://web.archive.org/web"

# Weekly timeline limited to last 12 months
curl "http://localhost:8000/api/serps/timeline?query=climate&interval=week&last_n_months=12"
```

#### ✅ SERP Detail Endpoints

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

**Query Parameters for SERP Detail Endpoint:**

- `view` - View mode: `raw` (default), `unbranded`, or `snapshot`
- `include` - Comma-separated fields: `original_url`, `memento_url`, `related`, `unfurl`, `direct_links`, `unbranded`
- `remove_tracking` - Remove tracking parameters from original URL (requires `include=original_url`)
- `related_size` - Number of related SERPs (requires `include=related`, default: 10)
- `same_provider` - Only return related SERPs from same provider (requires `include=related`)

**SERP View Switcher:**

The SERP detail endpoint supports different view modes to help researchers examine archived SERPs from different perspectives:

1. **Raw View** (`view=raw`, default):
   - Complete SERP data as stored in the database
   - Includes all metadata, results, and archive information
   - Always available

2. **Unbranded View** (`view=unbranded`):
   - Provider-agnostic, normalized view of search results
   - Strips provider-specific branding and formatting
   - Focuses on query and results in a standardized format
   - Available when parsed results exist

3. **Snapshot View** (`view=snapshot`):
   - Redirects to the web archive's memento interface
   - Shows the original SERP as it appeared in the archive
   - Available when memento URL can be constructed

**View Discovery:**

Use `/api/serps/{serp_id}/views` to discover which views are available for a specific SERP. The response includes:
- View type and label
- Description of what the view provides
- Availability status
- Direct URL to access the view
- Reason if view is unavailable

**Example View Switcher Requests:**

```bash
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

#### ✅ Archive Endpoints

| Method | Endpoint                     | Description                                    |
| ------ | ---------------------------- | ---------------------------------------------- |
| GET    | `/api/archives`              | List all available web archives in the dataset |
| GET    | `/api/archives/{archive_id}` | Get metadata for a specific web archive        |

**Query Parameters for Archives List Endpoint:**

- `limit` - Maximum number of archives to return (default: 100, range: 1-1000)

**Path Parameters for Archive Detail Endpoint:**

- `archive_id` - Memento API URL of the archive (no encoding needed)

**Archive Metadata Fields:**

- `id` - Unique archive identifier (Memento API URL)
- `name` - Human-readable archive name (e.g., "Internet Archive (Wayback Machine)")
- `memento_api_url` - Memento API base URL
- `cdx_api_url` - CDX API URL (from archive data or derived)
- `homepage` - Archive homepage URL
- `serp_count` - Number of SERPs captured from this archive

**Example Archive Requests:**

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

**Example Response for Individual Archive:**

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

#### ✅ Providers Endpoints

| Method | Endpoint                                   | Description                                         |
| ------ | ------------------------------------------ | --------------------------------------------------- |
| GET    | `/api/providers?size=uint`                 | Get all available search providers                  |
| GET    | `/api/providers/{provider_id}`             | Get metadata for a specific search provider         |
| GET    | `/api/providers/{provider_id}/statistics`  | Get descriptive statistics for a search provider    |

**Provider Identifier Resolution:**

Both provider endpoints accept either a **provider UUID** or a **provider name**:

- By name: `/api/providers/google`
- By UUID: `/api/providers/f205fc44-d918-4b79-9a7f-c1373a6ff9f2`

The API automatically resolves the identifier to the correct provider by:
1. First trying it as a UUID (direct lookup in `aql_providers` index)
2. If not found, searching by provider name
3. Returns 404 if neither lookup succeeds

**Query Parameters for Provider Statistics Endpoint:**

- `interval` - Histogram interval: `day`, `week`, `month` (default: `month`)
- `last_n_months` - Limit histogram to last N months (default: 36, can be None to disable)

**Provider Statistics Response includes:**

- Total number of archived SERPs
- Number of unique queries
- Date range of captures
- Top web archives used by this provider
- Date histogram of captures over time

**Example Provider Requests:**

```bash
# Get provider metadata by name
curl http://localhost:8000/api/providers/google

# Get provider metadata by UUID
curl http://localhost:8000/api/providers/f205fc44-d918-4b79-9a7f-c1373a6ff9f2

# Get statistics for a provider (by name)
curl http://localhost:8000/api/providers/google/statistics

# Get statistics with custom interval and time range (by name)
curl http://localhost:8000/api/providers/google/statistics?interval=week&last_n_months=12

# Get statistics by UUID
curl http://localhost:8000/api/providers/f205fc44-d918-4b79-9a7f-c1373a6ff9f2/statistics

# Get daily statistics for all available data
curl http://localhost:8000/api/providers/google/statistics?interval=day&last_n_months=null
```

#### ✅ Archive Statistics Endpoints

| Method | Endpoint                                | Description                                    |
| ------ | --------------------------------------- | ---------------------------------------------- |
| GET    | `/api/archives/{archive_id}/statistics` | Get descriptive statistics for a web archive   |

**Query Parameters for Archive Statistics Endpoint:**

- `interval` - Histogram interval: `day`, `week`, `month` (default: `month`)
- `last_n_months` - Limit histogram to last N months (default: 36, can be None to disable)

**Archive Statistics Response includes:**

- Total number of archived SERPs
- Number of unique queries
- Date range of captures
- Top search providers in this archive
- Date histogram of captures over time

**Example Archive Statistics Requests:**

```bash
# Get statistics for Internet Archive
curl "http://localhost:8000/api/archives/https://web.archive.org/web/statistics"

# Get statistics with custom interval and time range
curl "http://localhost:8000/api/archives/https://web.archive.org/web/statistics?interval=week&last_n_months=12"

# Get daily statistics for arquivo.pt archive
curl "http://localhost:8000/api/archives/https://arquivo.pt/wayback/statistics?interval=day"
```

---

## ⚙️ For Developers (Development)

### Developer Requirements

- Python 3.13 installed
- Git installed

### Setting Up Local Development Environment

**Note:** Make sure to configure your openVPN and [`.env`](#environment-variables) file with the required Elasticsearch credentials before running the development server.

1. **Create a virtual environment:**

```bash
python3.13 -m venv venv
```

1. **Activate the virtual environment:**

```bash
# Linux / Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

1. **Install dependencies:**

```bash
pip install -r requirements.txt
```

1. **Start the development server:**

```bash
uvicorn app.main:app --reload
```

- API available at: [http://localhost:8000](http://localhost:8000)

1. **Run tests:**

```bash
pytest -v

# With coverage:
pytest --cov=app

# Generate XML coverage report:
pytest --cov-report=xml
```

1. **Check code quality:**

```bash
black app/ tests/          # Format code
flake8 app/ tests/         # Linting
mypy app/                  # Type checking
```

---

## 📁 Project Structure

```text
.
├── app/                        
│   ├── main.py                 # FastAPI app & configuration
│   ├── routers/               
│   │   └── search.py           # SERP & Search endpoints
│   ├── models/                
│   │   └── __init__.py
│   ├── schemas/               
│   │   └── aql.py
│   ├── utils/
│   │   ├── url_cleaner.py 
│   │   └── url_unfurler.py 
│   ├── services/          
│   │   └── aql_service.py      # Elasticsearch AQL operations
│   └── core/                   
│       ├── elastic.py          # Elasticsearch client
│       └── settings.py         # Pydantic settings with .env
├── tests/                      
│   ├── conftest.py             # Pytest fixtures, including mocked Elasticsearch
│   ├── aql_services/    
│   │   ├── test_aql_service_archive_metadata.py
│   │   ├── test_aql_service_archive_statistics.py
│   │   ├── test_aql_service_autocomplete.py
│   │   ├── test_aql_service_compare.py
│   │   ├── test_aql_service_direct_links.py
│   │   ├── test_aql_service_preview.py
│   │   ├── test_aql_service_provider_by_id.py
│   │   ├── test_aql_service_provider_statistics.py
│   │   ├── test_aql_service_related_serps.py
│   │   ├── test_aql_service_search.py
│   │   ├── test_aql_service_search_suggestions.py
│   │   ├── test_aql_service_serp_by_id.py
│   │   ├── test_aql_service_serp_memento_url.py
│   │   ├── test_aql_service_serp_original_url.py
│   │   ├── test_aql_service_serp_unfurl.py
│   │   ├── test_aql_service_timeline.py
│   │   └── test_aql_service_unbranded.py
│   ├── search_router/    
│   │   ├── test_search_router_archive_detail.py
│   │   ├── test_search_router_archives.py
│   │   ├── test_search_router_archives_detail_canonical.py
│   │   ├── test_search_router_archive_statistics.py
│   │   ├── test_search_router_compare.py
│   │   ├── test_search_router_direct_links.py
│   │   ├── test_search_router_edge_cases.py
│   │   ├── test_search_router_error_handling.py
│   │   ├── test_search_router_legacy_endpoints.py
│   │   ├── test_search_router_pagination.py
│   │   ├── test_search_router_preview.py
│   │   ├── test_search_router_provider_by_id.py
│   │   ├── test_search_router_provider_statistics.py
│   │   ├── test_search_router_safe_search.py
│   │   ├── test_search_router_serp_detail.py
│   │   ├── test_search_router_suggestions.py
│   │   ├── test_search_router_timeline.py
│   │   └── test_search_router_unified_search_endpoint.py
│   ├── test_autocomplete.py
│   ├── test_elastic.py
│   ├── test_main.py
│   ├── test_search_basic.py
│   ├── test_search_advanced.py
│   └── test_search_router_unbranded.py
├── requirements.txt            
├── Dockerfile     
├── .flake8             
├── docker-compose.yml                        
├── .gitignore                  
├── .env.example   
├── .gitlab-ci.yml
├── mypy.ini
├── pytest.ini                     
└── README.md                   
```

---

## 📚 API Documentation

FastAPI generates interactive API documentation automatically:

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 🔧 Extending the Project

### Add a New Router

1. **Create router file:** `app/routers/users.py`

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/users")
async def get_users():
    return {"users": []}
```

1. **Register in main.py:**

```python
from app.routers import users
app.include_router(users.router, prefix="/api", tags=["users"])
```

### Add a Database

1. **Add dependencies to `requirements.txt`**

```bash
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
```

1. **Create database setup in `app/database.py`**  
2. **Define models in `app/models/`**  
3. **Add PostgreSQL service in `docker-compose.yml`**

### Environment Variables

1. **Create `.env`:**

```bash
ES_HOST=https://elasticsearch.srv.webis.de:9200
ES_API_KEY=<API_KEY>
ES_VERIFY=False
```

1. **Use Pydantic Settings:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    es_host: str
    es_api_key: str | None = None
    es_verify: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 🛠 CI/CD Pipeline

The project uses GitLab CI/CD with three stages:

### Test Stage

- Runs pytest with coverage  
- Code quality checks (`black`, `flake8`)  
- Automatically mocks Elasticsearch (no network needed)  
- Runs on every push and merge request  

### Build Stage

- Builds Docker image  
- Pushes to GitLab Container Registry  
- Tags: `latest` for main branch, branch name otherwise  
- Runs only if tests pass  

### Deploy Stage (Optional)

- Manual trigger  
- Can deploy to Kubernetes, Docker Compose, etc.  

---

## ⚡ Important Commands

```bash
# Development
uvicorn app.main:app --reload
pytest -v
pytest --cov=app
black app/ tests/
flake8 app/ tests/
mypy app/

# Docker
docker compose up --build
docker compose down
docker compose logs -f fastapi

# GitLab Container Registry
docker login git.uni-jena.de:5050
docker push $CI_REGISTRY_IMAGE:latest
```

---

## 🤝 Contributing

1. Create a feature branch  
2. Commit changes  
3. Write/update tests  
4. Format code (`black`, `flake8`)  
5. Create a merge request  

---

## 🔒 Content Filtering

### Hidden SERPs Filter

The backend is prepared to filter out hidden SERPs (marked as spam, porn, or other problematic content) from all search results and aggregations.

**Current Status:**

- ✅ Filter logic implemented in all SERP-related Elasticsearch queries
- ⏳ Waiting for `hidden` flag to be added to Elasticsearch `aql_serps` index

**Implementation Details:**

- A helper function `_add_hidden_filter()` adds the filter to all queries that access `aql_serps`
- Affected functions: `search_basic()`, `search_advanced()`, `search_suggestions()`, `preview_search()`, `get_archive_metadata()`, `list_all_archives()`
- Filter clause: `{"bool": {"must_not": [{"term": {"hidden": True}}]}}`
  - This means: `hidden != True` (excludes only documents where hidden is explicitly True)
  - **Backwards compatible**: Accepts documents where the field is missing or False
- Once the `hidden` field is added to the index, filtering will work automatically without code changes

**Next Steps (Research Project):**

- Add `hidden` boolean field to Elasticsearch documents in `aql_serps` index
- Mark problematic SERPs with `hidden: True`
- Filter will be automatically applied to all API responses (no code changes needed)

---

## 📄 License

This project is a FastAPI starter template for building extensible web APIs.
