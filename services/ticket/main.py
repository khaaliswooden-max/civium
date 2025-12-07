"""
Pro-Ticket: Service Management.

Main FastAPI application for ticket management, AI triage,
and SLA prediction.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.settings import get_settings
from shared.logging.logger import get_logger
from services.ticket.routes import (
    tickets_router,
    triage_router,
    sla_router,
)


logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Pro-Ticket service", port=settings.ticket_port)
    yield
    logger.info("Shutting down Pro-Ticket service")


app = FastAPI(
    title="Pro-Ticket",
    description="AI-Powered Service Management & SLA Prediction",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "tickets", "description": "Ticket CRUD operations"},
        {"name": "triage", "description": "AI-powered ticket classification and routing"},
        {"name": "sla", "description": "SLA prediction and management"},
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
app.include_router(tickets_router, prefix="/api/v1")
app.include_router(triage_router, prefix="/api/v1")
app.include_router(sla_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, Any]:
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "pro-ticket",
        "version": "1.0.0",
        "components": {
            "triage_engine": "operational",
            "sla_predictor": "operational",
            "knowledge_base": "operational",
        },
    }


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": "Pro-Ticket",
        "description": "AI-Powered Service Management & SLA Prediction",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.ticket.main:app",
        host="0.0.0.0",
        port=settings.ticket_port,
        reload=settings.debug,
    )

