"""
Entity Graph Routes
===================

API endpoints for entity-related graph operations.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from shared.auth import User, get_current_user
from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger
from shared.models.compliance import ComplianceGap, ComplianceStatus


logger = get_logger(__name__)

router = APIRouter()


class EntityRequirements(BaseModel):
    """Requirements applicable to an entity."""

    entity_id: str
    total_requirements: int
    requirements: list[dict[str, Any]]


class EntityComplianceState(BaseModel):
    """Compliance state for an entity."""

    entity_id: str
    compliant: int = 0
    non_compliant: int = 0
    partial: int = 0
    not_assessed: int = 0


@router.get("/{entity_id}/requirements", response_model=EntityRequirements)
async def get_entity_requirements(
    entity_id: str,
    tier: str | None = Query(default=None, description="Filter by tier"),
    limit: int = Query(default=100, ge=1, le=500),
) -> EntityRequirements:
    """
    Get all requirements applicable to an entity.

    This queries the graph to find requirements that apply based on:
    - Entity's jurisdictions
    - Entity's sectors
    - Entity type

    Args:
        entity_id: Entity ID
        tier: Optional tier filter
        limit: Maximum requirements to return
    """
    # Build Cypher query
    tier_filter = "AND r.tier = $tier" if tier else ""

    query = f"""
    MATCH (e:Entity {{id: $entity_id}})<-[:APPLIES_TO]-(r:Requirement)
    WHERE r.effective_date <= date()
    {tier_filter}
    RETURN r
    ORDER BY r.tier, r.id
    LIMIT $limit
    """

    params: dict[str, Any] = {
        "entity_id": entity_id,
        "limit": limit,
    }
    if tier:
        params["tier"] = tier.lower()

    try:
        results = await Neo4jClient.run_query(query, params)

        requirements = []
        for record in results:
            node = record.get("r", {})
            requirements.append(
                {
                    "id": node.get("id"),
                    "regulation_id": node.get("regulation_id"),
                    "natural_language": node.get("natural_language"),
                    "tier": node.get("tier"),
                    "verification_method": node.get("verification_method"),
                }
            )

        return EntityRequirements(
            entity_id=entity_id,
            total_requirements=len(requirements),
            requirements=requirements,
        )

    except Exception as e:
        logger.error(
            "get_entity_requirements_failed",
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {e!s}",
        )


@router.get("/{entity_id}/compliance-state", response_model=EntityComplianceState)
async def get_entity_compliance_state(
    entity_id: str,
) -> EntityComplianceState:
    """
    Get compliance state summary for an entity.

    Returns counts of requirements by compliance status.
    """
    query = """
    MATCH (e:Entity {id: $entity_id})-[:HAS_STATE]->(cs:ComplianceState)
    RETURN cs.status as status, count(cs) as count
    """

    try:
        results = await Neo4jClient.run_query(query, {"entity_id": entity_id})

        state = EntityComplianceState(entity_id=entity_id)

        for record in results:
            status = record.get("status", "")
            count = record.get("count", 0)

            if status == "compliant":
                state.compliant = count
            elif status == "non_compliant":
                state.non_compliant = count
            elif status == "partially_compliant":
                state.partial = count
            else:
                state.not_assessed += count

        return state

    except Exception as e:
        logger.error(
            "get_compliance_state_failed",
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {e!s}",
        )


@router.get("/{entity_id}/gaps", response_model=list[ComplianceGap])
async def get_entity_compliance_gaps(
    entity_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ComplianceGap]:
    """
    Compute compliance gaps for an entity.

    A gap is a requirement that applies to the entity but does not
    have a compliant state.
    """
    query = """
    MATCH (e:Entity {id: $entity_id})<-[:APPLIES_TO]-(r:Requirement)
    WHERE r.effective_date <= date()
    AND NOT EXISTS {
        MATCH (e)-[:HAS_STATE]->(cs:ComplianceState {status: 'compliant'})-[:FOR]->(r)
    }
    OPTIONAL MATCH (reg:Regulation {id: r.regulation_id})
    RETURN r, reg
    LIMIT $limit
    """

    try:
        results = await Neo4jClient.run_query(
            query,
            {"entity_id": entity_id, "limit": limit},
        )

        gaps = []
        for record in results:
            req_node = record.get("r", {})
            reg_node = record.get("reg", {})

            # Determine priority based on tier
            tier = req_node.get("tier", "basic")
            priority = {
                "basic": "medium",
                "standard": "high",
                "advanced": "critical",
            }.get(tier, "medium")

            gaps.append(
                ComplianceGap(
                    entity_id=entity_id,
                    requirement_id=req_node.get("id", ""),
                    requirement_text=req_node.get("natural_language"),
                    regulation_id=req_node.get("regulation_id"),
                    regulation_name=reg_node.get("name") if reg_node else None,
                    current_status=ComplianceStatus.NOT_ASSESSED,
                    priority=priority,
                )
            )

        logger.debug(
            "compliance_gaps_computed",
            entity_id=entity_id,
            gap_count=len(gaps),
        )

        return gaps

    except Exception as e:
        logger.error(
            "get_gaps_failed",
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {e!s}",
        )


@router.post("/{entity_id}/compliance-state", status_code=status.HTTP_201_CREATED)
async def update_compliance_state(
    entity_id: str,
    requirement_id: str,
    status: ComplianceStatus,
    evidence_hash: str | None = None,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Update compliance state for an entity-requirement pair.

    Creates or updates the compliance state relationship in the graph.

    Requires authentication.
    """

    query = """
    MATCH (e:Entity {id: $entity_id})
    MATCH (r:Requirement {id: $requirement_id})
    MERGE (e)-[:HAS_STATE]->(cs:ComplianceState {entity_id: $entity_id, requirement_id: $requirement_id})
    SET cs.status = $status,
        cs.verification_timestamp = datetime(),
        cs.evidence_hash = $evidence_hash,
        cs.verified_by = $verified_by
    MERGE (cs)-[:FOR]->(r)
    RETURN cs
    """

    params = {
        "entity_id": entity_id,
        "requirement_id": requirement_id,
        "status": status.value,
        "evidence_hash": evidence_hash,
        "verified_by": current_user.id,
    }

    try:
        counters = await Neo4jClient.run_write_query(query, params)

        logger.info(
            "compliance_state_updated",
            entity_id=entity_id,
            requirement_id=requirement_id,
            status=status.value,
            user_id=current_user.id,
        )

        return {
            "success": True,
            "entity_id": entity_id,
            "requirement_id": requirement_id,
            "status": status.value,
            "counters": counters,
        }

    except Exception as e:
        logger.error(
            "update_compliance_state_failed",
            entity_id=entity_id,
            requirement_id=requirement_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Update failed: {e!s}",
        )


