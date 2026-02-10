"""FastAPI Main Application

This is the entry point for the FastAPI application.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from contextlib import asynccontextmanager

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from archive_query_log.browser.core.elastic import close_es_client
from archive_query_log.browser.routers import search


# ---------------------------------------------------------
# Lifespan for startup/shutdown
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup code (if any)
    yield
    # shutdown code
    await close_es_client()


# ---------------------------------------------------------
# Create FastAPI app
# ---------------------------------------------------------
app = FastAPI(
    title="FastAPI AQL-Browser Backend",
    description="A minimal FastAPI project serving as a proxy between frontend and elasticsearch.",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------
# Configure CORS
# ---------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------
# Setup slowapi Limiter
# ---------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter


# ---------------------------------------------------------
# Global Rate Limit Handler
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Include routers
# ---------------------------------------------------------
app.include_router(search.router, tags=["search"])


# ---------------------------------------------------------
# Root & Health Endpoints
# ---------------------------------------------------------
@app.get("/")
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return "healthy"
