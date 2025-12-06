"""
Requirements Routes
===================

API endpoints for managing requirements.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared.auth import User, get_current_user
from shared.database.mongodb import get_mongodb
from shared.logging import get_logger
from shared.models.common import PaginatedResponse
from shared.models.regulation import Requirement, RequirementTier


logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[Requirement])
async def list_requirements(
    regulation_id: str | None = Query(default=None, description="Filter by regulation"),
    tier: RequirementTier | None = Query(default=None, description="Filter by tier"),
    search: str | None = Query(default=None, description="Text search"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> PaginatedResponse[Requirement]:
    """
    List requirements with filtering.

    Args:
        regulation_id: Filter by parent regulation
        tier: Filter by compliance tier
        search: Full-text search in requirement text
        page: Page number
        page_size: Items per page
        db: MongoDB database
    """
    # Build query
    query: dict[str, Any] = {}
    if regulation_id:
        query["regulation_id"] = regulation_id
    if tier:
        query["tier"] = tier.value

    # Handle text search
    if search:
        query["$text"] = {"$search": search}

    # Get total count
    total = await db.requirements.count_documents(query)

    # Get requirements
    skip = (page - 1) * page_size
    cursor = db.requirements.find(query).skip(skip).limit(page_size)

    items = []
    async for doc in cursor:
        items.append(
            Requirement(
                id=doc["_id"],
                regulation_id=doc["regulation_id"],
                article_ref=doc.get("article_ref"),
                natural_language=doc["natural_language"],
                formal_logic=doc.get("formal_logic"),
                summary=doc.get("summary"),
                tier=RequirementTier(doc.get("tier", "basic")),
                verification_method=doc.get("verification_method", "self_attestation"),
                sectors=doc.get("sectors", []),
                entity_types=doc.get("entity_types", []),
                penalty=doc.get("penalty"),
                effective_date=doc.get("effective_date"),
                sunset_date=doc.get("sunset_date"),
                parsing_metadata=doc.get("parsing_metadata", {}),
                created_at=doc.get("created_at"),
                updated_at=doc.get("updated_at"),
            )
        )

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    logger.debug(
        "requirements_listed",
        total=total,
        page=page,
        regulation_id=regulation_id,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{requirement_id}", response_model=Requirement)
async def get_requirement(
    requirement_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
) -> Requirement:
    """
    Get a requirement by ID.

    Args:
        requirement_id: Requirement ID (e.g., "REQ-GDPR-6-1-a")
        db: MongoDB database
    """
    doc = await db.requirements.find_one({"_id": requirement_id})

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement not found: {requirement_id}",
        )

    return Requirement(
        id=doc["_id"],
        regulation_id=doc["regulation_id"],
        article_ref=doc.get("article_ref"),
        natural_language=doc["natural_language"],
        formal_logic=doc.get("formal_logic"),
        summary=doc.get("summary"),
        tier=RequirementTier(doc.get("tier", "basic")),
        verification_method=doc.get("verification_method", "self_attestation"),
        sectors=doc.get("sectors", []),
        entity_types=doc.get("entity_types", []),
        penalty=doc.get("penalty"),
        effective_date=doc.get("effective_date"),
        sunset_date=doc.get("sunset_date"),
        parsing_metadata=doc.get("parsing_metadata", {}),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


@router.post("", response_model=Requirement, status_code=status.HTTP_201_CREATED)
async def create_requirement(
    requirement: Requirement,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> Requirement:
    """
    Create a new requirement.

    Requires authentication.
    """
    # Check if requirement already exists
    existing = await db.requirements.find_one({"_id": requirement.id})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Requirement already exists: {requirement.id}",
        )

    # Check if regulation exists
    regulation = await db.regulations.find_one({"_id": requirement.regulation_id})
    if not regulation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Regulation not found: {requirement.regulation_id}",
        )

    # Insert requirement
    doc = requirement.model_dump(mode="json")
    doc["_id"] = doc.pop("id")

    await db.requirements.insert_one(doc)

    logger.info(
        "requirement_created",
        requirement_id=requirement.id,
        regulation_id=requirement.regulation_id,
        user_id=current_user.id,
    )

    return requirement


@router.put("/{requirement_id}", response_model=Requirement)
async def update_requirement(
    requirement_id: str,
    updates: dict[str, Any],
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> Requirement:
    """
    Update a requirement.

    Requires authentication.
    """
    from datetime import UTC, datetime

    # Check if requirement exists
    existing = await db.requirements.find_one({"_id": requirement_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement not found: {requirement_id}",
        )

    # Don't allow changing ID or regulation_id
    updates.pop("id", None)
    updates.pop("_id", None)
    updates.pop("regulation_id", None)

    # Add timestamp
    updates["updated_at"] = datetime.now(UTC)

    # Update
    await db.requirements.update_one({"_id": requirement_id}, {"$set": updates})

    # Get updated document
    updated = await db.requirements.find_one({"_id": requirement_id})

    logger.info(
        "requirement_updated",
        requirement_id=requirement_id,
        user_id=current_user.id,
    )

    return Requirement(
        id=updated["_id"],  # type: ignore[index]
        regulation_id=updated["regulation_id"],  # type: ignore[index]
        article_ref=updated.get("article_ref"),  # type: ignore[union-attr]
        natural_language=updated["natural_language"],  # type: ignore[index]
        formal_logic=updated.get("formal_logic"),  # type: ignore[union-attr]
        tier=RequirementTier(updated.get("tier", "basic")),  # type: ignore[union-attr]
        verification_method=updated.get("verification_method", "self_attestation"),  # type: ignore[union-attr]
        sectors=updated.get("sectors", []),  # type: ignore[union-attr]
        entity_types=updated.get("entity_types", []),  # type: ignore[union-attr]
        penalty=updated.get("penalty"),  # type: ignore[union-attr]
        effective_date=updated.get("effective_date"),  # type: ignore[union-attr]
        sunset_date=updated.get("sunset_date"),  # type: ignore[union-attr]
        parsing_metadata=updated.get("parsing_metadata", {}),  # type: ignore[union-attr]
        created_at=updated.get("created_at"),  # type: ignore[union-attr]
        updated_at=updated.get("updated_at"),  # type: ignore[union-attr]
    )


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_requirement(
    requirement_id: str,
    db: AsyncIOMotorDatabase = Depends(get_mongodb),  # type: ignore[type-arg]
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete a requirement.

    Requires authentication.
    """
    result = await db.requirements.delete_one({"_id": requirement_id})

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement not found: {requirement_id}",
        )

    logger.info(
        "requirement_deleted",
        requirement_id=requirement_id,
        user_id=current_user.id,
    )
