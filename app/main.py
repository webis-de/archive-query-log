"""FastAPI Main Application

This is the entry point for the FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.elastic import close_es_client
from app.routers import hello, search
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup code (if any)
    yield
    # shutdown code
    await close_es_client()


# Create FastAPI app instance with lifespan
app = FastAPI(
    title="FastAPI Starter Project",
    description="A minimal FastAPI project template ready for extension",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS - adjust for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(hello.router, prefix="/api", tags=["hello"])
app.include_router(search.router, prefix="/api", tags=["search"])


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
