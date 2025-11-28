// ==============================================================================
// CIVIUM Neo4j Initialization Script
// ==============================================================================
// This script sets up the initial graph schema for the Compliance Graph Engine.
// Run manually after container startup: 
//   docker exec -i civium-neo4j cypher-shell -u neo4j -p civium_graph_password < infrastructure/docker/neo4j/init.cypher
// ==============================================================================

// ==============================================================================
// Constraints: Ensure uniqueness and existence
// ==============================================================================

// Requirement nodes
CREATE CONSTRAINT requirement_id IF NOT EXISTS
FOR (r:Requirement) REQUIRE r.id IS UNIQUE;

// Entity nodes
CREATE CONSTRAINT entity_id IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

// Regulation nodes
CREATE CONSTRAINT regulation_id IF NOT EXISTS
FOR (reg:Regulation) REQUIRE reg.id IS UNIQUE;

// Jurisdiction nodes
CREATE CONSTRAINT jurisdiction_code IF NOT EXISTS
FOR (j:Jurisdiction) REQUIRE j.code IS UNIQUE;

// Sector nodes
CREATE CONSTRAINT sector_code IF NOT EXISTS
FOR (s:Sector) REQUIRE s.code IS UNIQUE;

// ComplianceState nodes
CREATE CONSTRAINT compliance_state_id IF NOT EXISTS
FOR (cs:ComplianceState) REQUIRE cs.id IS UNIQUE;

// ==============================================================================
// Indexes: Optimize query performance
// ==============================================================================

// Requirement indexes
CREATE INDEX requirement_tier IF NOT EXISTS
FOR (r:Requirement) ON (r.tier);

CREATE INDEX requirement_effective_date IF NOT EXISTS
FOR (r:Requirement) ON (r.effective_date);

CREATE INDEX requirement_sunset_date IF NOT EXISTS
FOR (r:Requirement) ON (r.sunset_date);

// Entity indexes
CREATE INDEX entity_type IF NOT EXISTS
FOR (e:Entity) ON (e.type);

CREATE INDEX entity_compliance_score IF NOT EXISTS
FOR (e:Entity) ON (e.compliance_score);

CREATE INDEX entity_risk_tier IF NOT EXISTS
FOR (e:Entity) ON (e.risk_tier);

// ComplianceState indexes
CREATE INDEX compliance_state_status IF NOT EXISTS
FOR (cs:ComplianceState) ON (cs.status);

CREATE INDEX compliance_state_timestamp IF NOT EXISTS
FOR (cs:ComplianceState) ON (cs.verification_timestamp);

// Full-text search indexes
CREATE FULLTEXT INDEX requirement_text IF NOT EXISTS
FOR (r:Requirement) ON EACH [r.natural_language, r.summary];

CREATE FULLTEXT INDEX entity_name IF NOT EXISTS
FOR (e:Entity) ON EACH [e.name];

// ==============================================================================
// Seed Data: Governance Layers (from Seven-Layer Stack)
// ==============================================================================

// Create Governance Layer nodes
MERGE (l1:GovernanceLayer {level: 1, name: "Planetary Boundaries", description: "Climate, biodiversity, freshwater hard limits"})
MERGE (l2:GovernanceLayer {level: 2, name: "Universal Principles", description: "Human rights, labor standards, anti-corruption"})
MERGE (l3:GovernanceLayer {level: 3, name: "Sectoral Regimes", description: "Finance, health, trade standards"})
MERGE (l4:GovernanceLayer {level: 4, name: "Regional Harmonization", description: "EU, ASEAN, GCC frameworks"})
MERGE (l5:GovernanceLayer {level: 5, name: "National Implementation", description: "Domestic legislation"})
MERGE (l6:GovernanceLayer {level: 6, name: "Organizational Compliance", description: "Internal controls, audits"})
MERGE (l7:GovernanceLayer {level: 7, name: "Individual Behavior", description: "Professional licensing, personal liability"});

// Create layer hierarchy
MATCH (l1:GovernanceLayer {level: 1})
MATCH (l2:GovernanceLayer {level: 2})
MERGE (l1)-[:CONSTRAINS]->(l2);

MATCH (l2:GovernanceLayer {level: 2})
MATCH (l3:GovernanceLayer {level: 3})
MERGE (l2)-[:CONSTRAINS]->(l3);

MATCH (l3:GovernanceLayer {level: 3})
MATCH (l4:GovernanceLayer {level: 4})
MERGE (l3)-[:CONSTRAINS]->(l4);

MATCH (l4:GovernanceLayer {level: 4})
MATCH (l5:GovernanceLayer {level: 5})
MERGE (l4)-[:CONSTRAINS]->(l5);

