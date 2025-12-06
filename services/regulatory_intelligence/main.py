"""
Regulatory Intelligence Service - Main Application
===================================================

FastAPI application for regulatory document ingestion and parsing.

Version: 0.1.0
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from services.regulatory_intelligence.routes import (
    ingestion,
    pipeline,
    regulations,
    requirements,
)
from shared.config import settings
from shared.database.mongodb import MongoDBClient
from shared.database.redis import RedisClient
from shared.logging import get_logger, setup_logging
from shared.models.common import HealthResponse


# Setup logging
setup_logging(
    log_level=settings.log_level.value,
    json_logs=settings.is_production,
    service_name="regulatory-intelligence",
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    """Application lifespan manager."""
    logger.info(
        "regulatory_intelligence_starting",
        environment=settings.environment.value,
        port=settings.ports.regulatory_intelligence,
    )

    # Startup
    try:
        # Initialize MongoDB connection
        MongoDBClient.get_client()
        await MongoDBClient.create_indexes()
        logger.info("mongodb_connected")

        # Initialize Redis
        RedisClient.get_client()
        logger.info("redis_connected")

    except Exception as e:
        logger.error("startup_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("regulatory_intelligence_shutting_down")
    await MongoDBClient.close()
    await RedisClient.close()


# Create FastAPI application
app = FastAPI(
    title="Civium Regulatory Intelligence Service",
    description="NLP-powered regulatory parsing and ingestion",
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

    # Check MongoDB
    mongo_health = await MongoDBClient.health_check()
    components["mongodb"] = mongo_health

    # Check Redis
    redis_health = await RedisClient.health_check()
    components["redis"] = redis_health

    # Determine overall status
    all_healthy = all(c.get("status") == "healthy" for c in components.values())

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        service="regulatory-intelligence",
        version="0.1.0",
        components=components,
    )


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Civium Regulatory Intelligence Service",
        "version": "0.1.0",
        "docs": "/docs",
    }


# ============================================================================
# Include Routers
# ============================================================================

app.include_router(
    regulations.router,
    prefix="/api/v1/regulations",
    tags=["Regulations"],
)

app.include_router(
    requirements.router,
    prefix="/api/v1/requirements",
    tags=["Requirements"],
)

app.include_router(
    ingestion.router,
    prefix="/api/v1/ingest",
    tags=["Ingestion"],
)

app.include_router(
    pipeline.router,
    prefix="/api/v1/pipeline",
    tags=["Pipeline"],
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
        "services.regulatory_intelligence.main:app",
        host="0.0.0.0",
        port=settings.ports.regulatory_intelligence,
        reload=settings.debug,
        log_level=settings.log_level.value.lower(),
    )
