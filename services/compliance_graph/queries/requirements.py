"""
Requirement Query Engine
========================

Query engine for searching and filtering requirements in the compliance graph.

Version: 0.1.0
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class RequirementSearchResult:
    """A requirement from search results."""

    id: str
    regulation_id: str
    article_ref: str
    natural_language: str
    tier: str
    verification_method: str

    # Optional fields
    formal_logic: str | None = None
    summary: str | None = None
    jurisdictions: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    effective_date: str | None = None
    penalty_monetary_max: float | None = None

    # Search metadata
    score: float | None = None  # Full-text search score


@dataclass
class RequirementFilter:
    """Filters for requirement queries."""

    # Text search
    text_search: str | None = None

    # Classification filters
    tiers: list[str] | None = None
    verification_methods: list[str] | None = None

    # Scope filters
    jurisdictions: list[str] | None = None
    sectors: list[str] | None = None
    governance_layers: list[int] | None = None

    # Regulation filters
    regulation_ids: list[str] | None = None

    # Date filters
    effective_after: date | None = None
    effective_before: date | None = None

    # Pagination
    skip: int = 0
    limit: int = 100


class RequirementQueryEngine:
    """
    Query engine for requirements in the compliance graph.

    Features:
    - Full-text search
    - Multi-dimensional filtering
    - Relationship-based queries
    - Aggregations and statistics
    """

    async def search(
        self,
        filter: RequirementFilter,
    ) -> list[RequirementSearchResult]:
        """
        Search requirements with filters.

        Args:
            filter: Search filters

        Returns:
            List of matching requirements
        """
        if filter.text_search:
            return await self._full_text_search(filter)
        else:
            return await self._filtered_search(filter)

    async def _full_text_search(
        self,
        filter: RequirementFilter,
    ) -> list[RequirementSearchResult]:
        """Execute full-text search with additional filters."""
        # Build WHERE clause for additional filters
        where_clauses = self._build_where_clauses(filter)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        CALL db.index.fulltext.queryNodes('requirement_text_search', $search_text)
        YIELD node, score
        WITH node as r, score
        {where_clause}
        RETURN r, score
        ORDER BY score DESC
        SKIP $skip
        LIMIT $limit
        """

        params = {
            "search_text": filter.text_search,
            "skip": filter.skip,
            "limit": filter.limit,
        }

        # Add filter parameters
        params.update(self._get_filter_params(filter))

        try:
            results = await Neo4jClient.run_query(query, params)
            return [self._record_to_result(r, r.get("score")) for r in results]
        except Exception as e:
            logger.warning(
                "fulltext_search_failed",
                error=str(e),
                fallback="filtered_search",
            )
            # Fall back to filtered search with CONTAINS
            return await self._filtered_search_with_contains(filter)

    async def _filtered_search(
        self,
        filter: RequirementFilter,
    ) -> list[RequirementSearchResult]:
        """Execute filtered search without full-text."""
        where_clauses = self._build_where_clauses(filter)
        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        MATCH (r:Requirement)
        {where_clause}
        RETURN r
        ORDER BY r.regulation_id, r.article_ref
        SKIP $skip
        LIMIT $limit
        """

        params = {
            "skip": filter.skip,
            "limit": filter.limit,
        }
        params.update(self._get_filter_params(filter))

        results = await Neo4jClient.run_query(query, params)
        return [self._record_to_result(r) for r in results]

    async def _filtered_search_with_contains(
        self,
        filter: RequirementFilter,
    ) -> list[RequirementSearchResult]:
        """Fallback search using CONTAINS."""
        where_clauses = self._build_where_clauses(filter)

        # Add text search using CONTAINS
        if filter.text_search:
            where_clauses.append(
                "(toLower(r.natural_language) CONTAINS toLower($search_text) "
                "OR toLower(r.summary) CONTAINS toLower($search_text))"
            )

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        MATCH (r:Requirement)
        {where_clause}
        RETURN r
        ORDER BY r.regulation_id, r.article_ref
        SKIP $skip
        LIMIT $limit
        """

        params = {
            "search_text": filter.text_search,
            "skip": filter.skip,
            "limit": filter.limit,
        }
        params.update(self._get_filter_params(filter))

        results = await Neo4jClient.run_query(query, params)
        return [self._record_to_result(r) for r in results]

    def _build_where_clauses(self, filter: RequirementFilter) -> list[str]:
        """Build WHERE clause conditions."""
        clauses = []

        if filter.tiers:
            clauses.append("r.tier IN $tiers")

        if filter.verification_methods:
            clauses.append("r.verification_method IN $verification_methods")

        if filter.jurisdictions:
            clauses.append("ANY(j IN r.jurisdictions WHERE j IN $jurisdictions)")

        if filter.sectors:
            clauses.append("ANY(s IN r.sectors WHERE s IN $sectors)")

        if filter.governance_layers:
            clauses.append("r.governance_layer IN $governance_layers")

        if filter.regulation_ids:
            clauses.append("r.regulation_id IN $regulation_ids")

        if filter.effective_after:
            clauses.append("r.effective_date >= date($effective_after)")

        if filter.effective_before:
            clauses.append("r.effective_date <= date($effective_before)")

        return clauses

    def _get_filter_params(self, filter: RequirementFilter) -> dict[str, Any]:
        """Get parameters for filters."""
        params: dict[str, Any] = {}

        if filter.tiers:
            params["tiers"] = filter.tiers
        if filter.verification_methods:
            params["verification_methods"] = filter.verification_methods
        if filter.jurisdictions:
            params["jurisdictions"] = filter.jurisdictions
        if filter.sectors:
            params["sectors"] = filter.sectors
        if filter.governance_layers:
            params["governance_layers"] = filter.governance_layers
        if filter.regulation_ids:
            params["regulation_ids"] = filter.regulation_ids
        if filter.effective_after:
            params["effective_after"] = filter.effective_after.isoformat()
        if filter.effective_before:
            params["effective_before"] = filter.effective_before.isoformat()

        return params

    def _record_to_result(
        self,
        record: dict[str, Any],
        score: float | None = None,
    ) -> RequirementSearchResult:
        """Convert Neo4j record to result object."""
        r = record.get("r", {})

        return RequirementSearchResult(
            id=r.get("id", ""),
            regulation_id=r.get("regulation_id", ""),
            article_ref=r.get("article_ref", ""),
            natural_language=r.get("natural_language", ""),
            tier=r.get("tier", "basic"),
            verification_method=r.get("verification_method", "self_attestation"),
            formal_logic=r.get("formal_logic"),
            summary=r.get("summary"),
            jurisdictions=r.get("jurisdictions", []),
            sectors=r.get("sectors", []),
            effective_date=r.get("effective_date"),
            penalty_monetary_max=r.get("penalty_monetary_max"),
            score=score,
        )

    async def get_by_id(self, requirement_id: str) -> RequirementSearchResult | None:
        """Get a specific requirement by ID."""
        query = """
        MATCH (r:Requirement {id: $id})
        RETURN r
        """

        results = await Neo4jClient.run_query(query, {"id": requirement_id})

        if not results:
            return None

        return self._record_to_result(results[0])

    async def get_by_regulation(
        self,
        regulation_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[RequirementSearchResult]:
        """Get all requirements for a regulation."""
        query = """
        MATCH (r:Requirement {regulation_id: $regulation_id})
        RETURN r
        ORDER BY r.article_ref
        SKIP $skip
        LIMIT $limit
        """

        results = await Neo4jClient.run_query(
            query,
            {"regulation_id": regulation_id, "skip": skip, "limit": limit},
        )

        return [self._record_to_result(r) for r in results]

    async def get_applicable_requirements(
        self,
        entity_id: str,
    ) -> list[RequirementSearchResult]:
        """
        Get requirements applicable to an entity.

        Considers entity's jurisdiction and sector.
        """
        query = """
        MATCH (e:Entity {id: $entity_id})
        MATCH (r:Requirement)
        WHERE (ANY(j IN r.jurisdictions WHERE j IN e.jurisdictions)
               OR 'ALL' IN r.jurisdictions)
          AND (ANY(s IN r.sectors WHERE s IN e.sectors)
               OR 'ALL' IN r.sectors)
        RETURN r
        ORDER BY r.tier, r.regulation_id
        """

        results = await Neo4jClient.run_query(query, {"entity_id": entity_id})
        return [self._record_to_result(r) for r in results]

    async def count_by_tier(
        self,
        jurisdiction: str | None = None,
    ) -> dict[str, int]:
        """Count requirements by tier."""
        where_clause = ""
        params: dict[str, Any] = {}

        if jurisdiction:
            where_clause = "WHERE $jurisdiction IN r.jurisdictions"
            params["jurisdiction"] = jurisdiction

        query = f"""
        MATCH (r:Requirement)
        {where_clause}
        RETURN r.tier as tier, count(r) as count
        ORDER BY tier
        """

        results = await Neo4jClient.run_query(query, params)

        return {r["tier"]: r["count"] for r in results}

    async def count_by_jurisdiction(self) -> dict[str, int]:
        """Count requirements by jurisdiction."""
        query = """
        MATCH (r:Requirement)
        UNWIND r.jurisdictions as jurisdiction
        RETURN jurisdiction, count(r) as count
        ORDER BY count DESC
        """

        results = await Neo4jClient.run_query(query)
        return {r["jurisdiction"]: r["count"] for r in results}
