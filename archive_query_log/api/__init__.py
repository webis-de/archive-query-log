"""FastAPI Main Application

This is the entry point for the FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import RouteMap, MCPType
from slowapi import Limiter
from slowapi.util import get_remote_address

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

# Configure routers.
app.include_router(monitoring_router, tags=["monitoring"])
app.include_router(serps_router, tags=["serps"], prefix="/serps")
app.include_router(providers_router, tags=["providers"], prefix="/providers")
app.include_router(archives_router, tags=["archives"], prefix="/archives")

# Configure and mount MCP server.
mcp = FastMCP.from_fastapi(
    app=app,
    name="AQL MCP API",
    # include_operations=[
    #     "search_serps",
    #     "search_providers",
    #     "search_archives",
    # ],
    instructions="""
    This server provides data analysis tools for the Archive Query Log.
    """.lstrip(),
    route_maps=[
        RouteMap(
            methods=["PUT", "POST", "DELETE", "PATCH"],
            mcp_type=MCPType.EXCLUDE,
        ),
        RouteMap(
            tags={"monitoring"},
            mcp_type=MCPType.EXCLUDE,
        ),
    ],
)


# Create a new FastAPI app to serve the MCP endpoints under the /mcp prefix.
mcp_app = mcp.http_app(path="/")
# Attach the MCP app's lifespan context to the main app.
# Note: This overrides the current lifespan context of the main app.
app.router.lifespan_context = mcp_app.router.lifespan_context
app.mount("/mcp", mcp_app)


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


# Add health endpoint.
@app.get("/health")
async def health_check() -> str:
    """
    Check the health of the application.
    """
    return "healthy"
