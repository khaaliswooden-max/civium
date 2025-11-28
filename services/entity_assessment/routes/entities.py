"""
Entities Routes
===============

API endpoints for entity management.

Version: 0.1.0
"""

from datetime import UTC, datetime
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_current_user, User
from shared.database.postgres import get_postgres_session
from shared.logging import get_logger
from shared.models.entity import (
    Entity,
    EntityCreate,
    EntityUpdate,
    EntitySummary,
    ComplianceTier,
)
from shared.models.common import PaginatedResponse
from services.entity_assessment.services.tier import TierService

logger = get_logger(__name__)

router = APIRouter()

# Initialize tier service
tier_service = TierService()


@router.get("", response_model=PaginatedResponse[EntitySummary])
async def list_entities(
    jurisdiction: str | None = Query(default=None, description="Filter by jurisdiction"),
    tier: ComplianceTier | None = Query(default=None, description="Filter by compliance tier"),
    search: str | None = Query(default=None, description="Search by name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_postgres_session),
) -> PaginatedResponse[EntitySummary]:
    """
    List entities with optional filtering.

    Args:
        jurisdiction: Filter by jurisdiction code
        tier: Filter by compliance tier
        search: Search in entity name
        page: Page number
        page_size: Items per page
        db: Database session
    """
    # Build base query
    base_query = """
    SELECT 
        id, name, entity_type, compliance_tier, 
        compliance_score, jurisdictions
    FROM core.entities
    WHERE deleted_at IS NULL
    """

    count_query = "SELECT COUNT(*) FROM core.entities WHERE deleted_at IS NULL"
    params: dict[str, Any] = {}

    # Add filters
    filters = []
    if jurisdiction:
        filters.append(":jurisdiction = ANY(jurisdictions)")
        params["jurisdiction"] = jurisdiction.upper()

    if tier:
        filters.append("compliance_tier = :tier")
        params["tier"] = tier.value

    if search:
        filters.append("name ILIKE :search")
        params["search"] = f"%{search}%"

    if filters:
        filter_clause = " AND " + " AND ".join(filters)
        base_query += filter_clause
        count_query += filter_clause

    # Get total count
    count_result = await db.execute(text(count_query), params)
    total = count_result.scalar() or 0

    # Add pagination
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    full_query = base_query + " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"

    # Execute query
    result = await db.execute(text(full_query), params)
    rows = result.fetchall()

    items = [
        EntitySummary(
            id=str(row.id),
            name=row.name,
            entity_type=row.entity_type,
            compliance_tier=ComplianceTier(row.compliance_tier),
            compliance_score=float(row.compliance_score) if row.compliance_score else None,
            jurisdictions=row.jurisdictions or [],
        )
        for row in rows
    ]

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    logger.debug(
        "entities_listed",
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


@router.get("/{entity_id}", response_model=Entity)
async def get_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
) -> Entity:
    """
    Get an entity by ID.

    Args:
        entity_id: Entity UUID
        db: Database session
    """
    query = text("""
        SELECT * FROM core.entities
        WHERE id = :entity_id AND deleted_at IS NULL
    """)

    result = await db.execute(query, {"entity_id": entity_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    return Entity(
        id=str(row.id),
        name=row.name,
        entity_type=row.entity_type,
        sectors=row.sectors or [],
        jurisdictions=row.jurisdictions or [],
        size=row.size,
        external_id=row.external_id,
        metadata=row.metadata or {},
        compliance_tier=ComplianceTier(row.compliance_tier),
        compliance_score=float(row.compliance_score) if row.compliance_score else None,
        risk_score=float(row.risk_score) if row.risk_score else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_assessment_at=row.last_assessment_at,
    )


@router.post("", response_model=Entity, status_code=status.HTTP_201_CREATED)
async def create_entity(
    entity_data: EntityCreate,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Entity:
    """
    Create a new entity.

    Automatically assigns compliance tier based on entity attributes.

    Requires authentication.
    """
    entity_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    # Determine initial tier based on size and sectors
    initial_tier = determine_tier(entity_data)

    query = text("""
        INSERT INTO core.entities (
            id, name, entity_type, sectors, jurisdictions, 
            size, external_id, metadata, compliance_tier,
            created_at, updated_at
        ) VALUES (
            :id, :name, :entity_type, :sectors, :jurisdictions,
            :size, :external_id, :metadata, :compliance_tier,
            :created_at, :updated_at
        )
        RETURNING *
    """)

    params = {
        "id": entity_id,
        "name": entity_data.name,
        "entity_type": entity_data.entity_type.value,
        "sectors": entity_data.sectors,
        "jurisdictions": entity_data.jurisdictions,
        "size": entity_data.size,
        "external_id": entity_data.external_id,
        "metadata": entity_data.metadata,
        "compliance_tier": initial_tier.value,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.execute(query, params)
    row = result.fetchone()

    logger.info(
        "entity_created",
        entity_id=entity_id,
        name=entity_data.name,
        tier=initial_tier.value,
        user_id=current_user.id,
    )

    return Entity(
        id=str(row.id),  # type: ignore[union-attr]
        name=row.name,  # type: ignore[union-attr]
        entity_type=row.entity_type,  # type: ignore[union-attr]
        sectors=row.sectors or [],  # type: ignore[union-attr]
        jurisdictions=row.jurisdictions or [],  # type: ignore[union-attr]
        size=row.size,  # type: ignore[union-attr]
        external_id=row.external_id,  # type: ignore[union-attr]
        metadata=row.metadata or {},  # type: ignore[union-attr]
        compliance_tier=ComplianceTier(row.compliance_tier),  # type: ignore[union-attr]
        created_at=row.created_at,  # type: ignore[union-attr]
        updated_at=row.updated_at,  # type: ignore[union-attr]
    )


@router.put("/{entity_id}", response_model=Entity)
async def update_entity(
    entity_id: str,
    updates: EntityUpdate,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Entity:
    """
    Update an entity.

    Requires authentication.
    """
    # Check entity exists
    check_query = text("""
        SELECT id FROM core.entities 
        WHERE id = :entity_id AND deleted_at IS NULL
    """)
    result = await db.execute(check_query, {"entity_id": entity_id})
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    # Build update query dynamically
    update_fields = []
    params: dict[str, Any] = {"entity_id": entity_id, "updated_at": datetime.now(UTC)}

    if updates.name is not None:
        update_fields.append("name = :name")
        params["name"] = updates.name

    if updates.entity_type is not None:
        update_fields.append("entity_type = :entity_type")
        params["entity_type"] = updates.entity_type.value

    if updates.sectors is not None:
        update_fields.append("sectors = :sectors")
        params["sectors"] = updates.sectors

    if updates.jurisdictions is not None:
        update_fields.append("jurisdictions = :jurisdictions")
        params["jurisdictions"] = updates.jurisdictions

    if updates.size is not None:
        update_fields.append("size = :size")
        params["size"] = updates.size

    if updates.external_id is not None:
        update_fields.append("external_id = :external_id")
        params["external_id"] = updates.external_id

    if updates.metadata is not None:
        update_fields.append("metadata = :metadata")
        params["metadata"] = updates.metadata

    update_fields.append("updated_at = :updated_at")

    update_query = text(f"""
        UPDATE core.entities
        SET {', '.join(update_fields)}
        WHERE id = :entity_id
        RETURNING *
    """)

    result = await db.execute(update_query, params)
    row = result.fetchone()

    logger.info(
        "entity_updated",
        entity_id=entity_id,
        user_id=current_user.id,
    )

    return Entity(
        id=str(row.id),  # type: ignore[union-attr]
        name=row.name,  # type: ignore[union-attr]
        entity_type=row.entity_type,  # type: ignore[union-attr]
        sectors=row.sectors or [],  # type: ignore[union-attr]
        jurisdictions=row.jurisdictions or [],  # type: ignore[union-attr]
        size=row.size,  # type: ignore[union-attr]
        external_id=row.external_id,  # type: ignore[union-attr]
        metadata=row.metadata or {},  # type: ignore[union-attr]
        compliance_tier=ComplianceTier(row.compliance_tier),  # type: ignore[union-attr]
        compliance_score=float(row.compliance_score) if row.compliance_score else None,  # type: ignore[union-attr]
        risk_score=float(row.risk_score) if row.risk_score else None,  # type: ignore[union-attr]
        created_at=row.created_at,  # type: ignore[union-attr]
        updated_at=row.updated_at,  # type: ignore[union-attr]
        last_assessment_at=row.last_assessment_at,  # type: ignore[union-attr]
    )


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(
    entity_id: str,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Soft delete an entity.

    Requires authentication.
    """
    query = text("""
        UPDATE core.entities
        SET deleted_at = :deleted_at
        WHERE id = :entity_id AND deleted_at IS NULL
    """)

    result = await db.execute(
        query,
        {"entity_id": entity_id, "deleted_at": datetime.now(UTC)},
    )

    if result.rowcount == 0:  # type: ignore[union-attr]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity not found: {entity_id}",
        )

    logger.info(
        "entity_deleted",
        entity_id=entity_id,
        user_id=current_user.id,
    )


def determine_tier(entity_data: EntityCreate) -> ComplianceTier:
    """
    Determine initial compliance tier based on entity attributes.

    Uses the TierService for comprehensive tier assignment.
    """
    recommendation = tier_service.determine_tier(
        entity_type=entity_data.entity_type.value,
        size=entity_data.size,
        employee_count=getattr(entity_data, 'employee_count', None),
        annual_revenue=getattr(entity_data, 'annual_revenue', None),
        jurisdictions=entity_data.jurisdictions,
        sectors=entity_data.sectors,
        risk_factors=entity_data.metadata.get("risk_factors", {}) if entity_data.metadata else {},
    )

    logger.info(
        "entity_tier_determined",
        tier=recommendation.recommended_tier.value,
        confidence=recommendation.confidence,
        risk_level=recommendation.risk_level.value,
    )

    return ComplianceTier(recommendation.recommended_tier.value)