MATCH (l5:GovernanceLayer {level: 5})
MATCH (l6:GovernanceLayer {level: 6})
MERGE (l5)-[:CONSTRAINS]->(l6);

MATCH (l6:GovernanceLayer {level: 6})
MATCH (l7:GovernanceLayer {level: 7})
MERGE (l6)-[:CONSTRAINS]->(l7);

// ==============================================================================
// Seed Data: Major Jurisdictions
// ==============================================================================

MERGE (us:Jurisdiction {code: "US", name: "United States", type: "country", region: "North America"})
MERGE (eu:Jurisdiction {code: "EU", name: "European Union", type: "supranational", region: "Europe"})
MERGE (uk:Jurisdiction {code: "UK", name: "United Kingdom", type: "country", region: "Europe"})
MERGE (sg:Jurisdiction {code: "SG", name: "Singapore", type: "country", region: "Asia-Pacific"})
MERGE (jp:Jurisdiction {code: "JP", name: "Japan", type: "country", region: "Asia-Pacific"})
MERGE (au:Jurisdiction {code: "AU", name: "Australia", type: "country", region: "Asia-Pacific"})
MERGE (ca:Jurisdiction {code: "CA", name: "Canada", type: "country", region: "North America"})
MERGE (ch:Jurisdiction {code: "CH", name: "Switzerland", type: "country", region: "Europe"})
MERGE (de:Jurisdiction {code: "DE", name: "Germany", type: "country", region: "Europe"})
MERGE (fr:Jurisdiction {code: "FR", name: "France", type: "country", region: "Europe"});

// EU membership relationships
MATCH (eu:Jurisdiction {code: "EU"})
MATCH (de:Jurisdiction {code: "DE"})
MATCH (fr:Jurisdiction {code: "FR"})
MERGE (de)-[:MEMBER_OF]->(eu)
MERGE (fr)-[:MEMBER_OF]->(eu);

// ==============================================================================
// Seed Data: Key Sectors
// ==============================================================================

MERGE (fin:Sector {code: "FINANCE", name: "Financial Services", description: "Banking, insurance, investment"})
MERGE (health:Sector {code: "HEALTH", name: "Healthcare", description: "Medical, pharmaceutical, biotech"})
MERGE (tech:Sector {code: "TECH", name: "Technology", description: "Software, hardware, telecommunications"})
MERGE (energy:Sector {code: "ENERGY", name: "Energy", description: "Oil, gas, renewables, utilities"})
MERGE (mfg:Sector {code: "MANUFACTURING", name: "Manufacturing", description: "Industrial production"})
MERGE (retail:Sector {code: "RETAIL", name: "Retail & Consumer", description: "Consumer goods and services"})
MERGE (transport:Sector {code: "TRANSPORT", name: "Transportation", description: "Aviation, shipping, logistics"});

// ==============================================================================
// Seed Data: Example Regulation (GDPR)
// ==============================================================================

MERGE (gdpr:Regulation {
    id: "REG-GDPR",
    name: "General Data Protection Regulation",
    short_name: "GDPR",
    effective_date: date("2018-05-25"),
    governance_layer: 4,
    regulation_type: "data_protection",
    version: "2016/679"
})
WITH gdpr
MATCH (eu:Jurisdiction {code: "EU"})
MERGE (gdpr)-[:APPLIES_IN]->(eu);

// GDPR Article 6 - Lawfulness of processing
MERGE (req1:Requirement {
    id: "REQ-GDPR-6-1-a",
    regulation_id: "REG-GDPR",
    article: "Article 6(1)(a)",
    tier: "basic",
    natural_language: "Processing shall be lawful only if and to the extent that the data subject has given consent to the processing of his or her personal data for one or more specific purposes.",
    formal_logic: "lawful(processing) <- consent_given(data_subject, processing.purposes)",
    verification_method: "cryptographic_proof",
    penalty_max: 20000000,
    penalty_formula: "MAX(20000000, 0.04 * global_annual_turnover)",
    effective_date: date("2018-05-25"),
    created_at: datetime(),
    updated_at: datetime()
})
WITH req1
MATCH (gdpr:Regulation {id: "REG-GDPR"})
MERGE (req1)-[:PART_OF]->(gdpr);

// Apply GDPR to Tech sector
MATCH (req1:Requirement {id: "REQ-GDPR-6-1-a"})
MATCH (tech:Sector {code: "TECH"})
MERGE (req1)-[:APPLIES_TO_SECTOR]->(tech);

// ==============================================================================
// Completion
// ==============================================================================

RETURN "CIVIUM Neo4j initialization completed successfully." AS status;

