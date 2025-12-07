"""
Pro-Visit: Visitor Management Service.

Main FastAPI application for visitor management, threat assessment,
and access control.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from services.visitor.routes import (
    access_router,
    screening_router,
    visitors_router,
)


logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Pro-Visit service", port=settings.visitor_port)
    yield
    logger.info("Shutting down Pro-Visit service")


app = FastAPI(
    title="Pro-Visit",
    description="AI-Powered Visitor Management & Threat Assessment",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "screening", "description": "Threat assessment and watchlist screening"},
        {"name": "visitors", "description": "Visitor pre-registration and management"},
        {"name": "access", "description": "Zone-based access control"},
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
app.include_router(screening_router, prefix="/api/v1")
app.include_router(visitors_router, prefix="/api/v1")
app.include_router(access_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, Any]:
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "pro-visit",
        "version": "1.0.0",
        "components": {
            "threat_assessment": "operational",
            "identity_verification": "operational",
            "access_control": "operational",
        },
    }


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Pro-Visit",
        "description": "AI-Powered Visitor Management & Threat Assessment",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.visitor.main:app",
        host="0.0.0.0",
        port=settings.visitor_port,
        reload=settings.debug,
    )

