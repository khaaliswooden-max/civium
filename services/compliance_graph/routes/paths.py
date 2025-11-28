"""
Graph Path Discovery Routes
===========================

API endpoints for compliance path discovery and analysis.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.auth import get_current_user, User
from shared.logging import get_logger

from services.compliance_graph.queries.paths import (
    PathFinder,
    DependencyChain,
    CompliancePath,
    ConflictPair,
)

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Response Models
# =============================================================================


class PathNodeResponse(BaseModel):
    """A node in a path."""

    id: str
    label: str
    name: str
    properties: dict[str, Any]


class PathEdgeResponse(BaseModel):
    """An edge in a path."""

    type: str
    from_id: str
    to_id: str
    properties: dict[str, Any]


class CompliancePathResponse(BaseModel):
    """A compliance path."""

    nodes: list[PathNodeResponse]
    edges: list[PathEdgeResponse]
    length: int


class DependencyChainResponse(BaseModel):
    """A chain of requirement dependencies."""

    root_requirement_id: str
    requirements: list[dict[str, Any]]
    depth: int
    has_cycles: bool
    cycle_at: str | None


class ConflictResponse(BaseModel):
    """A conflict between requirements."""

    requirement_a_id: str
    requirement_a_text: str
    requirement_b_id: str
    requirement_b_text: str
    conflict_type: str
    resolution: str | None


class ImpactAnalysisResponse(BaseModel):
    """Impact analysis for a requirement."""

    requirement_id: str
    affected_entities: int
    dependent_requirements: int
    dependents: list[dict[str, Any]]
    conflicts: int
    conflict_details: list[ConflictResponse]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/dependencies/{requirement_id}", response_model=DependencyChainResponse)
async def get_dependency_chain(
    requirement_id: str,
    max_depth: int = Query(default=10, ge=1, le=50),
) -> DependencyChainResponse:
    """
    Get all dependencies (prerequisites) for a requirement.

    Traverses DEPENDS_ON relationships to find all requirements
    that must be satisfied before this one.

    Args:
        requirement_id: The requirement to analyze
        max_depth: Maximum traversal depth
    """
    finder = PathFinder()

    try:
        chain = await finder.find_dependency_chain(requirement_id, max_depth)

        return DependencyChainResponse(
            root_requirement_id=chain.root_requirement_id,
            requirements=chain.requirements,
            depth=chain.depth,
            has_cycles=chain.has_cycles,
            cycle_at=chain.cycle_at,
        )

    except Exception as e:
        logger.error("dependency_chain_failed", requirement_id=requirement_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dependency chain: {str(e)}",
        )


@router.get("/dependents/{requirement_id}")
async def get_dependents(
    requirement_id: str,
    max_depth: int = Query(default=10, ge=1, le=50),
) -> list[dict[str, Any]]:
    """
    Get all requirements that depend on this one.

    Reverse traversal - finds what breaks if this requirement changes.

    Args:
        requirement_id: The requirement to analyze
        max_depth: Maximum traversal depth
    """
    finder = PathFinder()

    try:
        return await finder.find_dependents(requirement_id, max_depth)

    except Exception as e:
        logger.error("dependents_failed", requirement_id=requirement_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dependents: {str(e)}",
        )


@router.get("/conflicts", response_model=list[ConflictResponse])
async def get_conflicts(
    requirement_id: str | None = Query(default=None),
    jurisdiction: str | None = Query(default=None),
) -> list[ConflictResponse]:
    """
    Find conflicting requirements.

    Requirements that cannot both be satisfied simultaneously.

    Args:
        requirement_id: Find conflicts for specific requirement
        jurisdiction: Find conflicts within a jurisdiction
    """
    finder = PathFinder()

    try:
        conflicts = await finder.find_conflicts(requirement_id, jurisdiction)

        return [
            ConflictResponse(
                requirement_a_id=c.requirement_a_id,
                requirement_a_text=c.requirement_a_text,
                requirement_b_id=c.requirement_b_id,
                requirement_b_text=c.requirement_b_text,
                conflict_type=c.conflict_type,
                resolution=c.resolution,
            )
            for c in conflicts
        ]

    except Exception as e:
        logger.error("conflicts_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find conflicts: {str(e)}",
        )


@router.get("/compliance-path")
async def get_compliance_path(
    entity_id: str = Query(...),
    requirement_id: str = Query(...),
) -> CompliancePathResponse | None:
    """
    Find the compliance path from entity to requirement.

    Shows how a requirement applies to an entity through
    jurisdictions, sectors, and regulations.

    Args:
        entity_id: Entity ID
        requirement_id: Requirement ID
    """
    finder = PathFinder()

    try:
        path = await finder.find_compliance_path(entity_id, requirement_id)

        if path is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No compliance path found from {entity_id} to {requirement_id}",
            )

        return CompliancePathResponse(
            nodes=[
                PathNodeResponse(
                    id=n.id,
                    label=n.label,
                    name=n.name,
                    properties=n.properties,
                )
                for n in path.nodes
            ],
            edges=[
                PathEdgeResponse(
                    type=e.type,
                    from_id=e.from_id,
                    to_id=e.to_id,
                    properties=e.properties,
                )
                for e in path.edges
            ],
            length=path.length,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("compliance_path_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find compliance path: {str(e)}",
        )


@router.get("/impact/{requirement_id}", response_model=ImpactAnalysisResponse)
async def analyze_impact(
    requirement_id: str,
) -> ImpactAnalysisResponse:
    """
    Analyze the impact of changing a requirement.

    Returns:
    - Number of affected entities
    - Number of dependent requirements
    - Conflicts that might be affected
    """
    finder = PathFinder()

    try:
        impact = await finder.analyze_impact(requirement_id)

        return ImpactAnalysisResponse(
            requirement_id=impact["requirement_id"],
            affected_entities=impact["affected_entities"],
            dependent_requirements=impact["dependent_requirements"],
            dependents=impact["dependents"],
            conflicts=impact["conflicts"],
            conflict_details=[
                ConflictResponse(
                    requirement_a_id=c.requirement_a_id,
                    requirement_a_text=c.requirement_a_text,
                    requirement_b_id=c.requirement_b_id,
                    requirement_b_text=c.requirement_b_text,
                    conflict_type=c.conflict_type,
                    resolution=c.resolution,
                )
                for c in impact["conflict_details"]
            ],
        )

    except Exception as e:
        logger.error("impact_analysis_failed", requirement_id=requirement_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze impact: {str(e)}",
        )


@router.get("/common-ancestors")
async def find_common_ancestors(
    requirement_ids: str = Query(..., description="Comma-separated requirement IDs"),
) -> list[dict[str, Any]]:
    """
    Find common ancestor requirements (shared dependencies).

    Useful for identifying shared compliance foundations.

    Args:
        requirement_ids: Comma-separated list of requirement IDs
    """
    ids = [r.strip() for r in requirement_ids.split(",") if r.strip()]

    if len(ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 requirement IDs required",
        )

    finder = PathFinder()

    try:
        return await finder.find_common_ancestors(ids)

    except Exception as e:
        logger.error("common_ancestors_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find common ancestors: {str(e)}",
        )

