"""FastAPI Main Application

This is the entry point for the FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.elastic import close_es_client
from app.routers import hello, search

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
    title="FastAPI Starter Project",
    description="A minimal FastAPI project template ready for extension",
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
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests, slow down!"}
    )

# ---------------------------------------------------------
# Include routers
# ---------------------------------------------------------
app.include_router(hello.router, prefix="/api", tags=["hello"])
app.include_router(search.router, prefix="/api", tags=["search"])

# ---------------------------------------------------------
# Root & Health Endpoints
# ---------------------------------------------------------
@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "message": "FastAPI is running!",
        "version": "0.1.0",
        "status": "healthy",
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
