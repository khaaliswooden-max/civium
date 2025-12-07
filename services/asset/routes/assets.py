"""
Asset Management API Endpoints.

Asset lifecycle tracking and management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field


router = APIRouter(prefix="/assets", tags=["assets"])


# In-memory store for development
_assets: dict[str, dict[str, Any]] = {}


class AssetCreate(BaseModel):
    """Request to register a new asset."""

    name: str = Field(..., min_length=2, max_length=200)
    asset_type: str = Field(..., description="Type of asset: hardware, software, vehicle, etc.")
    serial_number: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    purchase_date: datetime | None = None
    purchase_price: float | None = Field(None, ge=0)
    location: str | None = None
    assigned_to: str | None = None
    department: str | None = None
    tags: list[str] = Field(default_factory=list)


class AssetResponse(BaseModel):
    """Asset record response."""

    id: str
    name: str
    asset_type: str
    serial_number: str | None
    manufacturer: str | None
    model: str | None
    purchase_date: datetime | None
    purchase_price: float | None
    location: str | None
    assigned_to: str | None
    department: str | None
    status: str
    warranty_id: str | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class AssetUpdate(BaseModel):
    """Request to update asset."""

    name: str | None = None
    location: str | None = None
    assigned_to: str | None = None
    department: str | None = None
    status: str | None = None
    tags: list[str] | None = None


@router.post(
    "/",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new asset",
)
async def create_asset(asset: AssetCreate) -> AssetResponse:
    """Register a new asset in the system."""
    asset_id = f"AST-{uuid4().hex[:8].upper()}"
    now = datetime.utcnow()

    record = {
        "id": asset_id,
        "name": asset.name,
        "asset_type": asset.asset_type,
        "serial_number": asset.serial_number,
        "manufacturer": asset.manufacturer,
        "model": asset.model,
        "purchase_date": asset.purchase_date,
        "purchase_price": asset.purchase_price,
        "location": asset.location,
        "assigned_to": asset.assigned_to,
        "department": asset.department,
        "status": "active",
        "warranty_id": None,
        "tags": asset.tags,
        "created_at": now,
        "updated_at": now,
    }

    _assets[asset_id] = record
    return AssetResponse(**record)


@router.get(
    "/",
    response_model=list[AssetResponse],
    summary="List assets",
)
async def list_assets(
    asset_type: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    department: str | None = Query(None),
    assigned_to: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[AssetResponse]:
    """List assets with optional filters."""
    assets = list(_assets.values())

    if asset_type:
        assets = [a for a in assets if a["asset_type"] == asset_type]
    if status_filter:
        assets = [a for a in assets if a["status"] == status_filter]
    if department:
        assets = [a for a in assets if a["department"] == department]
    if assigned_to:
        assets = [a for a in assets if a["assigned_to"] == assigned_to]

    return [AssetResponse(**a) for a in assets[offset : offset + limit]]


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Get asset by ID",
)
async def get_asset(asset_id: str) -> AssetResponse:
    """Get a specific asset."""
    if asset_id not in _assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )
    return AssetResponse(**_assets[asset_id])


@router.patch(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Update asset",
)
async def update_asset(asset_id: str, update: AssetUpdate) -> AssetResponse:
    """Update asset information."""
    if asset_id not in _assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )

    record = _assets[asset_id]
    update_data = update.model_dump(exclude_unset=True)
    record.update(update_data)
    record["updated_at"] = datetime.utcnow()

    return AssetResponse(**record)


@router.post(
    "/{asset_id}/assign",
    response_model=AssetResponse,
    summary="Assign asset to user",
)
async def assign_asset(
    asset_id: str,
    user_id: str,
    department: str | None = None,
) -> AssetResponse:
    """Assign asset to a user."""
    if asset_id not in _assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )

    record = _assets[asset_id]
    record["assigned_to"] = user_id
    if department:
        record["department"] = department
    record["status"] = "assigned"
    record["updated_at"] = datetime.utcnow()

    return AssetResponse(**record)


@router.post(
    "/{asset_id}/retire",
    response_model=AssetResponse,
    summary="Retire asset",
)
async def retire_asset(
    asset_id: str,
    reason: str = "",
) -> AssetResponse:
    """Mark asset as retired."""
    if asset_id not in _assets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found",
        )

    record = _assets[asset_id]
    record["status"] = "retired"
    record["retired_at"] = datetime.utcnow()
    record["retirement_reason"] = reason
    record["updated_at"] = datetime.utcnow()

    return AssetResponse(**record)


@router.get(
    "/types",
    response_model=list[str],
    summary="Get asset types",
)
async def get_asset_types() -> list[str]:
    """Get list of asset types."""
    return [
        "hardware",
        "software",
        "vehicle",
        "furniture",
        "equipment",
        "facility",
        "other",
    ]


@router.get(
    "/statuses",
    response_model=list[str],
    summary="Get asset statuses",
)
async def get_asset_statuses() -> list[str]:
    """Get list of asset statuses."""
    return [
        "active",
        "assigned",
        "in_repair",
        "maintenance",
        "retired",
        "disposed",
    ]

