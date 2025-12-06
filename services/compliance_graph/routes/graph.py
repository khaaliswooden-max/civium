"""
Graph Operations Routes
=======================

API endpoints for graph database operations.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.auth import User, get_current_user
from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger
from shared.models.regulation import Requirement


logger = get_logger(__name__)

router = APIRouter()


class RequirementNode(BaseModel):
    """Graph representation of a requirement."""

    id: str
    regulation_id: str
    natural_language: str
    tier: str
    jurisdiction: str | None = None
    effective_date: str | None = None


class GraphStats(BaseModel):
    """Graph statistics."""

    total_requirements: int = 0
    total_entities: int = 0
    total_compliance_states: int = 0
    total_relationships: int = 0


class GraphQuery(BaseModel):
    """Custom Cypher query request."""

    query: str = Field(..., description="Cypher query to execute")
    parameters: dict[str, Any] = Field(default_factory=dict)


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats() -> GraphStats:
    """
    Get graph database statistics.

    Returns counts of nodes and relationships.
    """
    try:
        # Count requirements
        req_result = await Neo4jClient.run_query("MATCH (r:Requirement) RETURN count(r) as count")
        req_count = req_result[0]["count"] if req_result else 0

        # Count entities
        entity_result = await Neo4jClient.run_query("MATCH (e:Entity) RETURN count(e) as count")
        entity_count = entity_result[0]["count"] if entity_result else 0

        # Count compliance states
        state_result = await Neo4jClient.run_query(
            "MATCH (cs:ComplianceState) RETURN count(cs) as count"
        )
        state_count = state_result[0]["count"] if state_result else 0

        # Count relationships
        rel_result = await Neo4jClient.run_query("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = rel_result[0]["count"] if rel_result else 0

        return GraphStats(
            total_requirements=req_count,
            total_entities=entity_count,
            total_compliance_states=state_count,
            total_relationships=rel_count,
        )

    except Exception as e:
        logger.error("graph_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get graph stats: {e!s}",
        )


@router.get("/requirements", response_model=list[RequirementNode])
async def get_requirements(
    jurisdiction: str | None = Query(default=None),
    tier: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[RequirementNode]:
    """
    Get requirement nodes from the graph.

    Args:
        jurisdiction: Filter by jurisdiction
        tier: Filter by compliance tier
        limit: Maximum nodes to return
    """
    # Build query with optional filters
    where_clauses = []
    params: dict[str, Any] = {"limit": limit}

    if jurisdiction:
        where_clauses.append("r.jurisdiction = $jurisdiction")
        params["jurisdiction"] = jurisdiction.upper()

    if tier:
        where_clauses.append("r.tier = $tier")
        params["tier"] = tier.lower()

    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"""
    MATCH (r:Requirement)
    {where_clause}
    RETURN r
    LIMIT $limit
    """

    try:
        results = await Neo4jClient.run_query(query, params)

        requirements = []
        for record in results:
            node = record.get("r", {})
            requirements.append(
                RequirementNode(
                    id=node.get("id", ""),
                    regulation_id=node.get("regulation_id", ""),
                    natural_language=node.get("natural_language", ""),
                    tier=node.get("tier", "basic"),
                    jurisdiction=node.get("jurisdiction"),
                    effective_date=str(node.get("effective_date"))
                    if node.get("effective_date")
                    else None,
                )
            )

        return requirements

    except Exception as e:
        logger.error("get_requirements_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {e!s}",
        )


@router.post("/requirements", status_code=status.HTTP_201_CREATED)
async def add_requirement_to_graph(
    requirement: Requirement,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Add a requirement node to the graph.

    Requires authentication.
    """
    query = """
    MERGE (r:Requirement {id: $id})
    SET r.regulation_id = $regulation_id,
        r.natural_language = $natural_language,
        r.formal_logic = $formal_logic,
        r.tier = $tier,
        r.verification_method = $verification_method,
        r.effective_date = date($effective_date),
        r.created_at = datetime(),
        r.updated_at = datetime()
    RETURN r
    """

    params = {
        "id": requirement.id,
        "regulation_id": requirement.regulation_id,
        "natural_language": requirement.natural_language,
        "formal_logic": requirement.formal_logic or "",
        "tier": requirement.tier.value,
        "verification_method": requirement.verification_method.value,
        "effective_date": str(requirement.effective_date) if requirement.effective_date else None,
    }

    try:
        counters = await Neo4jClient.run_write_query(query, params)

        logger.info(
            "requirement_added_to_graph",
            requirement_id=requirement.id,
            user_id=current_user.id,
        )

        return {
            "success": True,
            "requirement_id": requirement.id,
            "counters": counters,
        }

    except Exception as e:
        logger.error("add_requirement_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add requirement: {e!s}",
        )


@router.post("/query")
async def execute_cypher_query(
    query_request: GraphQuery,
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Execute a custom Cypher query.

    Only read queries are allowed. Write queries require admin role.

    Requires authentication.
    """
    query = query_request.query.strip()

    # Basic security: block write operations for non-admins
    write_keywords = ["CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP"]
    is_write_query = any(kw in query.upper() for kw in write_keywords)

    if is_write_query and "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write queries require admin role",
        )

    try:
        if is_write_query:
            result = await Neo4jClient.run_write_query(
                query,
                query_request.parameters,
            )
            return [result]
        else:
            results = await Neo4jClient.run_query(
                query,
                query_request.parameters,
            )
            return results

    except Exception as e:
        logger.error(
            "cypher_query_failed",
            query=query[:100],
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query failed: {e!s}",
        )
