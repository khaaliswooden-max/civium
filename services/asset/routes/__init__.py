"""Pro-Assure API routes."""

from services.asset.routes.warranties import router as warranties_router
from services.asset.routes.claims import router as claims_router
from services.asset.routes.assets import router as assets_router

__all__ = [
    "warranties_router",
    "claims_router",
    "assets_router",
]

