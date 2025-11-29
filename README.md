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
  - [� API Documentation](#-api-documentation)
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

1. **Start the container:**
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

#### ✅ SERP Detail Endpoints
| Method | Endpoint                                                | Description                                                |
| ------ | ------------------------------------------------------- | ---------------------------------------------------------- |
| GET    | `/api/serp/{serp_id}`                                   | Get a single SERP by ID                                    |
| GET    | `/api/serp/{serp_id}/original-url&remove_tracking=bool` | Get original SERP URL optional removed tracking parameters |
| GET    | `/api/serp/{serp_id}/memento-url`                       | Get Memento SERP URL                                       |
| GET    | `/api/serp/{serp_id}/related?size=X&same_provider=bool` | Get related SERPs                                          |
| GET    | `/api/serp/{serp_id}/unfurl`                            | Get unfurled destination URL from redirect chain           |

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
