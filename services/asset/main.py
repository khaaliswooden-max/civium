"""
Pro-Assure: Warranty & Asset Management Service.

Main FastAPI application for warranty registry, claims processing,
and asset lifecycle management.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from services.asset.routes import (
    warranties_router,
    claims_router,
    assets_router,
)


logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Pro-Assure service", port=settings.asset_port)
    yield
    logger.info("Shutting down Pro-Assure service")


app = FastAPI(
    title="Pro-Assure",
    description="Blockchain Warranty Registry & Asset Lifecycle Management",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "warranties", "description": "Blockchain warranty registration and management"},
        {"name": "claims", "description": "Warranty claims with fraud detection"},
        {"name": "assets", "description": "Asset lifecycle management"},
        {"name": "health", "description": "Service health checks"},
    ],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(",") if settings.cors_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(warranties_router, prefix="/api/v1")
app.include_router(claims_router, prefix="/api/v1")
app.include_router(assets_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, Any]:
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "pro-assure",
        "version": "1.0.0",
        "components": {
            "warranty_registry": "operational",
            "fraud_detection": "operational",
            "asset_management": "operational",
            "blockchain": "mock_mode",
        },
    }


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Pro-Assure",
        "description": "Blockchain Warranty Registry & Asset Lifecycle Management",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.asset.main:app",
        host="0.0.0.0",
        port=settings.asset_port,
        reload=settings.debug,
    )