@router.post("/{entity_id}/sync", status_code=status.HTTP_200_OK)
async def sync_entity_to_graph(
    entity_id: str,
    entity_data: dict[str, Any],
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Sync entity data to the graph.

    Creates or updates the entity node and establishes
    APPLIES_TO relationships based on jurisdictions and sectors.

    Requires authentication.
    """
    # Create/update entity node
    entity_query = """
    MERGE (e:Entity {id: $id})
    SET e.name = $name,
        e.type = $type,
        e.sectors = $sectors,
        e.jurisdictions = $jurisdictions,
        e.compliance_tier = $compliance_tier,
        e.compliance_score = $compliance_score,
        e.updated_at = datetime()
    RETURN e
    """

    entity_params = {
        "id": entity_id,
        "name": entity_data.get("name", ""),
        "type": entity_data.get("entity_type", "corporation"),
        "sectors": entity_data.get("sectors", []),
        "jurisdictions": entity_data.get("jurisdictions", []),
        "compliance_tier": entity_data.get("compliance_tier", "basic"),
        "compliance_score": entity_data.get("compliance_score"),
    }

    try:
        await Neo4jClient.run_write_query(entity_query, entity_params)

        # Create APPLIES_TO relationships based on jurisdictions
        relationship_query = """
        MATCH (e:Entity {id: $entity_id})
        MATCH (r:Requirement)
        WHERE r.jurisdiction IN e.jurisdictions
           OR any(j IN e.jurisdictions WHERE j IN r.jurisdictions)
        MERGE (r)-[:APPLIES_TO]->(e)
        RETURN count(*) as relationships_created
        """

        result = await Neo4jClient.run_query(
            relationship_query,
            {"entity_id": entity_id},
        )
        rel_count = result[0].get("relationships_created", 0) if result else 0

        logger.info(
            "entity_synced_to_graph",
            entity_id=entity_id,
            relationships=rel_count,
            user_id=current_user.id,
        )

        return {
            "success": True,
            "entity_id": entity_id,
            "relationships_created": rel_count,
        }

    except Exception as e:
        logger.error(
            "sync_entity_failed",
            entity_id=entity_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {e!s}",
        )
