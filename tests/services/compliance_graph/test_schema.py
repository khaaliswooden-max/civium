"""
Tests for Compliance Graph Schema
=================================

Tests for node types, relationships, and schema constraints.

Version: 0.1.0
"""

from datetime import date, datetime

import pytest

from services.compliance_graph.schema.nodes import (
    RequirementNode,
    RegulationNode,
    EntityNode,
    ComplianceStateNode,
    JurisdictionNode,
    SectorNode,
    EvidenceNode,
    ComplianceTier,
    VerificationMethod,
    ComplianceStatus,
    EntityType,
    GovernanceLayer,
)
from services.compliance_graph.schema.relationships import (
    RelationshipType,
    BelongsTo,
    AppliesTo,
    HasState,
    Satisfies,
    DependsOn,
    ConflictsWith,
    Supersedes,
    create_relationship_query,
    delete_relationship_query,
)


# =============================================================================
# Node Tests
# =============================================================================


class TestRequirementNode:
    """Tests for RequirementNode."""

    def test_create_basic_requirement(self) -> None:
        """Test creating a basic requirement node."""
        req = RequirementNode(
            id="REQ-US-001",
            regulation_id="REG-US-SEC",
            article_ref="Section 10.1",
            natural_language="Organizations must file quarterly reports.",
        )

        assert req.id == "REQ-US-001"
        assert req.regulation_id == "REG-US-SEC"
        assert req.tier == ComplianceTier.BASIC
        assert req.verification_method == VerificationMethod.SELF_ATTESTATION

    def test_requirement_with_all_fields(self) -> None:
        """Test requirement with all optional fields."""
        req = RequirementNode(
            id="REQ-EU-GDPR-001",
            regulation_id="REG-EU-GDPR",
            article_ref="Article 6(1)(a)",
            natural_language="Processing shall be lawful if consent given.",
            formal_logic="FORALL x: has_consent(x) -> lawful_processing(x)",
            summary="Consent-based lawful processing",
            tier=ComplianceTier.STANDARD,
            verification_method=VerificationMethod.DOCUMENT_REVIEW,
            governance_layer=GovernanceLayer.REGIONAL,
            jurisdictions=["EU"],
            sectors=["ALL"],
            effective_date=date(2018, 5, 25),
            penalty_monetary_max=20000000.0,
            confidence=0.95,
        )

        assert req.tier == ComplianceTier.STANDARD
        assert req.governance_layer == GovernanceLayer.REGIONAL
        assert req.penalty_monetary_max == 20000000.0

    def test_to_neo4j_properties(self) -> None:
        """Test conversion to Neo4j properties."""
        req = RequirementNode(
            id="REQ-001",
            regulation_id="REG-001",
            article_ref="Art. 1",
            natural_language="Test requirement",
            tier=ComplianceTier.ADVANCED,
            jurisdictions=["US", "EU"],
            penalty_monetary_max=1000000.0,
        )

        props = req.to_neo4j_properties()

        assert props["id"] == "REQ-001"
        assert props["tier"] == "advanced"
        assert props["jurisdictions"] == ["US", "EU"]
        assert props["penalty_monetary_max"] == 1000000.0
        assert "natural_language" in props


class TestRegulationNode:
    """Tests for RegulationNode."""

    def test_create_regulation(self) -> None:
        """Test creating a regulation node."""
        reg = RegulationNode(
            id="REG-US-SOX",
            name="Sarbanes-Oxley Act",
            short_name="SOX",
            jurisdiction="US",
            jurisdictions=["US"],
            sectors=["FINANCE"],
            requirement_count=50,
        )

        assert reg.id == "REG-US-SOX"
        assert reg.short_name == "SOX"
        assert reg.requirement_count == 50

    def test_to_neo4j_properties(self) -> None:
        """Test conversion to Neo4j properties."""
        reg = RegulationNode(
            id="REG-EU-GDPR",
            name="General Data Protection Regulation",
            short_name="GDPR",
            jurisdiction="EU",
            source_url="https://eur-lex.europa.eu/...",
            effective_date=date(2018, 5, 25),
        )

        props = reg.to_neo4j_properties()

        assert props["id"] == "REG-EU-GDPR"
        assert props["name"] == "General Data Protection Regulation"
        assert props["short_name"] == "GDPR"
        assert props["effective_date"] == "2018-05-25"


class TestEntityNode:
    """Tests for EntityNode."""

    def test_create_entity(self) -> None:
        """Test creating an entity node."""
        entity = EntityNode(
            id="ENT-001",
            name="Acme Corporation",
            entity_type=EntityType.CORPORATION,
            jurisdiction="US",
            jurisdictions=["US", "EU"],
            sectors=["TECH", "FINANCE"],
            employee_count=5000,
            annual_revenue=1000000000.0,
        )

        assert entity.id == "ENT-001"
        assert entity.entity_type == EntityType.CORPORATION
        assert entity.employee_count == 5000

    def test_entity_types(self) -> None:
        """Test different entity types."""
        for entity_type in EntityType:
            entity = EntityNode(
                id=f"ENT-{entity_type.value}",
                name=f"Test {entity_type.value}",
                entity_type=entity_type,
                jurisdiction="US",
            )
            assert entity.entity_type == entity_type


