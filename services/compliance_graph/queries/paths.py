"""
Compliance Path Finder
======================

Graph traversal algorithms for compliance path discovery.

Features:
- Dependency chain analysis
- Compliance path finding
- Conflict detection
- Impact analysis

Version: 0.1.0
"""

from dataclasses import dataclass, field
from typing import Any

from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class PathNode:
    """A node in a compliance path."""

    id: str
    label: str  # Node label (Requirement, Entity, etc.)
    name: str  # Display name
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class PathEdge:
    """An edge in a compliance path."""

    type: str  # Relationship type
    from_id: str
    to_id: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompliancePath:
    """A path through the compliance graph."""

    nodes: list[PathNode] = field(default_factory=list)
    edges: list[PathEdge] = field(default_factory=list)
    length: int = 0
    total_cost: float = 0.0  # For weighted paths

    @property
    def start_node(self) -> PathNode | None:
        """Get the starting node."""
        return self.nodes[0] if self.nodes else None

    @property
    def end_node(self) -> PathNode | None:
        """Get the ending node."""
        return self.nodes[-1] if self.nodes else None


@dataclass
class DependencyChain:
    """A chain of requirement dependencies."""

    root_requirement_id: str
    requirements: list[dict[str, Any]] = field(default_factory=list)
    depth: int = 0
    has_cycles: bool = False
    cycle_at: str | None = None  # ID where cycle detected


@dataclass
class ConflictPair:
    """Two conflicting requirements."""

    requirement_a_id: str
    requirement_a_text: str
    requirement_b_id: str
    requirement_b_text: str
    conflict_type: str
    resolution: str | None = None


