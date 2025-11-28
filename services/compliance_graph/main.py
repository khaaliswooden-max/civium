"""
Compliance Graph Service - Main Application
============================================

FastAPI application for the Neo4j-powered compliance knowledge graph.

Version: 0.1.0
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from shared.config import settings
from shared.logging import get_logger, setup_logging
from shared.database.neo4j import Neo4jClient
from shared.database.redis import RedisClient
from shared.models.common import HealthResponse

from services.compliance_graph.routes import graph, entities, conflicts

# Setup logging
setup_logging(
    log_level=settings.log_level.value,
    json_logs=settings.is_production,
    service_name="compliance-graph",
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    logger.info(
        "compliance_graph_starting",
        environment=settings.environment.value,
        port=settings.ports.compliance_graph,
    )

    # Startup
    try:
        # Initialize Neo4j
        Neo4jClient.get_driver()
        logger.info("neo4j_connected")

        # Initialize Redis
        RedisClient.get_client()
        logger.info("redis_connected")

    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("compliance_graph_shutting_down")
    await Neo4jClient.close()
    await RedisClient.close()


# Create FastAPI application
app = FastAPI(
    title="Civium Compliance Graph Service",
    description="Neo4j-powered compliance knowledge graph engine",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.origins_list,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Service health check.

    Returns health status of the service and its dependencies.
    """
    components: dict[str, dict[str, Any]] = {}

    # Check Neo4j
    neo4j_health = await Neo4jClient.health_check()
    components["neo4j"] = neo4j_health

    # Check Redis
    redis_health = await RedisClient.health_check()
    components["redis"] = redis_health

    # Determine overall status
    all_healthy = all(
        c.get("status") == "healthy" for c in components.values()
    )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        service="compliance-graph",
        version="0.1.0",
        components=components,
    )


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Civium Compliance Graph Service",
        "version": "0.1.0",
        "docs": "/docs",
    }


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(
    graph.router,
    prefix="/api/v1/graph",
    tags=["Graph Operations"],
)

app.include_router(
    entities.router,
    prefix="/api/v1/entities",
    tags=["Entity Graph"],
)

app.include_router(
    conflicts.router,
    prefix="/api/v1/conflicts",
    tags=["Conflict Detection"],
)


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Any, exc: HTTPException) -> Any:
    """Handle HTTP exceptions."""
    from fastapi.responses import JSONResponse

    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Any, exc: Exception) -> Any:
    """Handle unexpected exceptions."""
    from fastapi.responses import JSONResponse

    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "status_code": 500,
        },
    )


# ============================================================================
# Run with Uvicorn
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.compliance_graph.main:app",
        host="0.0.0.0",
        port=settings.ports.compliance_graph,
        reload=settings.debug,
        log_level=settings.log_level.value.lower(),
    )