class TestComplianceStateNode:
    """Tests for ComplianceStateNode."""

    def test_create_compliance_state(self) -> None:
        """Test creating a compliance state."""
        state = ComplianceStateNode(
            id="CS-001",
            entity_id="ENT-001",
            requirement_id="REQ-001",
            status=ComplianceStatus.COMPLIANT,
            confidence=0.95,
            assessed_at=datetime.now(),
            assessor="system",
        )

        assert state.status == ComplianceStatus.COMPLIANT
        assert state.confidence == 0.95

    def test_compliance_statuses(self) -> None:
        """Test all compliance statuses."""
        for status in ComplianceStatus:
            state = ComplianceStateNode(
                id=f"CS-{status.value}",
                entity_id="ENT-001",
                requirement_id="REQ-001",
                status=status,
            )
            assert state.status == status


class TestJurisdictionNode:
    """Tests for JurisdictionNode."""

    def test_create_jurisdiction(self) -> None:
        """Test creating a jurisdiction node."""
        jurisdiction = JurisdictionNode(
            id="US",
            name="United States",
            jurisdiction_type="country",
            governance_layer=GovernanceLayer.NATIONAL,
            iso_code="US",
        )

        assert jurisdiction.id == "US"
        assert jurisdiction.governance_layer == GovernanceLayer.NATIONAL


class TestSectorNode:
    """Tests for SectorNode."""

    def test_create_sector(self) -> None:
        """Test creating a sector node."""
        sector = SectorNode(
            id="FINANCE",
            name="Financial Services",
            naics_code="52",
            regulation_count=100,
            requirement_count=500,
        )

        assert sector.id == "FINANCE"
        assert sector.regulation_count == 100


# =============================================================================
# Relationship Tests
# =============================================================================


class TestRelationshipTypes:
    """Tests for relationship types."""

    def test_relationship_types_exist(self) -> None:
        """Test all relationship types are defined."""
        expected_types = [
            "BELONGS_TO",
            "DEPENDS_ON",
            "CONFLICTS_WITH",
            "SUPERSEDES",
            "APPLIES_TO_JURISDICTION",
            "APPLIES_TO_SECTOR",
            "HAS_STATE",
            "SATISFIES",
        ]

        for rel_type in expected_types:
            assert hasattr(RelationshipType, rel_type)


class TestBelongsTo:
    """Tests for BelongsTo relationship."""

    def test_create_belongs_to(self) -> None:
        """Test creating BelongsTo relationship."""
        rel = BelongsTo(
            article_ref="Article 6(1)",
            section_number="6.1",
        )

        props = rel.to_neo4j_properties()

        assert props["article_ref"] == "Article 6(1)"
        assert props["section_number"] == "6.1"


class TestAppliesTo:
    """Tests for AppliesTo relationship."""

    def test_create_applies_to(self) -> None:
        """Test creating AppliesTo relationship."""
        rel = AppliesTo(
            condition="employee_count > 250",
            threshold="large enterprise",
            mandatory=True,
        )

        props = rel.to_neo4j_properties()

        assert props["mandatory"] is True
        assert props["condition"] == "employee_count > 250"


class TestDependsOn:
    """Tests for DependsOn relationship."""

    def test_create_depends_on(self) -> None:
        """Test creating DependsOn relationship."""
        rel = DependsOn(
            dependency_type="prerequisite",
            mandatory=True,
        )

        props = rel.to_neo4j_properties()

        assert props["dependency_type"] == "prerequisite"
        assert props["mandatory"] is True


class TestConflictsWith:
    """Tests for ConflictsWith relationship."""

    def test_create_conflicts_with(self) -> None:
        """Test creating ConflictsWith relationship."""
        rel = ConflictsWith(
            conflict_type="mutual_exclusion",
            resolution="Requirement A takes precedence",
            priority_override="REQ-001",
        )

        props = rel.to_neo4j_properties()

        assert props["conflict_type"] == "mutual_exclusion"
        assert props["resolution"] == "Requirement A takes precedence"


class TestRelationshipQueries:
    """Tests for relationship query generators."""

    def test_create_relationship_query(self) -> None:
        """Test relationship creation query generation."""
        query = create_relationship_query(
            RelationshipType.BELONGS_TO,
            "Requirement",
            "Regulation",
        )

        assert "MATCH (a:Requirement" in query
        assert "MATCH (b:Regulation" in query
        assert "MERGE (a)-[r:BELONGS_TO]->(b)" in query

    def test_delete_relationship_query(self) -> None:
        """Test relationship deletion query generation."""
        query = delete_relationship_query(
            RelationshipType.DEPENDS_ON,
            "Requirement",
            "Requirement",
        )

        assert "MATCH (a:Requirement" in query
        assert "-[r:DEPENDS_ON]->" in query
        assert "DELETE r" in query


# =============================================================================
# Governance Layer Tests
# =============================================================================


class TestGovernanceLayers:
    """Tests for the seven governance layers."""

    def test_governance_layer_values(self) -> None:
        """Test governance layer values match Civium spec."""
        assert GovernanceLayer.INDIVIDUAL.value == 1
        assert GovernanceLayer.ORGANIZATIONAL.value == 2
        assert GovernanceLayer.NATIONAL.value == 3
        assert GovernanceLayer.REGIONAL.value == 4
        assert GovernanceLayer.SECTORAL.value == 5
        assert GovernanceLayer.UNIVERSAL.value == 6
        assert GovernanceLayer.PLANETARY.value == 7

    def test_all_layers_defined(self) -> None:
        """Test all seven layers are defined."""
        assert len(GovernanceLayer) == 7

