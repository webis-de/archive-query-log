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
      - [✅ Archive Endpoints (vereinheitlicht)](#-archive-endpoints-vereinheitlicht)
      - [✅ Providers Endpoints](#-providers-endpoints)
  - [| GET    | `/api/providers?size=uint` | Get all available search providers (optional: get number of providers) |](#-get-----apiproviderssizeuint--get-all-available-search-providers-optional-get-number-of-providers-)
  - [⚙️ For Developers (Development)](#️-for-developers-development)
    - [Requirements](#requirements-1)
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


#### ✅ SERP Detail Endpoints
| Method | Endpoint                                             | Description                            |
| ------ | ---------------------------------------------------- | -------------------------------------- |
| GET    | `/api/serp/{serp_id}`                                | Get a single SERP by ID                |
| GET    | `/api/serp/{serp_id}?include=original_url`           | Include original SERP URL              |
| GET    | `/api/serp/{serp_id}?include=memento_url`            | Include Memento SERP URL               |
| GET    | `/api/serp/{serp_id}?include=related&related_size=X` | Include related SERPs                  |
| GET    | `/api/serp/{serp_id}?include=unfurl`                 | Include unfurled URL components        |
| GET    | `/api/serp/{serp_id}?include=direct_links`           | Include direct search result links     |
| GET    | `/api/serp/{serp_id}?include=unbranded`              | Include provider-agnostic unified view |

**Query Parameters for SERP Detail Endpoint:**
- `include` - Comma-separated fields: `original_url`, `memento_url`, `related`, `unfurl`, `direct_links`, `unbranded`
- `remove_tracking` - Remove tracking parameters from original URL (requires `include=original_url`)
- `related_size` - Number of related SERPs (requires `include=related`, default: 10)
- `same_provider` - Only return related SERPs from same provider (requires `include=related`)

#### ✅ Archive Endpoints
| Method | Endpoint                       | Description                                    |
| ------ | ------------------------------ | ---------------------------------------------- |
| GET    | `/api/archives`                | List all available web archives in the dataset |
| GET    | `/api/archives/{archive_id}`   | Get metadata for a specific web archive       |

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
| Method | Endpoint                   | Description                                                            |
| ------ | -------------------------- | ---------------------------------------------------------------------- |
| GET    | `/api/providers?size=uint` | Get all available search providers (optional: get number of providers) |
---

## ⚙️ For Developers (Development)

### Requirements
- Python 3.13 installed
- Git installed

### Setting Up Local Development Environment
**Note:** Make sure to configure your openVPN and [`.env`](#environment-variables) file with the required Elasticsearch credentials before running the development server. 

1. **Create a virtual environment:**
```bash
python3.13 -m venv venv
```

2. **Activate the virtual environment:**
```bash
# Linux / Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Start the development server:**
```bash
uvicorn app.main:app --reload
```
- API available at: [http://localhost:8000](http://localhost:8000)

5. **Run tests:**
```bash
pytest -v

# With coverage:
pytest --cov=app

# Generate XML coverage report:
pytest --cov-report=xml
```

6. **Check code quality:**
```bash
black app/ tests/          # Format code
flake8 app/ tests/         # Linting
mypy app/                  # Type checking
```
---

## 📁 Project Structure

```
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
│   │   ├── test_aql_service_autocomplete.py
│   │   ├── test_aql_service_compare.py
│   │   ├── test_aql_service_direct_links.py
│   │   ├── test_aql_service_preview.py
│   │   ├── test_aql_service_provider_by_id.py
│   │   ├── test_aql_service_related_serps.py
│   │   ├── test_aql_service_search.py
│   │   ├── test_aql_service_search_suggestions.py
│   │   ├── test_aql_service_serp_by_id.py
│   │   ├── test_aql_service_serp_memento_url.py
│   │   ├── test_aql_service_serp_original_url.py
│   │   ├── test_aql_service_serp_unfurl.py
│   │   └── test_aql_service_unbranded.py
│   ├── search_router/    
│   │   ├── test_search_router_archive_detail.py
│   │   ├── test_search_router_archives.py
│   │   ├── test_search_router_archives_detail_canonical.py
│   │   ├── test_search_router_compare.py
│   │   ├── test_search_router_direct_links.py
│   │   ├── test_search_router_edge_cases.py
│   │   ├── test_search_router_error_handling.py
│   │   ├── test_search_router_legacy_endpoints.py
│   │   ├── test_search_router_pagination.py
│   │   ├── test_search_router_preview.py
│   │   ├── test_search_router_provider_by_id.py
│   │   ├── test_search_router_serp_detail.py
│   │   ├── test_search_router_unified_search_endpoint.py
│   │   └── test_search_router_unbranded.py
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

2. **Register in main.py:**
```python
from app.routers import users
app.include_router(users.router, prefix="/api", tags=["users"])
```

### Add a Database

1. **Add dependencies to `requirements.txt`**
```
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
```

2. **Create database setup in `app/database.py`**  
3. **Define models in `app/models/`**  
4. **Add PostgreSQL service in `docker-compose.yml`**

### Environment Variables

1. **Create `.env`:**
```
ES_HOST=https://elasticsearch.srv.webis.de:9200
ES_API_KEY=<API_KEY>
ES_VERIFY=False
```

2. **Use Pydantic Settings:**
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

## 📄 License

This project is a FastAPI starter template for building extensible web APIs.
