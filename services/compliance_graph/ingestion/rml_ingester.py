"""
RML to Neo4j Ingester
=====================

Converts RML (Regulatory Markup Language) documents into Neo4j graph nodes
and relationships.

Version: 0.1.0
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from services.compliance_graph.schema.nodes import (
    ComplianceTier,
    GovernanceLayer,
    JurisdictionNode,
    RegulationNode,
    RequirementNode,
    SectorNode,
    VerificationMethod,
)
from services.compliance_graph.schema.relationships import (
    AppliesTo,
    BelongsTo,
    ConflictsWith,
    DependsOn,
)
from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger


logger = get_logger(__name__)


@dataclass
class IngestionOptions:
    """Options for RML ingestion."""

    # What to create
    create_regulations: bool = True
    create_requirements: bool = True
    create_jurisdictions: bool = True
    create_sectors: bool = True

    # Relationships
    create_belongs_to: bool = True
    create_applies_to: bool = True
    create_dependencies: bool = True
    create_conflicts: bool = True

    # Update behavior
    upsert: bool = True  # Update existing nodes
    skip_existing: bool = False  # Skip if already exists

    # Batch settings
    batch_size: int = 100


@dataclass
class IngestionResult:
    """Result of RML ingestion."""

    # Counts
    regulations_created: int = 0
    regulations_updated: int = 0
    requirements_created: int = 0
    requirements_updated: int = 0
    jurisdictions_created: int = 0
    sectors_created: int = 0
    relationships_created: int = 0

    # Errors
    errors: list[dict[str, Any]] = field(default_factory=list)

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """Whether ingestion completed without errors."""
        return len(self.errors) == 0

    @property
    def total_nodes_created(self) -> int:
        """Total nodes created."""
        return (
            self.regulations_created
            + self.requirements_created
            + self.jurisdictions_created
            + self.sectors_created
        )


class RMLIngester:
    """
    Ingests RML documents into Neo4j.

    Converts RML structure to graph nodes and relationships:
    - Regulation -> Regulation node
    - Requirement -> Requirement node with BELONGS_TO relationship
    - Jurisdictions -> Jurisdiction nodes with APPLIES_TO relationships
    - Sectors -> Sector nodes with APPLIES_TO relationships
    - Dependencies -> DEPENDS_ON relationships
    - Conflicts -> CONFLICTS_WITH relationships
    """

    def __init__(self, options: IngestionOptions | None = None) -> None:
        """
        Initialize the ingester.

        Args:
            options: Ingestion options
        """
        self.options = options or IngestionOptions()

    async def ingest(self, rml_document: dict[str, Any]) -> IngestionResult:
        """
        Ingest an RML document into Neo4j.

        Args:
            rml_document: RML document as dictionary

        Returns:
            IngestionResult with counts and any errors
        """
        result = IngestionResult()

        try:
            # Step 1: Create Regulation node
            if self.options.create_regulations:
                reg_result = await self._create_regulation(rml_document)
                if reg_result.get("created"):
                    result.regulations_created += 1
                elif reg_result.get("updated"):
                    result.regulations_updated += 1

            # Step 2: Create Jurisdiction nodes
            if self.options.create_jurisdictions:
                jurisdictions = self._extract_jurisdictions(rml_document)
                for jurisdiction in jurisdictions:
                    try:
                        await self._create_jurisdiction(jurisdiction)
                        result.jurisdictions_created += 1
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            result.errors.append(
                                {
                                    "type": "jurisdiction",
                                    "id": jurisdiction,
                                    "error": str(e),
                                }
                            )

            # Step 3: Create Sector nodes
            if self.options.create_sectors:
                sectors = self._extract_sectors(rml_document)
                for sector in sectors:
                    try:
                        await self._create_sector(sector)
                        result.sectors_created += 1
                    except Exception as e:
                        if "already exists" not in str(e).lower():
                            result.errors.append(
                                {
                                    "type": "sector",
                                    "id": sector,
                                    "error": str(e),
                                }
                            )

            # Step 4: Create Requirement nodes
            if self.options.create_requirements:
                requirements = rml_document.get("requirements", [])

                for req in requirements:
                    try:
                        req_result = await self._create_requirement(
                            req,
                            rml_document.get("id", ""),
                        )
                        if req_result.get("created"):
                            result.requirements_created += 1
                        elif req_result.get("updated"):
                            result.requirements_updated += 1

                        # Create BELONGS_TO relationship
                        if self.options.create_belongs_to:
                            await self._create_belongs_to(
                                req.get("id", ""),
                                rml_document.get("id", ""),
                                req.get("article_ref"),
                            )
                            result.relationships_created += 1

                        # Create APPLIES_TO relationships
                        if self.options.create_applies_to:
                            rel_count = await self._create_applies_to_relationships(req)
                            result.relationships_created += rel_count

                        # Create dependency relationships
                        if self.options.create_dependencies:
                            rel_count = await self._create_dependency_relationships(req)
                            result.relationships_created += rel_count

                    except Exception as e:
                        result.errors.append(
                            {
                                "type": "requirement",
                                "id": req.get("id", "unknown"),
                                "error": str(e),
                            }
                        )

            result.completed_at = datetime.now(UTC)
            result.duration_seconds = (result.completed_at - result.started_at).total_seconds()

            logger.info(
                "rml_ingestion_complete",
                regulation_id=rml_document.get("id"),
                requirements=result.requirements_created,
                relationships=result.relationships_created,
                errors=len(result.errors),
                duration=f"{result.duration_seconds:.2f}s",
            )

        except Exception as e:
            result.errors.append(
                {
                    "type": "general",
                    "error": str(e),
                }
            )
            logger.error(
                "rml_ingestion_failed",
                regulation_id=rml_document.get("id"),
                error=str(e),
            )

        return result

    async def _create_regulation(self, rml: dict[str, Any]) -> dict[str, Any]:
        """Create or update Regulation node."""
        regulation = RegulationNode(
            id=rml.get("id", ""),
            name=rml.get("name", ""),
            short_name=rml.get("short_name"),
            jurisdiction=rml.get("jurisdiction", ""),
            jurisdictions=rml.get("jurisdictions", []),
            sectors=rml.get("sectors", []),
            governance_layer=GovernanceLayer(rml.get("governance_layer", 3)),
            source_url=rml.get("source", {}).get("url"),
            source_hash=rml.get("source", {}).get("hash"),
            requirement_count=len(rml.get("requirements", [])),
        )

        # Parse dates if present
        if rml.get("effective_date"):
            try:
                from datetime import date

                regulation.effective_date = date.fromisoformat(rml["effective_date"])
            except (ValueError, TypeError):
                pass

        props = regulation.to_neo4j_properties()
        props["updated_at"] = datetime.now(UTC).isoformat()

        if self.options.upsert:
            query = """
            MERGE (r:Regulation {id: $id})
            ON CREATE SET r = $props, r.created_at = datetime()
            ON MATCH SET r += $props
            RETURN r, 
                   CASE WHEN r.created_at = datetime() THEN true ELSE false END as created
            """
        else:
            query = """
            CREATE (r:Regulation)
            SET r = $props, r.created_at = datetime()
            RETURN r, true as created
            """

        results = await Neo4jClient.run_query(
            query,
            {"id": regulation.id, "props": props},
        )

        return {
            "created": results[0].get("created", False) if results else False,
            "updated": not results[0].get("created", True) if results else False,
        }

    async def _create_requirement(
        self,
        req: dict[str, Any],
        regulation_id: str,
    ) -> dict[str, Any]:
        """Create or update Requirement node."""
        # Map tier
        tier_str = req.get("tier", "basic")
        try:
            tier = ComplianceTier(tier_str)
        except ValueError:
            tier = ComplianceTier.BASIC

        # Map verification method
        vm_str = req.get("verification_method", "self_attestation")
        try:
            verification_method = VerificationMethod(vm_str)
        except ValueError:
            verification_method = VerificationMethod.SELF_ATTESTATION

        requirement = RequirementNode(
            id=req.get("id", ""),
            regulation_id=regulation_id,
            article_ref=req.get("article_ref", ""),
            natural_language=req.get("text", ""),
            formal_logic=req.get("formal_logic"),
            summary=req.get("summary"),
            tier=tier,
            verification_method=verification_method,
            jurisdictions=req.get("scope", {}).get("jurisdictions", []),
            sectors=req.get("scope", {}).get("sectors", []),
            applies_to_entity_types=req.get("scope", {}).get("entities", []),
            confidence=req.get("metadata", {}).get("confidence", 1.0),
        )

        # Parse enforcement
        enforcement = req.get("enforcement", {})
        if enforcement.get("penalty_monetary_max"):
            requirement.penalty_monetary_max = float(enforcement["penalty_monetary_max"])
        if enforcement.get("penalty_formula"):
            requirement.penalty_formula = enforcement["penalty_formula"]

        # Parse dates
        temporal = req.get("temporal", {})
        if temporal.get("effective_date"):
            try:
                from datetime import date

                requirement.effective_date = date.fromisoformat(temporal["effective_date"])
            except (ValueError, TypeError):
                pass

        props = requirement.to_neo4j_properties()
        props["updated_at"] = datetime.now(UTC).isoformat()

        if self.options.upsert:
            query = """
            MERGE (r:Requirement {id: $id})
            ON CREATE SET r = $props, r.created_at = datetime()
            ON MATCH SET r += $props
            RETURN r,
                   CASE WHEN r.created_at = datetime() THEN true ELSE false END as created
            """
        else:
            query = """
            CREATE (r:Requirement)
            SET r = $props, r.created_at = datetime()
            RETURN r, true as created
            """

        results = await Neo4jClient.run_query(
            query,
            {"id": requirement.id, "props": props},
        )

        return {
            "created": results[0].get("created", False) if results else False,
            "updated": not results[0].get("created", True) if results else False,
        }

    async def _create_jurisdiction(self, jurisdiction_code: str) -> None:
        """Create Jurisdiction node if not exists."""
        # Determine jurisdiction type and name
        jurisdiction_type = "country"
        name = jurisdiction_code

        # Known jurisdiction mappings
        jurisdiction_names = {
            "US": "United States",
            "EU": "European Union",
            "UK": "United Kingdom",
            "CA": "Canada",
            "AU": "Australia",
            "SG": "Singapore",
            "JP": "Japan",
            "CN": "China",
            "DE": "Germany",
            "FR": "France",
        }

        if jurisdiction_code in jurisdiction_names:
            name = jurisdiction_names[jurisdiction_code]

        # Determine governance layer
        governance_layer = GovernanceLayer.NATIONAL
        if jurisdiction_code == "EU":
            governance_layer = GovernanceLayer.REGIONAL

        jurisdiction = JurisdictionNode(
            id=jurisdiction_code,
            name=name,
            jurisdiction_type=jurisdiction_type,
            governance_layer=governance_layer,
            iso_code=jurisdiction_code,
        )

        props = jurisdiction.to_neo4j_properties()

        query = """
        MERGE (j:Jurisdiction {id: $id})
        ON CREATE SET j = $props, j.created_at = datetime()
        RETURN j
        """

        await Neo4jClient.run_query(query, {"id": jurisdiction_code, "props": props})

    async def _create_sector(self, sector_code: str) -> None:
        """Create Sector node if not exists."""
        # Known sector mappings
        sector_names = {
            "FINANCE": "Financial Services",
            "HEALTH": "Healthcare",
            "TECH": "Technology",
            "ENERGY": "Energy",
            "MANUFACTURING": "Manufacturing",
            "RETAIL": "Retail",
            "TRANSPORT": "Transportation",
            "GOVERNMENT": "Government",
            "ALL": "All Sectors",
        }

        name = sector_names.get(sector_code, sector_code)

        sector = SectorNode(
            id=sector_code,
            name=name,
        )

        props = sector.to_neo4j_properties()

        query = """
        MERGE (s:Sector {id: $id})
        ON CREATE SET s = $props, s.created_at = datetime()
        RETURN s
        """

        await Neo4jClient.run_query(query, {"id": sector_code, "props": props})

    async def _create_belongs_to(
        self,
        requirement_id: str,
        regulation_id: str,
        article_ref: str | None,
    ) -> None:
        """Create BELONGS_TO relationship."""
        rel = BelongsTo(
            article_ref=article_ref,
            created_at=datetime.now(UTC),
        )

        query = """
        MATCH (req:Requirement {id: $req_id})
        MATCH (reg:Regulation {id: $reg_id})
        MERGE (req)-[r:BELONGS_TO]->(reg)
        SET r = $props
        RETURN r
        """

        await Neo4jClient.run_query(
            query,
            {
                "req_id": requirement_id,
                "reg_id": regulation_id,
                "props": rel.to_neo4j_properties(),
            },
        )

    async def _create_applies_to_relationships(self, req: dict[str, Any]) -> int:
        """Create APPLIES_TO relationships for jurisdictions and sectors."""
        count = 0
        req_id = req.get("id", "")
        scope = req.get("scope", {})

        rel = AppliesTo(
            mandatory=True,
            created_at=datetime.now(UTC),
        )
        props = rel.to_neo4j_properties()

        # Jurisdiction relationships
        for jurisdiction in scope.get("jurisdictions", []):
            query = """
            MATCH (req:Requirement {id: $req_id})
            MATCH (j:Jurisdiction {id: $j_id})
            MERGE (req)-[r:APPLIES_TO_JURISDICTION]->(j)
            SET r = $props
            RETURN r
            """
            try:
                await Neo4jClient.run_query(
                    query,
                    {"req_id": req_id, "j_id": jurisdiction, "props": props},
                )
                count += 1
            except Exception:
                pass  # Jurisdiction might not exist yet

        # Sector relationships
        for sector in scope.get("sectors", []):
            query = """
            MATCH (req:Requirement {id: $req_id})
            MATCH (s:Sector {id: $s_id})
            MERGE (req)-[r:APPLIES_TO_SECTOR]->(s)
            SET r = $props
            RETURN r
            """
            try:
                await Neo4jClient.run_query(
                    query,
                    {"req_id": req_id, "s_id": sector, "props": props},
                )
                count += 1
            except Exception:
                pass  # Sector might not exist yet

        return count

    async def _create_dependency_relationships(self, req: dict[str, Any]) -> int:
        """Create DEPENDS_ON and CONFLICTS_WITH relationships."""
        count = 0
        req_id = req.get("id", "")
        references = req.get("references", [])

        for ref in references:
            ref_type = ref.get("type", "")
            target = ref.get("target", "")

            if not target:
                continue

            if ref_type == "depends_on":
                rel = DependsOn(
                    dependency_type="prerequisite",
                    mandatory=True,
                    created_at=datetime.now(UTC),
                )
                query = """
                MATCH (req:Requirement {id: $req_id})
                MATCH (target:Requirement {id: $target_id})
                MERGE (req)-[r:DEPENDS_ON]->(target)
                SET r = $props
                RETURN r
                """
            elif ref_type == "conflicts_with":
                rel = ConflictsWith(
                    conflict_type="mutual_exclusion",
                    created_at=datetime.now(UTC),
                )
                query = """
                MATCH (req:Requirement {id: $req_id})
                MATCH (target:Requirement {id: $target_id})
                MERGE (req)-[r:CONFLICTS_WITH]->(target)
                SET r = $props
                RETURN r
                """
            else:
                continue

            try:
                await Neo4jClient.run_query(
                    query,
                    {"req_id": req_id, "target_id": target, "props": rel.to_neo4j_properties()},
                )
                count += 1
            except Exception:
                pass  # Target might not exist yet

        return count

    def _extract_jurisdictions(self, rml: dict[str, Any]) -> list[str]:
        """Extract all unique jurisdictions from RML document."""
        jurisdictions = set()

        # From document level
        if rml.get("jurisdiction"):
            jurisdictions.add(rml["jurisdiction"])
        for j in rml.get("jurisdictions", []):
            jurisdictions.add(j)

        # From requirements
        for req in rml.get("requirements", []):
            scope = req.get("scope", {})
            for j in scope.get("jurisdictions", []):
                jurisdictions.add(j)

        return list(jurisdictions)

    def _extract_sectors(self, rml: dict[str, Any]) -> list[str]:
        """Extract all unique sectors from RML document."""
        sectors = set()

        # From document level
        for s in rml.get("sectors", []):
            sectors.add(s)

        # From requirements
        for req in rml.get("requirements", []):
            scope = req.get("scope", {})
            for s in scope.get("sectors", []):
                sectors.add(s)

        return list(sectors)
