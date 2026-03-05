"""FastAPI Main Application

This is the entry point for the FastAPI application.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_mcp import FastApiMCP
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from archive_query_log import __version__ as app_version
from archive_query_log.api.routers.monitoring import router as monitoring_router
from archive_query_log.api.routers.serps import router as serps_router
from archive_query_log.api.routers.providers import router as providers_router
from archive_query_log.api.routers.archives import router as archives_router


# Create FastAPI app.
app = FastAPI(
    title="AQL API",
    description="Access and explore data from the Archive Query Log.",
    version=app_version,
)

# Setup CORS middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup rate limiter.
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter


# Setup global rate limit handler.
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too Many Requests",
            "message": str(exc.detail),
            "status_code": 429,
        },
    )


# Configure routers.
app.include_router(monitoring_router, tags=["monitoring"])
app.include_router(serps_router, tags=["serps"], prefix="/serps")
app.include_router(providers_router, tags=["providers"], prefix="/providers")
app.include_router(archives_router, tags=["archives"], prefix="/archives")

# Configure and mount MCP server.
mcp = FastApiMCP(app)
mcp.mount_http()


# Add health endpoint.
@app.get("/health")
async def health_check() -> str:
    """
    Check the health of the application.
    """
    return "healthy"
