"""
Compliance Query Engine
=======================

Query engine for compliance status and gap analysis.

Version: 0.1.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from services.compliance_graph.schema.nodes import ComplianceStatus
from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ComplianceGap:
    """A compliance gap (missing or failed compliance)."""

    requirement_id: str
    requirement_text: str
    regulation_id: str
    tier: str
    status: ComplianceStatus
    penalty_risk: float | None = None
    remediation_priority: int = 1  # 1 = highest priority


@dataclass
class ComplianceScore:
    """Compliance score for an entity."""

    total_requirements: int = 0
    compliant: int = 0
    non_compliant: int = 0
    partial: int = 0
    pending: int = 0
    exempt: int = 0
    unknown: int = 0

    @property
    def compliance_rate(self) -> float:
        """Percentage of compliant requirements."""
        if self.total_requirements == 0:
            return 0.0
        return self.compliant / self.total_requirements

    @property
    def risk_score(self) -> float:
        """Risk score (higher = more risk)."""
        if self.total_requirements == 0:
            return 0.0
        return (self.non_compliant + self.partial * 0.5) / self.total_requirements


@dataclass
class ComplianceReport:
    """Comprehensive compliance report for an entity."""

    entity_id: str
    entity_name: str
    generated_at: datetime

    # Overall score
    score: ComplianceScore

    # By jurisdiction
    by_jurisdiction: dict[str, ComplianceScore] = field(default_factory=dict)

    # By regulation
    by_regulation: dict[str, ComplianceScore] = field(default_factory=dict)

    # By tier
    by_tier: dict[str, ComplianceScore] = field(default_factory=dict)

    # Gaps
    critical_gaps: list[ComplianceGap] = field(default_factory=list)
    all_gaps: list[ComplianceGap] = field(default_factory=list)


class ComplianceQueryEngine:
    """
    Query engine for compliance analysis.

    Features:
    - Entity compliance status
    - Gap analysis
    - Risk scoring
    - Compliance path finding
    """

    async def get_entity_compliance_status(
        self,
        entity_id: str,
    ) -> dict[str, Any]:
        """
        Get compliance status for all applicable requirements.

        Args:
            entity_id: Entity ID

        Returns:
            Dictionary of requirement_id -> status
        """
        query = """
        MATCH (e:Entity {id: $entity_id})
        MATCH (e)-[:HAS_STATE]->(cs:ComplianceState)-[:FOR_REQUIREMENT]->(r:Requirement)
        RETURN r.id as requirement_id, 
               cs.status as status,
               cs.confidence as confidence,
               cs.assessed_at as assessed_at
        """

        results = await Neo4jClient.run_query(query, {"entity_id": entity_id})

        return {
            r["requirement_id"]: {
                "status": r["status"],
                "confidence": r["confidence"],
                "assessed_at": r["assessed_at"],
            }
            for r in results
        }

    async def get_compliance_score(
        self,
        entity_id: str,
        jurisdiction: str | None = None,
        regulation_id: str | None = None,
    ) -> ComplianceScore:
        """
        Calculate compliance score for an entity.

        Args:
            entity_id: Entity ID
            jurisdiction: Optional jurisdiction filter
            regulation_id: Optional regulation filter

        Returns:
            ComplianceScore
        """
        # Build query with optional filters
        where_clauses = ["e.id = $entity_id"]
        params: dict[str, Any] = {"entity_id": entity_id}

        if jurisdiction:
            where_clauses.append("$jurisdiction IN r.jurisdictions")
            params["jurisdiction"] = jurisdiction

        if regulation_id:
            where_clauses.append("r.regulation_id = $regulation_id")
            params["regulation_id"] = regulation_id

        where_clause = " AND ".join(where_clauses)

        query = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        
        // Get applicable requirements
        MATCH (r:Requirement)
        WHERE (ANY(j IN r.jurisdictions WHERE j IN e.jurisdictions) OR 'ALL' IN r.jurisdictions)
          AND (ANY(s IN r.sectors WHERE s IN e.sectors) OR 'ALL' IN r.sectors)
        
        // Get compliance states
        OPTIONAL MATCH (e)-[:HAS_STATE]->(cs:ComplianceState {{requirement_id: r.id}})
        
        RETURN 
            count(r) as total,
            sum(CASE WHEN cs.status = 'compliant' THEN 1 ELSE 0 END) as compliant,
            sum(CASE WHEN cs.status = 'non_compliant' THEN 1 ELSE 0 END) as non_compliant,
            sum(CASE WHEN cs.status = 'partial' THEN 1 ELSE 0 END) as partial,
            sum(CASE WHEN cs.status = 'pending' THEN 1 ELSE 0 END) as pending,
            sum(CASE WHEN cs.status = 'exempt' THEN 1 ELSE 0 END) as exempt,
            sum(CASE WHEN cs.status IS NULL OR cs.status = 'unknown' THEN 1 ELSE 0 END) as unknown
        """

        results = await Neo4jClient.run_query(query, params)

        if not results:
            return ComplianceScore()

        r = results[0]
        return ComplianceScore(
            total_requirements=r.get("total", 0),
            compliant=r.get("compliant", 0),
            non_compliant=r.get("non_compliant", 0),
            partial=r.get("partial", 0),
            pending=r.get("pending", 0),
            exempt=r.get("exempt", 0),
            unknown=r.get("unknown", 0),
        )

    async def get_compliance_gaps(
        self,
        entity_id: str,
        include_partial: bool = True,
        include_unknown: bool = False,
    ) -> list[ComplianceGap]:
        """
        Find compliance gaps for an entity.

        Args:
            entity_id: Entity ID
            include_partial: Include partially compliant as gaps
            include_unknown: Include unknown status as gaps

        Returns:
            List of compliance gaps
        """
        status_filter = ["'non_compliant'"]
        if include_partial:
            status_filter.append("'partial'")
        if include_unknown:
            status_filter.append("'unknown'")

        status_list = ", ".join(status_filter)

        query = f"""
        MATCH (e:Entity {{id: $entity_id}})
        
        // Get applicable requirements
        MATCH (r:Requirement)
        WHERE (ANY(j IN r.jurisdictions WHERE j IN e.jurisdictions) OR 'ALL' IN r.jurisdictions)
          AND (ANY(s IN r.sectors WHERE s IN e.sectors) OR 'ALL' IN r.sectors)
        
        // Get compliance states
        OPTIONAL MATCH (e)-[:HAS_STATE]->(cs:ComplianceState {{requirement_id: r.id}})
        
        // Filter to gaps
        WHERE cs.status IN [{status_list}] OR cs IS NULL
        
        RETURN r.id as requirement_id,
               r.natural_language as requirement_text,
               r.regulation_id as regulation_id,
               r.tier as tier,
               COALESCE(cs.status, 'unknown') as status,
               r.penalty_monetary_max as penalty_risk
        ORDER BY 
            CASE r.tier 
                WHEN 'advanced' THEN 1 
                WHEN 'standard' THEN 2 
                ELSE 3 
            END,
            r.penalty_monetary_max DESC NULLS LAST
        """

        results = await Neo4jClient.run_query(query, {"entity_id": entity_id})

        gaps = []
        for i, r in enumerate(results):
            gaps.append(
                ComplianceGap(
                    requirement_id=r["requirement_id"],
                    requirement_text=r["requirement_text"],
                    regulation_id=r["regulation_id"],
                    tier=r["tier"],
                    status=ComplianceStatus(r["status"]),
                    penalty_risk=r.get("penalty_risk"),
                    remediation_priority=i + 1,
                )
            )

        return gaps

    async def generate_compliance_report(
        self,
        entity_id: str,
    ) -> ComplianceReport:
        """
        Generate a comprehensive compliance report.

        Args:
            entity_id: Entity ID

        Returns:
            ComplianceReport
        """
        from datetime import UTC

        # Get entity info
        entity_query = """
        MATCH (e:Entity {id: $entity_id})
        RETURN e.name as name, e.jurisdictions as jurisdictions, e.sectors as sectors
        """
        entity_result = await Neo4jClient.run_query(entity_query, {"entity_id": entity_id})

        if not entity_result:
            raise ValueError(f"Entity not found: {entity_id}")

        entity = entity_result[0]

        # Get overall score
        overall_score = await self.get_compliance_score(entity_id)

        # Get gaps
        all_gaps = await self.get_compliance_gaps(entity_id, include_unknown=True)
        critical_gaps = [
            g
            for g in all_gaps
            if g.tier == "advanced" or (g.penalty_risk and g.penalty_risk > 1000000)
        ]

        # Get score by jurisdiction
        by_jurisdiction: dict[str, ComplianceScore] = {}
        for jurisdiction in entity.get("jurisdictions", []):
            by_jurisdiction[jurisdiction] = await self.get_compliance_score(
                entity_id,
                jurisdiction=jurisdiction,
            )

        # Get score by tier
        by_tier: dict[str, ComplianceScore] = {}
        for tier in ["basic", "standard", "advanced"]:
            score = await self._get_score_by_tier(entity_id, tier)
            by_tier[tier] = score

        return ComplianceReport(
            entity_id=entity_id,
            entity_name=entity.get("name", entity_id),
            generated_at=datetime.now(UTC),
            score=overall_score,
            by_jurisdiction=by_jurisdiction,
            by_tier=by_tier,
            critical_gaps=critical_gaps,
            all_gaps=all_gaps,
        )

    async def _get_score_by_tier(
        self,
        entity_id: str,
        tier: str,
    ) -> ComplianceScore:
        """Get compliance score filtered by tier."""
        query = """
        MATCH (e:Entity {id: $entity_id})
        
        MATCH (r:Requirement)
        WHERE r.tier = $tier
          AND (ANY(j IN r.jurisdictions WHERE j IN e.jurisdictions) OR 'ALL' IN r.jurisdictions)
          AND (ANY(s IN r.sectors WHERE s IN e.sectors) OR 'ALL' IN r.sectors)
        
        OPTIONAL MATCH (e)-[:HAS_STATE]->(cs:ComplianceState {requirement_id: r.id})
        
        RETURN 
            count(r) as total,
            sum(CASE WHEN cs.status = 'compliant' THEN 1 ELSE 0 END) as compliant,
            sum(CASE WHEN cs.status = 'non_compliant' THEN 1 ELSE 0 END) as non_compliant,
            sum(CASE WHEN cs.status = 'partial' THEN 1 ELSE 0 END) as partial,
            sum(CASE WHEN cs.status IS NULL OR cs.status = 'unknown' THEN 1 ELSE 0 END) as unknown
        """

        results = await Neo4jClient.run_query(
            query,
            {"entity_id": entity_id, "tier": tier},
        )

        if not results:
            return ComplianceScore()

        r = results[0]
        return ComplianceScore(
            total_requirements=r.get("total", 0),
            compliant=r.get("compliant", 0),
            non_compliant=r.get("non_compliant", 0),
            partial=r.get("partial", 0),
            unknown=r.get("unknown", 0),
        )

    async def update_compliance_state(
        self,
        entity_id: str,
        requirement_id: str,
        status: ComplianceStatus,
        confidence: float = 1.0,
        assessor: str | None = None,
    ) -> dict[str, Any]:
        """
        Update compliance state for an entity-requirement pair.

        Args:
            entity_id: Entity ID
            requirement_id: Requirement ID
            status: New compliance status
            confidence: Confidence in the assessment
            assessor: Who/what made the assessment

        Returns:
            Update result
        """

        state_id = f"CS-{entity_id}-{requirement_id}"

        query = """
        MATCH (e:Entity {id: $entity_id})
        MATCH (r:Requirement {id: $requirement_id})
        
        MERGE (cs:ComplianceState {id: $state_id})
        SET cs.entity_id = $entity_id,
            cs.requirement_id = $requirement_id,
            cs.status = $status,
            cs.confidence = $confidence,
            cs.assessed_at = datetime(),
            cs.assessor = $assessor
        
        MERGE (e)-[:HAS_STATE]->(cs)
        MERGE (cs)-[:FOR_REQUIREMENT]->(r)
        
        RETURN cs
        """

        result = await Neo4jClient.run_write_query(
            query,
            {
                "entity_id": entity_id,
                "requirement_id": requirement_id,
                "state_id": state_id,
                "status": status.value,
                "confidence": confidence,
                "assessor": assessor,
            },
        )

        logger.info(
            "compliance_state_updated",
            entity_id=entity_id,
            requirement_id=requirement_id,
            status=status.value,
        )

        return result