class PathFinder:
    """
    Graph path finding algorithms for compliance analysis.

    Algorithms:
    - Dependency chain traversal
    - Shortest compliance path
    - All paths between nodes
    - Cycle detection
    - Conflict identification
    """

    async def find_dependency_chain(
        self,
        requirement_id: str,
        max_depth: int = 10,
    ) -> DependencyChain:
        """
        Find all dependencies of a requirement (prerequisites).

        Uses BFS to traverse DEPENDS_ON relationships.

        Args:
            requirement_id: Starting requirement
            max_depth: Maximum traversal depth

        Returns:
            DependencyChain with all prerequisites
        """
        query = """
        MATCH path = (start:Requirement {id: $req_id})-[:DEPENDS_ON*1..]->(dep:Requirement)
        WHERE length(path) <= $max_depth
        RETURN dep.id as dep_id,
               dep.natural_language as text,
               dep.tier as tier,
               dep.regulation_id as regulation_id,
               length(path) as depth
        ORDER BY depth
        """

        results = await Neo4jClient.run_query(
            query,
            {"req_id": requirement_id, "max_depth": max_depth},
        )

        requirements = []
        seen_ids = set()
        max_depth_found = 0

        for r in results:
            dep_id = r["dep_id"]
            if dep_id not in seen_ids:
                seen_ids.add(dep_id)
                requirements.append(
                    {
                        "id": dep_id,
                        "text": r["text"],
                        "tier": r["tier"],
                        "regulation_id": r["regulation_id"],
                        "depth": r["depth"],
                    }
                )
                max_depth_found = max(max_depth_found, r["depth"])

        # Check for cycles
        cycle_query = """
        MATCH (start:Requirement {id: $req_id})
        MATCH path = (start)-[:DEPENDS_ON*]->(start)
        RETURN start.id as cycle_at
        LIMIT 1
        """

        cycle_results = await Neo4jClient.run_query(
            cycle_query,
            {"req_id": requirement_id},
        )

        has_cycles = len(cycle_results) > 0
        cycle_at = cycle_results[0]["cycle_at"] if has_cycles else None

        return DependencyChain(
            root_requirement_id=requirement_id,
            requirements=requirements,
            depth=max_depth_found,
            has_cycles=has_cycles,
            cycle_at=cycle_at,
        )

    async def find_dependents(
        self,
        requirement_id: str,
        max_depth: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Find all requirements that depend on this one.

        Reverse traversal of DEPENDS_ON.

        Args:
            requirement_id: Target requirement
            max_depth: Maximum depth

        Returns:
            List of dependent requirements
        """
        query = """
        MATCH path = (dep:Requirement)-[:DEPENDS_ON*1..]->(target:Requirement {id: $req_id})
        WHERE length(path) <= $max_depth
        RETURN dep.id as id,
               dep.natural_language as text,
               dep.tier as tier,
               dep.regulation_id as regulation_id,
               length(path) as depth
        ORDER BY depth
        """

        results = await Neo4jClient.run_query(
            query,
            {"req_id": requirement_id, "max_depth": max_depth},
        )

        seen = set()
        dependents = []

        for r in results:
            if r["id"] not in seen:
                seen.add(r["id"])
                dependents.append(
                    {
                        "id": r["id"],
                        "text": r["text"],
                        "tier": r["tier"],
                        "regulation_id": r["regulation_id"],
                        "depth": r["depth"],
                    }
                )

        return dependents

    async def find_conflicts(
        self,
        requirement_id: str | None = None,
        jurisdiction: str | None = None,
    ) -> list[ConflictPair]:
        """
        Find conflicting requirements.

        Args:
            requirement_id: Find conflicts for specific requirement
            jurisdiction: Find conflicts within a jurisdiction

        Returns:
            List of conflict pairs
        """
        where_clauses = []
        params: dict[str, Any] = {}

        if requirement_id:
            where_clauses.append("(a.id = $req_id OR b.id = $req_id)")
            params["req_id"] = requirement_id

        if jurisdiction:
            where_clauses.append(
                "$jurisdiction IN a.jurisdictions AND $jurisdiction IN b.jurisdictions"
            )
            params["jurisdiction"] = jurisdiction

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        MATCH (a:Requirement)-[r:CONFLICTS_WITH]-(b:Requirement)
        {where_clause}
        RETURN DISTINCT
               a.id as a_id,
               a.natural_language as a_text,
               b.id as b_id,
               b.natural_language as b_text,
               r.conflict_type as conflict_type,
               r.resolution as resolution
        """

        results = await Neo4jClient.run_query(query, params)

        conflicts = []
        seen = set()

        for r in results:
            # Normalize pair order to avoid duplicates
            pair_key = tuple(sorted([r["a_id"], r["b_id"]]))
            if pair_key not in seen:
                seen.add(pair_key)
                conflicts.append(
                    ConflictPair(
                        requirement_a_id=r["a_id"],
                        requirement_a_text=r["a_text"],
                        requirement_b_id=r["b_id"],
                        requirement_b_text=r["b_text"],
                        conflict_type=r.get("conflict_type", "unknown"),
                        resolution=r.get("resolution"),
                    )
                )

        return conflicts

    async def find_compliance_path(
        self,
        entity_id: str,
        requirement_id: str,
    ) -> CompliancePath | None:
        """
        Find the compliance path from entity to requirement.

        Shows how a requirement applies to an entity through
        jurisdictions and sectors.

        Args:
            entity_id: Entity ID
            requirement_id: Requirement ID

        Returns:
            CompliancePath or None if no path exists
        """
        query = """
        MATCH (e:Entity {id: $entity_id}), (r:Requirement {id: $req_id})
        
        // Check if requirement applies to entity
        WHERE (ANY(j IN r.jurisdictions WHERE j IN e.jurisdictions) OR 'ALL' IN r.jurisdictions)
          AND (ANY(s IN r.sectors WHERE s IN e.sectors) OR 'ALL' IN r.sectors)
        
        // Get the regulation
        OPTIONAL MATCH (r)-[:BELONGS_TO]->(reg:Regulation)
        
        RETURN e, r, reg,
               [j IN r.jurisdictions WHERE j IN e.jurisdictions] as matching_jurisdictions,
               [s IN r.sectors WHERE s IN e.sectors] as matching_sectors
        """

        results = await Neo4jClient.run_query(
            query,
            {"entity_id": entity_id, "req_id": requirement_id},
        )

        if not results:
            return None

        r = results[0]
        entity = r.get("e", {})
        requirement = r.get("r", {})
        regulation = r.get("reg", {})

        # Build path
        nodes = [
            PathNode(
                id=entity.get("id", ""),
                label="Entity",
                name=entity.get("name", entity.get("id", "")),
                properties=dict(entity),
            ),
        ]

        # Add jurisdiction/sector nodes if they exist
        matching_j = r.get("matching_jurisdictions", [])
        if matching_j:
            nodes.append(
                PathNode(
                    id=matching_j[0],
                    label="Jurisdiction",
                    name=matching_j[0],
                    properties={"jurisdictions": matching_j},
                )
            )

        # Add regulation node
        if regulation:
            nodes.append(
                PathNode(
                    id=regulation.get("id", ""),
                    label="Regulation",
                    name=regulation.get("name", regulation.get("id", "")),
                    properties=dict(regulation),
                )
            )

        # Add requirement node
        nodes.append(
            PathNode(
                id=requirement.get("id", ""),
                label="Requirement",
                name=requirement.get("article_ref", requirement.get("id", "")),
                properties=dict(requirement),
            )
        )

        # Build edges
        edges = []
        for i in range(len(nodes) - 1):
            edges.append(
                PathEdge(
                    type="APPLIES_TO" if i == 0 else "BELONGS_TO",
                    from_id=nodes[i].id,
                    to_id=nodes[i + 1].id,
                )
            )

        return CompliancePath(
            nodes=nodes,
            edges=edges,
            length=len(edges),
        )

    async def find_shortest_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 10,
    ) -> CompliancePath | None:
        """
        Find shortest path between any two nodes.

        Args:
            from_id: Source node ID
            to_id: Target node ID
            max_depth: Maximum path length

        Returns:
            Shortest CompliancePath or None
        """
        query = """
        MATCH (start {id: $from_id}), (end {id: $to_id})
        MATCH path = shortestPath((start)-[*1..10]-(end))
        RETURN path
        LIMIT 1
        """

        results = await Neo4jClient.run_query(
            query,
            {"from_id": from_id, "to_id": to_id},
        )

        if not results:
            return None

        # Parse path
        path_data = results[0].get("path", {})
        # Neo4j returns path as a structured object
        # This is a simplified parsing - actual implementation depends on driver

        return CompliancePath(
            nodes=[],  # Would be populated from path_data
            edges=[],
            length=0,
        )

    async def analyze_impact(
        self,
        requirement_id: str,
    ) -> dict[str, Any]:
        """
        Analyze the impact of a requirement change.

        Finds all entities and other requirements affected.

        Args:
            requirement_id: Requirement being changed

        Returns:
            Impact analysis
        """
        # Find affected entities
        entity_query = """
        MATCH (r:Requirement {id: $req_id})
        MATCH (e:Entity)
        WHERE (ANY(j IN r.jurisdictions WHERE j IN e.jurisdictions) OR 'ALL' IN r.jurisdictions)
          AND (ANY(s IN r.sectors WHERE s IN e.sectors) OR 'ALL' IN r.sectors)
        RETURN count(e) as entity_count
        """

        entity_result = await Neo4jClient.run_query(
            entity_query,
            {"req_id": requirement_id},
        )
        entity_count = entity_result[0]["entity_count"] if entity_result else 0

        # Find dependent requirements
        dependents = await self.find_dependents(requirement_id)

        # Find conflicts that might be resolved
        conflicts = await self.find_conflicts(requirement_id)

        return {
            "requirement_id": requirement_id,
            "affected_entities": entity_count,
            "dependent_requirements": len(dependents),
            "dependents": dependents[:10],  # Top 10
            "conflicts": len(conflicts),
            "conflict_details": conflicts[:5],  # Top 5
        }

    async def find_common_ancestors(
        self,
        requirement_ids: list[str],
    ) -> list[dict[str, Any]]:
        """
        Find common ancestor requirements (shared dependencies).

        Useful for finding shared compliance foundations.

        Args:
            requirement_ids: List of requirement IDs

        Returns:
            List of common ancestor requirements
        """
        if len(requirement_ids) < 2:
            return []

        # Build MATCH clauses for each requirement
        match_clauses = []
        for i, req_id in enumerate(requirement_ids):
            match_clauses.append(
                f"MATCH path{i} = (r{i}:Requirement {{id: $req_{i}}})-[:DEPENDS_ON*0..5]->(ancestor)"
            )

        params = {f"req_{i}": req_id for i, req_id in enumerate(requirement_ids)}

        query = f"""
        {" ".join(match_clauses)}
        WITH ancestor, count(ancestor) as paths
        WHERE paths = $total
        RETURN ancestor.id as id,
               ancestor.natural_language as text,
               ancestor.tier as tier
        """

        params["total"] = len(requirement_ids)

        results = await Neo4jClient.run_query(query, params)

        return [
            {
                "id": r["id"],
                "text": r["text"],
                "tier": r["tier"],
            }
            for r in results
        ]
