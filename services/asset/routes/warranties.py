"""
Warranty Management API Endpoints.

Blockchain-based warranty registration and management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from services.asset.warranty.registry import BlockchainWarrantyRegistry, WarrantyRecord


router = APIRouter(prefix="/warranties", tags=["warranties"])


# Shared registry instance
_registry = BlockchainWarrantyRegistry()


class WarrantyRegisterRequest(BaseModel):
    """Request to register a new warranty."""

    asset_id: str = Field(..., description="Unique asset identifier")
    serial_number: str = Field(..., description="Product serial number")
    product_type: str = Field(..., description="Type of product")
    manufacturer: str = Field(..., description="Product manufacturer")
    owner_id: str = Field(..., description="Owner identifier")
    owner_name: str = Field(..., description="Owner name")
    coverage_type: str = Field(default="standard", description="Warranty coverage type")
    duration_days: int = Field(default=365, ge=30, le=3650)
    product_value: float = Field(default=0, ge=0)


class WarrantyResponse(BaseModel):
    """Warranty record response."""

    warranty_id: str
    asset_id: str
    serial_number: str
    product_type: str
    manufacturer: str
    purchase_date: datetime
    warranty_start: datetime
    warranty_end: datetime
    coverage_type: str
    current_owner: str
    transfer_count: int
    claims_count: int
    blockchain_hash: str
    is_active: bool

    @classmethod
    def from_record(cls, record: WarrantyRecord) -> WarrantyResponse:
        """Create response from WarrantyRecord."""
        now = datetime.utcnow()
        return cls(
            warranty_id=record.warranty_id,
            asset_id=record.asset_id,
            serial_number=record.serial_number,
            product_type=record.product_type,
            manufacturer=record.manufacturer,
            purchase_date=record.purchase_date,
            warranty_start=record.warranty_start,
            warranty_end=record.warranty_end,
            coverage_type=record.coverage_type,
            current_owner=record.current_owner,
            transfer_count=len(record.transfer_history),
            claims_count=len(record.claims_history),
            blockchain_hash=record.blockchain_hash,
            is_active=record.warranty_end > now,
        )


class WarrantyTransferRequest(BaseModel):
    """Request to transfer warranty ownership."""

    from_owner: str = Field(..., description="Current owner ID")
    to_owner: str = Field(..., description="New owner ID")


@router.post(
    "/register",
    response_model=WarrantyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new warranty",
)
async def register_warranty(request: WarrantyRegisterRequest) -> WarrantyResponse:
    """
    Register a new warranty on the blockchain.

    Creates an immutable warranty record with transfer tracking.
    """
    product_info = {
        "type": request.product_type,
        "manufacturer": request.manufacturer,
    }

    owner_info = {
        "id": request.owner_id,
        "name": request.owner_name,
    }

    warranty_terms = {
        "coverage": request.coverage_type,
        "duration_days": request.duration_days,
        "product_value": request.product_value,
    }

    record = await _registry.register_warranty(
        asset_id=request.asset_id,
        serial_number=request.serial_number,
        product_info=product_info,
        owner_info=owner_info,
        warranty_terms=warranty_terms,
    )

    return WarrantyResponse.from_record(record)


@router.get(
    "/{warranty_id}",
    response_model=WarrantyResponse,
    summary="Get warranty by ID",
)
async def get_warranty(warranty_id: str) -> WarrantyResponse:
    """Get warranty record by ID."""
    record = await _registry.get_warranty(warranty_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warranty {warranty_id} not found",
        )

    return WarrantyResponse.from_record(record)


@router.post(
    "/{warranty_id}/transfer",
    response_model=WarrantyResponse,
    summary="Transfer warranty ownership",
)
async def transfer_warranty(
    warranty_id: str,
    request: WarrantyTransferRequest,
) -> WarrantyResponse:
    """
    Transfer warranty to a new owner.

    Records the transfer on the blockchain for audit trail.
    """
    try:
        record = await _registry.transfer_warranty(
            warranty_id=warranty_id,
            from_owner=request.from_owner,
            to_owner=request.to_owner,
        )
        return WarrantyResponse.from_record(record)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{warranty_id}/history",
    response_model=dict[str, Any],
    summary="Get warranty history",
)
async def get_warranty_history(warranty_id: str) -> dict[str, Any]:
    """Get complete warranty history including transfers and claims."""
    record = await _registry.get_warranty(warranty_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Warranty {warranty_id} not found",
        )

    return {
        "warranty_id": record.warranty_id,
        "transfer_history": record.transfer_history,
        "claims_history": record.claims_history,
        "total_transfers": len(record.transfer_history),
        "total_claims": len(record.claims_history),
    }


@router.get(
    "/lookup/serial/{serial_number}",
    response_model=WarrantyResponse | None,
    summary="Lookup warranty by serial number",
)
async def lookup_by_serial(serial_number: str) -> WarrantyResponse | None:
    """
    Look up warranty by product serial number.

    Returns None if no warranty found.
    """
    # Mock implementation - searches ledger in production
    return None

