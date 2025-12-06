"""
Assessments Routes
==================

API endpoints for compliance assessments.

Version: 0.1.0
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import User, get_current_user
from shared.database.postgres import get_postgres_session
from shared.logging import get_logger
from shared.models.assessment import (
    Assessment,
    AssessmentCreate,
    AssessmentStatus,
    AssessmentSummary,
    AssessmentUpdate,
)
from shared.models.common import PaginatedResponse


logger = get_logger(__name__)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AssessmentSummary])
async def list_assessments(
    entity_id: str | None = Query(default=None, description="Filter by entity"),
    status: AssessmentStatus | None = Query(default=None, description="Filter by status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_postgres_session),
) -> PaginatedResponse[AssessmentSummary]:
    """
    List assessments with optional filtering.
    """
    base_query = """
        SELECT id, entity_id, assessment_type, status, 
               overall_score, started_at, completed_at
        FROM core.assessments
        WHERE 1=1
    """
    count_query = "SELECT COUNT(*) FROM core.assessments WHERE 1=1"
    params: dict[str, Any] = {}

    if entity_id:
        base_query += " AND entity_id = :entity_id"
        count_query += " AND entity_id = :entity_id"
        params["entity_id"] = entity_id

    if status:
        base_query += " AND status = :status"
        count_query += " AND status = :status"
        params["status"] = status.value

    # Get count
    count_result = await db.execute(text(count_query), params)
    total = count_result.scalar() or 0

    # Add pagination
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    full_query = base_query + " ORDER BY started_at DESC LIMIT :limit OFFSET :offset"

    result = await db.execute(text(full_query), params)
    rows = result.fetchall()

    items = [
        AssessmentSummary(
            id=str(row.id),
            entity_id=str(row.entity_id),
            assessment_type=row.assessment_type,
            status=AssessmentStatus(row.status),
            overall_score=float(row.overall_score) if row.overall_score else None,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
        for row in rows
    ]

    pages = (total + page_size - 1) // page_size if total > 0 else 1

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{assessment_id}", response_model=Assessment)
async def get_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_postgres_session),
) -> Assessment:
    """
    Get an assessment by ID.
    """
    query = text("SELECT * FROM core.assessments WHERE id = :assessment_id")
    result = await db.execute(query, {"assessment_id": assessment_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment not found: {assessment_id}",
        )

    return Assessment(
        id=str(row.id),
        entity_id=str(row.entity_id),
        assessment_type=row.assessment_type,
        status=AssessmentStatus(row.status),
        overall_score=float(row.overall_score) if row.overall_score else None,
        criterion_scores=row.criterion_scores or [],
        evidence_refs=row.evidence_refs or [],
        assessor_id=str(row.assessor_id) if row.assessor_id else None,
        reviewer_id=str(row.reviewer_id) if row.reviewer_id else None,
        started_at=row.started_at,
        submitted_at=row.submitted_at,
        reviewed_at=row.reviewed_at,
        completed_at=row.completed_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        notes=None,
    )


@router.post("", response_model=Assessment, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    assessment_data: AssessmentCreate,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Assessment:
    """
    Create a new assessment.

    Requires authentication.
    """
    # Verify entity exists
    entity_check = text("""
        SELECT id FROM core.entities 
        WHERE id = :entity_id AND deleted_at IS NULL
    """)
    result = await db.execute(entity_check, {"entity_id": assessment_data.entity_id})
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Entity not found: {assessment_data.entity_id}",
        )

    assessment_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    query = text("""
        INSERT INTO core.assessments (
            id, entity_id, assessment_type, status,
            assessor_id, started_at, created_at, updated_at
        ) VALUES (
            :id, :entity_id, :assessment_type, :status,
            :assessor_id, :started_at, :created_at, :updated_at
        )
        RETURNING *
    """)

    params = {
        "id": assessment_id,
        "entity_id": assessment_data.entity_id,
        "assessment_type": assessment_data.assessment_type,
        "status": AssessmentStatus.DRAFT.value,
        "assessor_id": assessment_data.assessor_id or current_user.id,
        "started_at": now,
        "created_at": now,
        "updated_at": now,
    }

    result = await db.execute(query, params)
    row = result.fetchone()

    logger.info(
        "assessment_created",
        assessment_id=assessment_id,
        entity_id=assessment_data.entity_id,
        user_id=current_user.id,
    )

    return Assessment(
        id=str(row.id),  # type: ignore[union-attr]
        entity_id=str(row.entity_id),  # type: ignore[union-attr]
        assessment_type=row.assessment_type,  # type: ignore[union-attr]
        status=AssessmentStatus(row.status),  # type: ignore[union-attr]
        assessor_id=str(row.assessor_id) if row.assessor_id else None,  # type: ignore[union-attr]
        started_at=row.started_at,  # type: ignore[union-attr]
        created_at=row.created_at,  # type: ignore[union-attr]
        updated_at=row.updated_at,  # type: ignore[union-attr]
        notes=assessment_data.notes,
    )


@router.put("/{assessment_id}", response_model=Assessment)
async def update_assessment(
    assessment_id: str,
    updates: AssessmentUpdate,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Assessment:
    """
    Update an assessment.

    Requires authentication.
    """
    # Check assessment exists
    check_query = text("SELECT * FROM core.assessments WHERE id = :assessment_id")
    result = await db.execute(check_query, {"assessment_id": assessment_id})
    existing = result.fetchone()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment not found: {assessment_id}",
        )

    # Build update
    update_fields = ["updated_at = :updated_at"]
    params: dict[str, Any] = {"assessment_id": assessment_id, "updated_at": datetime.now(UTC)}

    if updates.status is not None:
        update_fields.append("status = :status")
        params["status"] = updates.status.value

        # Set timestamps based on status
        if updates.status == AssessmentStatus.PENDING_REVIEW:
            update_fields.append("submitted_at = :submitted_at")
            params["submitted_at"] = datetime.now(UTC)
        elif updates.status in (AssessmentStatus.APPROVED, AssessmentStatus.REJECTED):
            update_fields.append("reviewed_at = :reviewed_at")
            update_fields.append("completed_at = :completed_at")
            params["reviewed_at"] = datetime.now(UTC)
            params["completed_at"] = datetime.now(UTC)

    if updates.overall_score is not None:
        update_fields.append("overall_score = :overall_score")
        params["overall_score"] = updates.overall_score

    if updates.criterion_scores is not None:
        update_fields.append("criterion_scores = :criterion_scores")
        params["criterion_scores"] = [cs.model_dump() for cs in updates.criterion_scores]

    if updates.reviewer_id is not None:
        update_fields.append("reviewer_id = :reviewer_id")
        params["reviewer_id"] = updates.reviewer_id

    update_query = text(f"""
        UPDATE core.assessments
        SET {", ".join(update_fields)}
        WHERE id = :assessment_id
        RETURNING *
    """)

    result = await db.execute(update_query, params)
    row = result.fetchone()

    # Update entity's last_assessment_at if completed
    if updates.status in (AssessmentStatus.APPROVED, AssessmentStatus.REJECTED):
        await db.execute(
            text("""
                UPDATE core.entities
                SET last_assessment_at = :now
                WHERE id = :entity_id
            """),
            {"entity_id": str(existing.entity_id), "now": datetime.now(UTC)},
        )

    logger.info(
        "assessment_updated",
        assessment_id=assessment_id,
        status=updates.status.value if updates.status else None,
        user_id=current_user.id,
    )

    return Assessment(
        id=str(row.id),  # type: ignore[union-attr]
        entity_id=str(row.entity_id),  # type: ignore[union-attr]
        assessment_type=row.assessment_type,  # type: ignore[union-attr]
        status=AssessmentStatus(row.status),  # type: ignore[union-attr]
        overall_score=float(row.overall_score) if row.overall_score else None,  # type: ignore[union-attr]
        criterion_scores=row.criterion_scores or [],  # type: ignore[union-attr]
        evidence_refs=row.evidence_refs or [],  # type: ignore[union-attr]
        assessor_id=str(row.assessor_id) if row.assessor_id else None,  # type: ignore[union-attr]
        reviewer_id=str(row.reviewer_id) if row.reviewer_id else None,  # type: ignore[union-attr]
        started_at=row.started_at,  # type: ignore[union-attr]
        submitted_at=row.submitted_at,  # type: ignore[union-attr]
        reviewed_at=row.reviewed_at,  # type: ignore[union-attr]
        completed_at=row.completed_at,  # type: ignore[union-attr]
        expires_at=row.expires_at,  # type: ignore[union-attr]
        created_at=row.created_at,  # type: ignore[union-attr]
        updated_at=row.updated_at,  # type: ignore[union-attr]
        notes=updates.notes,
    )


@router.post("/{assessment_id}/submit", response_model=Assessment)
async def submit_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Assessment:
    """
    Submit an assessment for review.

    Changes status from DRAFT/IN_PROGRESS to PENDING_REVIEW.
    """
    update = AssessmentUpdate(status=AssessmentStatus.PENDING_REVIEW)
    return await update_assessment(assessment_id, update, db, current_user)


@router.post("/{assessment_id}/approve", response_model=Assessment)
async def approve_assessment(
    assessment_id: str,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Assessment:
    """
    Approve an assessment.

    Changes status to APPROVED and updates entity's compliance score.
    """
    update = AssessmentUpdate(
        status=AssessmentStatus.APPROVED,
        reviewer_id=current_user.id,
    )
    return await update_assessment(assessment_id, update, db, current_user)


@router.post("/{assessment_id}/reject", response_model=Assessment)
async def reject_assessment(
    assessment_id: str,
    reason: str | None = None,
    db: AsyncSession = Depends(get_postgres_session),
    current_user: User = Depends(get_current_user),
) -> Assessment:
    """
    Reject an assessment.

    Changes status to REJECTED.
    """
    update = AssessmentUpdate(
        status=AssessmentStatus.REJECTED,
        reviewer_id=current_user.id,
        notes=reason,
    )
    return await update_assessment(assessment_id, update, db, current_user)
