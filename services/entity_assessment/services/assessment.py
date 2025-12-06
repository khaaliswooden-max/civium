"""
Assessment Workflow Service
===========================

Manages the lifecycle of compliance assessments.

Workflows:
1. Create assessment -> Draft
2. Populate items from requirements
3. Assess items -> In Progress
4. Submit for review -> Pending Review
5. Approve/Reject -> Completed/Rejected
6. Calculate scores

Version: 0.1.0
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.entity_assessment.models.assessment import (
    AssessmentStatus,
    AssessmentType,
    ItemStatus,
)
from services.entity_assessment.services.score import ScoreService
from shared.logging import get_logger


logger = get_logger(__name__)


class WorkflowAction(str, Enum):
    """Assessment workflow actions."""

    START = "start"
    SUBMIT = "submit"
    REVIEW = "review"
    APPROVE = "approve"
    REJECT = "reject"
    REOPEN = "reopen"
    ARCHIVE = "archive"


@dataclass
class AssessmentWorkflow:
    """Assessment workflow state machine."""

    # Valid transitions
    transitions: dict[AssessmentStatus, dict[WorkflowAction, AssessmentStatus]] = field(
        default_factory=lambda: {
            AssessmentStatus.DRAFT: {
                WorkflowAction.START: AssessmentStatus.IN_PROGRESS,
            },
            AssessmentStatus.IN_PROGRESS: {
                WorkflowAction.SUBMIT: AssessmentStatus.PENDING_REVIEW,
            },
            AssessmentStatus.PENDING_REVIEW: {
                WorkflowAction.APPROVE: AssessmentStatus.COMPLETED,
                WorkflowAction.REJECT: AssessmentStatus.REJECTED,
            },
            AssessmentStatus.REJECTED: {
                WorkflowAction.REOPEN: AssessmentStatus.IN_PROGRESS,
            },
            AssessmentStatus.COMPLETED: {
                WorkflowAction.ARCHIVE: AssessmentStatus.ARCHIVED,
            },
        }
    )

    def can_transition(
        self,
        current: AssessmentStatus,
        action: WorkflowAction,
    ) -> bool:
        """Check if transition is valid."""
        if current not in self.transitions:
            return False
        return action in self.transitions[current]

    def get_next_status(
        self,
        current: AssessmentStatus,
        action: WorkflowAction,
    ) -> AssessmentStatus | None:
        """Get the next status after an action."""
        if not self.can_transition(current, action):
            return None
        return self.transitions[current][action]


@dataclass
class AssessmentContext:
    """Context for assessment operations."""

    assessment_id: str
    entity_id: str
    assessment_type: AssessmentType
    status: AssessmentStatus
    jurisdictions: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    regulation_ids: list[str] = field(default_factory=list)


class AssessmentService:
    """
    Service for managing compliance assessments.

    Handles:
    - Assessment creation and lifecycle
    - Item population from requirements
    - Workflow transitions
    - Score calculation on completion
    """

    def __init__(self) -> None:
        """Initialize the assessment service."""
        self.workflow = AssessmentWorkflow()
        self.score_service = ScoreService()

    async def create_assessment(
        self,
        db: AsyncSession,
        entity_id: str,
        assessment_type: AssessmentType = AssessmentType.PERIODIC,
        jurisdictions: list[str] | None = None,
        sectors: list[str] | None = None,
        regulation_ids: list[str] | None = None,
        due_date: datetime | None = None,
        assessor_id: str | None = None,
        assessor_name: str | None = None,
    ) -> AssessmentContext:
        """
        Create a new assessment.

        Args:
            db: Database session
            entity_id: Entity to assess
            assessment_type: Type of assessment
            jurisdictions: Scope to specific jurisdictions
            sectors: Scope to specific sectors
            regulation_ids: Scope to specific regulations
            due_date: Assessment due date
            assessor_id: User performing assessment
            assessor_name: Name of assessor

        Returns:
            AssessmentContext for the new assessment
        """
        assessment_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Default due date is 30 days from now
        if due_date is None:
            due_date = now + timedelta(days=30)

        query = text("""
            INSERT INTO core.assessments (
                id, entity_id, assessment_type, status,
                jurisdictions, sectors, regulation_ids,
                assessment_date, due_date,
                assessor_id, assessor_name,
                created_at, updated_at
            ) VALUES (
                :id, :entity_id, :assessment_type, :status,
                :jurisdictions, :sectors, :regulation_ids,
                :assessment_date, :due_date,
                :assessor_id, :assessor_name,
                :created_at, :updated_at
            )
        """)

        await db.execute(
            query,
            {
                "id": assessment_id,
                "entity_id": entity_id,
                "assessment_type": assessment_type.value,
                "status": AssessmentStatus.DRAFT.value,
                "jurisdictions": jurisdictions or [],
                "sectors": sectors or [],
                "regulation_ids": regulation_ids or [],
                "assessment_date": now,
                "due_date": due_date,
                "assessor_id": assessor_id,
                "assessor_name": assessor_name,
                "created_at": now,
                "updated_at": now,
            },
        )

        logger.info(
            "assessment_created",
            assessment_id=assessment_id,
            entity_id=entity_id,
            type=assessment_type.value,
        )

        return AssessmentContext(
            assessment_id=assessment_id,
            entity_id=entity_id,
            assessment_type=assessment_type,
            status=AssessmentStatus.DRAFT,
            jurisdictions=jurisdictions or [],
            sectors=sectors or [],
            regulation_ids=regulation_ids or [],
        )

    async def populate_assessment_items(
        self,
        db: AsyncSession,
        assessment_id: str,
        entity_id: str,
        jurisdictions: list[str] | None = None,
        sectors: list[str] | None = None,
        regulation_ids: list[str] | None = None,
    ) -> int:
        """
        Populate assessment with items from applicable requirements.

        Queries the compliance graph to find requirements that apply
        to the entity based on its jurisdictions and sectors.

        Args:
            db: Database session
            assessment_id: Assessment to populate
            entity_id: Entity being assessed
            jurisdictions: Filter to specific jurisdictions
            sectors: Filter to specific sectors
            regulation_ids: Filter to specific regulations

        Returns:
            Number of items created
        """
        # For now, we'll query requirements from a cached table
        # In production, this would query Neo4j compliance graph
        requirements = await self._get_applicable_requirements(
            db,
            entity_id=entity_id,
            jurisdictions=jurisdictions,
            sectors=sectors,
            regulation_ids=regulation_ids,
        )

        items_created = 0
        now = datetime.now(UTC)

        for req in requirements:
            item_id = str(uuid.uuid4())

            query = text("""
                INSERT INTO core.assessment_items (
                    id, assessment_id, requirement_id, regulation_id,
                    requirement_text, requirement_tier, article_ref,
                    status, created_at, updated_at
                ) VALUES (
                    :id, :assessment_id, :requirement_id, :regulation_id,
                    :requirement_text, :requirement_tier, :article_ref,
                    :status, :created_at, :updated_at
                )
            """)

            await db.execute(
                query,
                {
                    "id": item_id,
                    "assessment_id": assessment_id,
                    "requirement_id": req.get("requirement_id"),
                    "regulation_id": req.get("regulation_id"),
                    "requirement_text": req.get("text"),
                    "requirement_tier": req.get("tier", "basic"),
                    "article_ref": req.get("article_ref"),
                    "status": ItemStatus.PENDING.value,
                    "created_at": now,
                    "updated_at": now,
                },
            )

            items_created += 1

        # Update assessment counts
        await self._update_assessment_counts(db, assessment_id)

        logger.info(
            "assessment_items_populated",
            assessment_id=assessment_id,
            items_count=items_created,
        )

        return items_created

    async def _get_applicable_requirements(
        self,
        db: AsyncSession,
        entity_id: str,
        jurisdictions: list[str] | None = None,
        sectors: list[str] | None = None,
        regulation_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get requirements applicable to an entity.

        This is a simplified version - production would query Neo4j.
        """
        # Query cached requirements table or call Neo4j
        # For now, return mock data structure
        query = text("""
            SELECT 
                r.id as requirement_id,
                r.regulation_id,
                r.text,
                r.tier,
                r.article_ref,
                r.jurisdictions,
                r.sectors
            FROM core.requirements r
            WHERE r.is_active = true
              AND (
                :any_jurisdiction = true 
                OR r.jurisdictions && :jurisdictions
              )
              AND (
                :any_sector = true
                OR r.sectors && :sectors
              )
              AND (
                :any_regulation = true
                OR r.regulation_id = ANY(:regulation_ids)
              )
        """)

        result = await db.execute(
            query,
            {
                "any_jurisdiction": not jurisdictions,
                "jurisdictions": jurisdictions or [],
                "any_sector": not sectors,
                "sectors": sectors or [],
                "any_regulation": not regulation_ids,
                "regulation_ids": regulation_ids or [],
            },
        )

        return [
            {
                "requirement_id": str(row.requirement_id),
                "regulation_id": row.regulation_id,
                "text": row.text,
                "tier": row.tier,
                "article_ref": row.article_ref,
            }
            for row in result.fetchall()
        ]

    async def update_item(
        self,
        db: AsyncSession,
        item_id: str,
        status: ItemStatus,
        score: float | None = None,
        finding: str | None = None,
        evidence_ids: list[str] | None = None,
        assessed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        """
        Update an assessment item.

        Args:
            db: Database session
            item_id: Item to update
            status: New compliance status
            score: Partial compliance score (0-1)
            finding: Assessment finding
            evidence_ids: Supporting evidence
            assessed_by: User making assessment
            notes: Additional notes
        """
        now = datetime.now(UTC)

        query = text("""
            UPDATE core.assessment_items
            SET status = :status,
                score = :score,
                finding = :finding,
                evidence_ids = :evidence_ids,
                assessed_by = :assessed_by,
                assessed_at = :assessed_at,
                notes = :notes,
                updated_at = :updated_at
            WHERE id = :item_id
        """)

        await db.execute(
            query,
            {
                "item_id": item_id,
                "status": status.value,
                "score": score,
                "finding": finding,
                "evidence_ids": evidence_ids or [],
                "assessed_by": assessed_by,
                "assessed_at": now,
                "notes": notes,
                "updated_at": now,
            },
        )

        # Get assessment ID and update counts
        result = await db.execute(
            text("SELECT assessment_id FROM core.assessment_items WHERE id = :id"),
            {"id": item_id},
        )
        row = result.fetchone()
        if row:
            await self._update_assessment_counts(db, str(row.assessment_id))

        logger.info(
            "assessment_item_updated",
            item_id=item_id,
            status=status.value,
        )

    async def transition_assessment(
        self,
        db: AsyncSession,
        assessment_id: str,
        action: WorkflowAction,
        user_id: str | None = None,
        user_name: str | None = None,
        notes: str | None = None,
    ) -> AssessmentStatus:
        """
        Transition assessment to next state.

        Args:
            db: Database session
            assessment_id: Assessment to transition
            action: Workflow action to perform
            user_id: User performing action
            user_name: Name of user
            notes: Action notes

        Returns:
            New assessment status

        Raises:
            ValueError: If transition is invalid
        """
        # Get current status
        result = await db.execute(
            text("SELECT status FROM core.assessments WHERE id = :id"),
            {"id": assessment_id},
        )
        row = result.fetchone()

        if not row:
            raise ValueError(f"Assessment not found: {assessment_id}")

        current_status = AssessmentStatus(row.status)

        # Validate transition
        if not self.workflow.can_transition(current_status, action):
            raise ValueError(f"Invalid transition: {current_status.value} -> {action.value}")

        new_status = self.workflow.get_next_status(current_status, action)
        if not new_status:
            raise ValueError("Could not determine next status")

        now = datetime.now(UTC)

        # Build update based on action
        update_fields = {
            "assessment_id": assessment_id,
            "status": new_status.value,
            "updated_at": now,
        }

        query_parts = ["status = :status", "updated_at = :updated_at"]

        if action == WorkflowAction.START:
            query_parts.append("started_at = :started_at")
            update_fields["started_at"] = now

        elif action == WorkflowAction.APPROVE:
            query_parts.extend(
                [
                    "completed_at = :completed_at",
                    "approver_id = :approver_id",
                    "approver_name = :approver_name",
                ]
            )
            update_fields["completed_at"] = now
            update_fields["approver_id"] = user_id
            update_fields["approver_name"] = user_name

        elif action == WorkflowAction.REJECT:
            query_parts.extend(
                [
                    "reviewer_id = :reviewer_id",
                    "reviewer_name = :reviewer_name",
                ]
            )
            update_fields["reviewer_id"] = user_id
            update_fields["reviewer_name"] = user_name

        query = text(f"""
            UPDATE core.assessments
            SET {", ".join(query_parts)}
            WHERE id = :assessment_id
        """)

        await db.execute(query, update_fields)

        # On completion, calculate and record scores
        if new_status == AssessmentStatus.COMPLETED:
            await self._finalize_assessment(db, assessment_id)

        logger.info(
            "assessment_transitioned",
            assessment_id=assessment_id,
            from_status=current_status.value,
            to_status=new_status.value,
            action=action.value,
        )

        return new_status

    async def _finalize_assessment(
        self,
        db: AsyncSession,
        assessment_id: str,
    ) -> None:
        """Finalize assessment: calculate scores and update entity."""
        # Get assessment details
        result = await db.execute(
            text("SELECT entity_id FROM core.assessments WHERE id = :id"),
            {"id": assessment_id},
        )
        row = result.fetchone()

        if not row:
            return

        entity_id = str(row.entity_id)

        # Get assessment items
        items_result = await db.execute(
            text("""
                SELECT requirement_id, status, requirement_tier, 
                       regulation_id, risk_impact, score
                FROM core.assessment_items
                WHERE assessment_id = :assessment_id
            """),
            {"assessment_id": assessment_id},
        )

        items = [
            {
                "requirement_id": r.requirement_id,
                "status": r.status,
                "requirement_tier": r.requirement_tier,
                "regulation_id": r.regulation_id,
                "risk_impact": r.risk_impact,
                "score": float(r.score) if r.score else None,
            }
            for r in items_result.fetchall()
        ]

        # Calculate scores
        score_result = await self.score_service.calculate_entity_score(
            db,
            entity_id=entity_id,
            assessment_items=items,
        )

        # Record scores
        await self.score_service.record_score(
            db,
            entity_id=entity_id,
            score_result=score_result,
            assessment_id=assessment_id,
        )

        # Update assessment with scores
        await db.execute(
            text("""
                UPDATE core.assessments
                SET overall_score = :score
                WHERE id = :id
            """),
            {"id": assessment_id, "score": score_result.overall_score},
        )

        # Update entity's last assessment
        await db.execute(
            text("""
                UPDATE core.entities
                SET last_assessment_id = :assessment_id,
                    last_assessment_at = :now
                WHERE id = :entity_id
            """),
            {
                "assessment_id": assessment_id,
                "now": datetime.now(UTC),
                "entity_id": entity_id,
            },
        )

        logger.info(
            "assessment_finalized",
            assessment_id=assessment_id,
            entity_id=entity_id,
            score=score_result.overall_score,
        )

    async def _update_assessment_counts(
        self,
        db: AsyncSession,
        assessment_id: str,
    ) -> None:
        """Update assessment item counts."""
        query = text("""
            UPDATE core.assessments
            SET total_items = counts.total,
                compliant_items = counts.compliant,
                non_compliant_items = counts.non_compliant,
                partial_items = counts.partial,
                not_applicable_items = counts.not_applicable,
                pending_items = counts.pending
            FROM (
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'compliant') as compliant,
                    COUNT(*) FILTER (WHERE status = 'non_compliant') as non_compliant,
                    COUNT(*) FILTER (WHERE status = 'partial') as partial,
                    COUNT(*) FILTER (WHERE status = 'not_applicable') as not_applicable,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending
                FROM core.assessment_items
                WHERE assessment_id = :assessment_id
            ) counts
            WHERE id = :assessment_id
        """)

        await db.execute(query, {"assessment_id": assessment_id})

    async def get_assessment_summary(
        self,
        db: AsyncSession,
        assessment_id: str,
    ) -> dict[str, Any]:
        """
        Get summary of an assessment.

        Args:
            db: Database session
            assessment_id: Assessment to summarize

        Returns:
            Assessment summary with counts and scores
        """
        query = text("""
            SELECT a.*, e.name as entity_name
            FROM core.assessments a
            JOIN core.entities e ON a.entity_id = e.id
            WHERE a.id = :id
        """)

        result = await db.execute(query, {"id": assessment_id})
        row = result.fetchone()

        if not row:
            return {}

        return {
            "assessment_id": str(row.id),
            "entity_id": str(row.entity_id),
            "entity_name": row.entity_name,
            "type": row.assessment_type,
            "status": row.status,
            "overall_score": float(row.overall_score) if row.overall_score else None,
            "total_items": row.total_items,
            "compliant_items": row.compliant_items,
            "non_compliant_items": row.non_compliant_items,
            "pending_items": row.pending_items,
            "completion_rate": (
                (row.total_items - row.pending_items) / row.total_items
                if row.total_items > 0
                else 0
            ),
            "assessment_date": row.assessment_date.isoformat() if row.assessment_date else None,
            "due_date": row.due_date.isoformat() if row.due_date else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
