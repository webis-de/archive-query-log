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
| Method | Endpoint                                                | Description          |
| ------ | ------------------------------------------------------- | -------------------- |
| GET    | `/api/serps?query=climate+change`                       | Basic SERP search    |
| GET    | `/api/serps?query=climate&year=2024&provider_id=google` | Advanced SERP search |
| GET    | `/api/serps/preview?query=climate`                      | Preview aggregations / suggestions for query |

**Query Parameters for Search Endpoint:**
- `query` (required) - Search term
- `page_size` - Results per page (default: 10, options: 10, 20, 50)
- `page_size` - Results per page (default: 10, options: 10, 20, 50, 100, 1000)
- `page` - Page number (1-based). Use together with `page_size` to navigate pages, e.g. `?query=climate&page_size=20&page=2`.
- `provider_id` - Filter by provider ID (optional)
- `year` - Filter by year (optional)
- `status_code` - Filter by HTTP status code (optional)


#### ✅ SERP Detail Endpoints
| Method | Endpoint                                                | Description                                                |
| ------ | ------------------------------------------------------- | ---------------------------------------------------------- |
| GET    | `/api/serp/{serp_id}`                                   | Get a single SERP by ID                                    |
| GET    | `/api/serp/{serp_id}?include=original_url`              | Include original SERP URL                                  |
| GET    | `/api/serp/{serp_id}?include=memento_url`               | Include Memento SERP URL                                   |
| GET    | `/api/serp/{serp_id}?include=related&related_size=X`    | Include related SERPs                                      |
| GET    | `/api/serp/{serp_id}?include=unfurl`                    | Include unfurled URL components                            |
| GET    | `/api/serp/{serp_id}?include=direct_links`              | Include direct search result links                         |
| GET    | `/api/serp/{serp_id}?include=unbranded`                 | Include provider-agnostic unified view                     |

**Query Parameters for SERP Detail Endpoint:**
- `include` - Comma-separated fields: `original_url`, `memento_url`, `related`, `unfurl`, `direct_links`, `unbranded`
- `remove_tracking` - Remove tracking parameters from original URL (requires `include=original_url`)
- `related_size` - Number of related SERPs (requires `include=related`, default: 10)
- `same_provider` - Only return related SERPs from same provider (requires `include=related`)

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
│   │   ├── test_aql_service_autocomplete.py
│   │   ├── test_aql_service_direct_links.py
│   │   ├── test_aql_service_related_serps.py 
│   │   ├── test_aql_service_search.py
│   │   ├── test_aql_service_serp_by_id.py
│   │   ├── test_aql_service_serp_memento_url.py
│   │   ├── test_aql_service_serp_original_url.py
│   │   ├── test_aql_service_serp_unfurl.py
│   │   ├── test_aql_service_unbranded.py
│   │   └── test_aql_service_preview.py      
│   ├── search_router/    
│   │   ├── test_search_router_direct_links.py
│   │   ├── test_search_router_edge_cases.py
│   │   ├── test_search_router_legacy_endpoints.py
│   │   ├── test_search_router_pagination.py
│   │   ├── test_search_router_safe_search.py
│   │   ├── test_search_router_serp_detail.py    
│   │   ├── test_search_router_unified_search_endpoint.py
│   │   └── test_search_router_preview.py
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
