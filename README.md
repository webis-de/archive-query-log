# FastAPI Starter Project

A minimal yet extensible FastAPI project with modern project structure, tests, Elasticsearch (AQL) integration, and Docker support.

## 📋 Table of Contents

- [For Users (Deployment & Usage)](#-for-users-deployment--usage)
- [For Developers (Development)](#-for-developers-development)
- [Project Structure](#-project-structure)
- [API Documentation](#-api-documentation)
- [Extending the Project](#-extending-the-project)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Important Commands](#-important-commands)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🚀 For Users (Deployment & Usage)

### Requirements
- Docker & Docker Compose installed
- Port 8000 available

### Configuration

Create a [`.env`](#Environment Variables) file in the project root.

### Installation & Start with Docker

1. **Clone the repository:**
```bash
git clone git@git.uni-jena.de:fusion/teaching/project/2025wise/swep/aql-browser/backend.git
cd backend
```

2. **Start the containers:**
```bash
docker compose up -d
```

3. **Test the API:**
```bash
curl http://localhost:8000/
```

... or open [http://localhost:8000/docs](http://localhost:8000/docs) in your browser for the Swagger UI.

4. **Stop the containers:**
```bash
docker compose down
```

### Available Endpoints

**To access the Elasticsearch data, the endpoints require a VPN connection to `vpn.webis.de` (via OpenVPN Connect, see Issue #7).**

- `GET /` - Root endpoint (Health Check)
- `GET /health` - Health Check
- `GET /api/search/basic?query=term` - Basic SERP search
- `GET /api/search/providers?name=provider` - Search for providers
- `GET /api/search/advanced` - Advanced search with filters
- `GET /api/autocomplete/providers?q=prefix` - Autocomplete provider names
- `GET /api/search/by-year?query=term&year=YYYY` - Search by year
- `GET /docs` - Swagger UI interactive API documentation
- `GET /redoc` - ReDoc API documentation
- `GET /api/serp/{serp_id}` - Get a single SERP by ID
- `GET /api/serp/{serp_id}/original-url` - Get the original SERP URL by ID
    -  `?remove_tracking=bool` - get URL with tracking parameters removed (default=false)
---

## ⚙️ For Developers (Development)

### Requirements
- Python 3.13 installed
- Git installed

### Setting Up Local Development Environment
**Note:** Make sure to configure your [`.env`](#environment-variables) file with the required Elasticsearch credentials before running the development server. 

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

### Docker for Development

**Start containers with hot reload:**
```bash
docker compose up
```

**Rebuild containers after changes:**
```bash
docker compose up --build
```

**View logs:**
```bash
docker compose logs -f fastapi
```

### Manual Docker Build & Push to GitLab Registry

1. **Login to GitLab Container Registry:**
```bash
docker login git.uni-jena.de:5050
# Username: <your-username>
# Password: <personal-access-token>
```

2. **Build Docker image:**
```bash
docker build -t fastapi-app .
```

3. **Tag image:**
```bash
docker tag fastapi-app git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/archive-query-log:latest
```

4. **Push image:**
```bash
docker push git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/archive-query-log:latest
```

**One-liner (all steps combined):**
```bash
docker build -t git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/archive-query-log:latest . && \
docker push git.uni-jena.de:5050/fusion/teaching/project/2025wise/swep/aql-browser/archive-query-log:latest
```

---

## 📁 Project Structure

```
.
├── app/                        
│   ├── main.py                 # FastAPI app & configuration
│   ├── routers/               
│   │   ├── hello.py            # Example router
│   │   └── search.py           # AQL search router (basic, advanced, autocomplete, by-year)
│   ├── models/                
│   │   └── __init__.py
│   ├── schemas/               
│   │   └── aql.py
│   ├── services/          
│   │   └── aql_service.py      # Elasticsearch AQL operations
│   └── core/                   
│       ├── elastic.py          # Elasticsearch client
│       └── settings.py         # Pydantic settings with .env
├── tests/                      
│   ├── conftest.py             # Pytest fixtures, including mocked Elasticsearch
│   ├── test_main.py
│   ├── test_hello.py
│   ├── test_search_basic.py
│   ├── test_search_advanced.py
│   ├── test_autocomplete.py
│   └── search_by_year.py
├── requirements.txt            
├── Dockerfile                  
├── docker-compose.yml          
├── .dockerignore               
├── .gitignore                  
├── .env                        
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
