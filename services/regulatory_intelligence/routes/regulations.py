"""
Regulations Routes
==================

API endpoints for managing regulations.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth import get_current_user, User
from shared.database.mongodb import get_mongodb
from shared.logging import get_logger
from shared.models.regulation import Regulation, RegulationSummary
from shared.models.common import PaginatedResponse

logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[RegulationSummary])
async def list_regulations(
    jurisdiction: str | None = Query(default=None, description="Filter by jurisdiction"),
    sector: str | None = Query(default=None, description="Filter by sector"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> PaginatedResponse[RegulationSummary]:
    """
    List all regulations with optional filtering.

    Args:
        jurisdiction: Filter by jurisdiction code (e.g., "EU", "US")
        sector: Filter by sector (e.g., "FINANCE", "HEALTH")
        page: Page number
        page_size: Items per page
        db: MongoDB database
    """
    # Build query
    query: dict[str, Any] = {}
    if jurisdiction:
        query["$or"] = [
            {"jurisdiction": jurisdiction.upper()},
            {"jurisdictions": jurisdiction.upper()},
        ]
    if sector:
        query["sectors"] = sector.upper()

    # Get total count
    total = await db.regulations.count_documents(query)

    # Get regulations
    skip = (page - 1) * page_size
    cursor = (
        db.regulations.find(query)
        .sort("effective_date", -1)
        .skip(skip)
        .limit(page_size)
    )

    items = []
    async for doc in cursor:
        # Count requirements for this regulation
        req_count = await db.requirements.count_documents(
            {"regulation_id": doc["_id"]}
        )

        items.append(
            RegulationSummary(
                id=doc["_id"],
                name=doc["name"],
                short_name=doc.get("short_name"),
                jurisdiction=doc["jurisdiction"],
                effective_date=doc["effective_date"],
                requirements_count=req_count,
            )
        )

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    logger.debug(
        "regulations_listed",
        total=total,
        page=page,
        jurisdiction=jurisdiction,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{regulation_id}", response_model=Regulation)
async def get_regulation(
    regulation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> Regulation:
    """
    Get a regulation by ID.

    Args:
        regulation_id: Regulation ID (e.g., "REG-GDPR")
        db: MongoDB database
    """
    doc = await db.regulations.find_one({"_id": regulation_id})

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulation not found: {regulation_id}",
        )

    logger.debug("regulation_retrieved", regulation_id=regulation_id)

    return Regulation(
        id=doc["_id"],
        name=doc["name"],
        short_name=doc.get("short_name"),
        jurisdiction=doc["jurisdiction"],
        jurisdictions=doc.get("jurisdictions", []),
        sectors=doc.get("sectors", []),
        governance_layer=doc.get("governance_layer", 5),
        source_url=doc.get("source_url"),
        source_hash=doc.get("source_hash"),
        effective_date=doc["effective_date"],
        sunset_date=doc.get("sunset_date"),
        rml=doc.get("rml", {}),
        parsing_metadata=doc.get("parsing_metadata", {}),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.post("", response_model=Regulation, status_code=status.HTTP_201_CREATED)
async def create_regulation(
    regulation: Regulation,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> Regulation:
    """
    Create a new regulation.

    Requires authentication.
    """
    # Check if regulation already exists
    existing = await db.regulations.find_one({"_id": regulation.id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Regulation already exists: {regulation.id}",
        )

    # Insert regulation
    doc = regulation.model_dump()
    doc["_id"] = doc.pop("id")

    await db.regulations.insert_one(doc)

    logger.info(
        "regulation_created",
        regulation_id=regulation.id,
        user_id=current_user.id,
    )

    return regulation


@router.delete("/{regulation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_regulation(
    regulation_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete a regulation and its requirements.

    Requires authentication.
    """
    # Check if regulation exists
    existing = await db.regulations.find_one({"_id": regulation_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regulation not found: {regulation_id}",
        )

    # Delete requirements first
    req_result = await db.requirements.delete_many({"regulation_id": regulation_id})

    # Delete regulation
    await db.regulations.delete_one({"_id": regulation_id})

    logger.info(
        "regulation_deleted",
        regulation_id=regulation_id,
        requirements_deleted=req_result.deleted_count,
        user_id=current_user.id,
    )


@router.get("/{regulation_id}/changes")
async def get_regulation_changes(
    regulation_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> list[dict[str, Any]]:
    """
    Get change history for a regulation.

    Args:
        regulation_id: Regulation ID
        limit: Maximum changes to return
        db: MongoDB database
    """
    cursor = (
        db.regulatory_changes.find({"regulation_id": regulation_id})
        .sort("detected_at", -1)
        .limit(limit)
    )

    changes = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        changes.append(doc)

    return changes

