"""
Conflict Detection Routes
=========================

API endpoints for detecting regulatory conflicts.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.auth import get_current_user, User
from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class RegulatoryConflict(BaseModel):
    """A detected conflict between requirements."""

    requirement_1_id: str
    requirement_1_text: str
    requirement_2_id: str
    requirement_2_text: str
    conflict_type: str = Field(description="Type: direct, indirect, temporal")
    severity: str = Field(default="medium", description="low, medium, high")
    description: str | None = None


class ConflictAnalysis(BaseModel):
    """Conflict analysis result for an entity."""

    entity_id: str
    total_conflicts: int
    high_severity: int = 0
    medium_severity: int = 0
    low_severity: int = 0
    conflicts: list[RegulatoryConflict]


@router.get("/entity/{entity_id}", response_model=ConflictAnalysis)
async def detect_entity_conflicts(
    entity_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> ConflictAnalysis:
    """
    Detect regulatory conflicts for an entity.

    Finds requirements that apply to the entity and have
    CONFLICTS_WITH relationships.

    Args:
        entity_id: Entity to analyze
        limit: Maximum conflicts to return
    """
    query = """
    MATCH (e:Entity {id: $entity_id})<-[:APPLIES_TO]-(r1:Requirement)
    MATCH (e)<-[:APPLIES_TO]-(r2:Requirement)
    WHERE (r1)-[:CONFLICTS_WITH]-(r2)
    AND id(r1) < id(r2)
    RETURN r1, r2
    LIMIT $limit
    """

    try:
        results = await Neo4jClient.run_query(
            query,
            {"entity_id": entity_id, "limit": limit},
        )

        conflicts = []
        high_count = 0
        medium_count = 0
        low_count = 0

        for record in results:
            r1 = record.get("r1", {})
            r2 = record.get("r2", {})

            # Determine severity based on tiers
            tier1 = r1.get("tier", "basic")
            tier2 = r2.get("tier", "basic")

            if tier1 == "advanced" or tier2 == "advanced":
                severity = "high"
                high_count += 1
            elif tier1 == "standard" or tier2 == "standard":
                severity = "medium"
                medium_count += 1
            else:
                severity = "low"
                low_count += 1

            conflicts.append(
                RegulatoryConflict(
                    requirement_1_id=r1.get("id", ""),
                    requirement_1_text=r1.get("natural_language", "")[:200],
                    requirement_2_id=r2.get("id", ""),
                    requirement_2_text=r2.get("natural_language", "")[:200],
                    conflict_type="direct",
                    severity=severity,
                )
            )

        logger.debug(
            "conflicts_detected",
            entity_id=entity_id,
            conflict_count=len(conflicts),
        )

        return ConflictAnalysis(
            entity_id=entity_id,
            total_conflicts=len(conflicts),
            high_severity=high_count,
            medium_severity=medium_count,
            low_severity=low_count,
            conflicts=conflicts,
        )

    except Exception as e:
        logger.error(
            "conflict_detection_failed",
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}",
        )


@router.get("/requirements/{requirement_id}", response_model=list[RegulatoryConflict])
async def get_requirement_conflicts(
    requirement_id: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[RegulatoryConflict]:
    """
    Get all conflicts for a specific requirement.

    Args:
        requirement_id: Requirement ID
        limit: Maximum conflicts to return
    """
    query = """
    MATCH (r1:Requirement {id: $requirement_id})-[:CONFLICTS_WITH]-(r2:Requirement)
    RETURN r1, r2
    LIMIT $limit
    """

    try:
        results = await Neo4jClient.run_query(
            query,
            {"requirement_id": requirement_id, "limit": limit},
        )

        conflicts = []
        for record in results:
            r1 = record.get("r1", {})
            r2 = record.get("r2", {})

            conflicts.append(
                RegulatoryConflict(
                    requirement_1_id=r1.get("id", ""),
                    requirement_1_text=r1.get("natural_language", "")[:200],
                    requirement_2_id=r2.get("id", ""),
                    requirement_2_text=r2.get("natural_language", "")[:200],
                    conflict_type="direct",
                    severity="medium",
                )
            )

        return conflicts

    except Exception as e:
        logger.error(
            "get_requirement_conflicts_failed",
            requirement_id=requirement_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}",
        )


@router.post("/mark", status_code=status.HTTP_201_CREATED)
async def mark_conflict(
    requirement_1_id: str,
    requirement_2_id: str,
    conflict_type: str = "direct",
    description: str | None = None,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Mark a conflict relationship between two requirements.

    Requires authentication.

    Args:
        requirement_1_id: First requirement
        requirement_2_id: Second requirement
        conflict_type: Type of conflict (direct, indirect, temporal)
        description: Optional description
    """
    query = """
    MATCH (r1:Requirement {id: $req1_id})
    MATCH (r2:Requirement {id: $req2_id})
    MERGE (r1)-[c:CONFLICTS_WITH]-(r2)
    SET c.conflict_type = $conflict_type,
        c.description = $description,
        c.marked_by = $marked_by,
        c.marked_at = datetime()
    RETURN c
    """

    params = {
        "req1_id": requirement_1_id,
        "req2_id": requirement_2_id,
        "conflict_type": conflict_type,
        "description": description,
        "marked_by": current_user.id,
    }

    try:
        counters = await Neo4jClient.run_write_query(query, params)

        logger.info(
            "conflict_marked",
            requirement_1=requirement_1_id,
            requirement_2=requirement_2_id,
            user_id=current_user.id,
        )

        return {
            "success": True,
            "requirement_1_id": requirement_1_id,
            "requirement_2_id": requirement_2_id,
            "conflict_type": conflict_type,
            "counters": counters,
        }

    except Exception as e:
        logger.error(
            "mark_conflict_failed",
            requirement_1=requirement_1_id,
            requirement_2=requirement_2_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark conflict: {str(e)}",
        )


@router.delete("/remove", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conflict(
    requirement_1_id: str,
    requirement_2_id: str,
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Remove a conflict relationship.

    Requires authentication.
    """
    query = """
    MATCH (r1:Requirement {id: $req1_id})-[c:CONFLICTS_WITH]-(r2:Requirement {id: $req2_id})
    DELETE c
    """

    try:
        await Neo4jClient.run_write_query(
            query,
            {"req1_id": requirement_1_id, "req2_id": requirement_2_id},
        )

        logger.info(
            "conflict_removed",
            requirement_1=requirement_1_id,
            requirement_2=requirement_2_id,
            user_id=current_user.id,
        )

    except Exception as e:
        logger.error(
            "remove_conflict_failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove conflict: {str(e)}",
        )

