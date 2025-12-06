"""
Graph Schema Constraints and Indexes
====================================

Neo4j constraints and indexes for the Compliance Graph.

Version: 0.1.0
"""

from typing import Any

from shared.database.neo4j import Neo4jClient
from shared.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Schema Constraints
# =============================================================================

SCHEMA_CONSTRAINTS = [
    # Requirement constraints
    {
        "name": "requirement_id_unique",
        "query": "CREATE CONSTRAINT requirement_id_unique IF NOT EXISTS FOR (r:Requirement) REQUIRE r.id IS UNIQUE",
    },
    # Regulation constraints
    {
        "name": "regulation_id_unique",
        "query": "CREATE CONSTRAINT regulation_id_unique IF NOT EXISTS FOR (r:Regulation) REQUIRE r.id IS UNIQUE",
    },
    # Entity constraints
    {
        "name": "entity_id_unique",
        "query": "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    },
    # ComplianceState constraints
    {
        "name": "compliance_state_id_unique",
        "query": "CREATE CONSTRAINT compliance_state_id_unique IF NOT EXISTS FOR (cs:ComplianceState) REQUIRE cs.id IS UNIQUE",
    },
    # Jurisdiction constraints
    {
        "name": "jurisdiction_id_unique",
        "query": "CREATE CONSTRAINT jurisdiction_id_unique IF NOT EXISTS FOR (j:Jurisdiction) REQUIRE j.id IS UNIQUE",
    },
    # Sector constraints
    {
        "name": "sector_id_unique",
        "query": "CREATE CONSTRAINT sector_id_unique IF NOT EXISTS FOR (s:Sector) REQUIRE s.id IS UNIQUE",
    },
    # Evidence constraints
    {
        "name": "evidence_id_unique",
        "query": "CREATE CONSTRAINT evidence_id_unique IF NOT EXISTS FOR (e:Evidence) REQUIRE e.id IS UNIQUE",
    },
]

# =============================================================================
# Schema Indexes
# =============================================================================

SCHEMA_INDEXES = [
    # Requirement indexes
    {
        "name": "requirement_regulation_id",
        "query": "CREATE INDEX requirement_regulation_id IF NOT EXISTS FOR (r:Requirement) ON (r.regulation_id)",
    },
    {
        "name": "requirement_tier",
        "query": "CREATE INDEX requirement_tier IF NOT EXISTS FOR (r:Requirement) ON (r.tier)",
    },
    {
        "name": "requirement_jurisdiction",
        "query": "CREATE INDEX requirement_jurisdictions IF NOT EXISTS FOR (r:Requirement) ON (r.jurisdictions)",
    },
    {
        "name": "requirement_effective_date",
        "query": "CREATE INDEX requirement_effective_date IF NOT EXISTS FOR (r:Requirement) ON (r.effective_date)",
    },
    {
        "name": "requirement_governance_layer",
        "query": "CREATE INDEX requirement_governance_layer IF NOT EXISTS FOR (r:Requirement) ON (r.governance_layer)",
    },
    # Regulation indexes
    {
        "name": "regulation_jurisdiction",
        "query": "CREATE INDEX regulation_jurisdiction IF NOT EXISTS FOR (r:Regulation) ON (r.jurisdiction)",
    },
    {
        "name": "regulation_name",
        "query": "CREATE INDEX regulation_name IF NOT EXISTS FOR (r:Regulation) ON (r.name)",
    },
    # Entity indexes
    {
        "name": "entity_jurisdiction",
        "query": "CREATE INDEX entity_jurisdiction IF NOT EXISTS FOR (e:Entity) ON (e.jurisdiction)",
    },
    {
        "name": "entity_type",
        "query": "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type)",
    },
    {
        "name": "entity_name",
        "query": "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
    },
    # ComplianceState indexes
    {
        "name": "compliance_state_entity_id",
        "query": "CREATE INDEX compliance_state_entity_id IF NOT EXISTS FOR (cs:ComplianceState) ON (cs.entity_id)",
    },
    {
        "name": "compliance_state_requirement_id",
        "query": "CREATE INDEX compliance_state_requirement_id IF NOT EXISTS FOR (cs:ComplianceState) ON (cs.requirement_id)",
    },
    {
        "name": "compliance_state_status",
        "query": "CREATE INDEX compliance_state_status IF NOT EXISTS FOR (cs:ComplianceState) ON (cs.status)",
    },
    # Jurisdiction indexes
    {
        "name": "jurisdiction_type",
        "query": "CREATE INDEX jurisdiction_type IF NOT EXISTS FOR (j:Jurisdiction) ON (j.jurisdiction_type)",
    },
    # Sector indexes
    {
        "name": "sector_name",
        "query": "CREATE INDEX sector_name IF NOT EXISTS FOR (s:Sector) ON (s.name)",
    },
    # Evidence indexes
    {
        "name": "evidence_entity_id",
        "query": "CREATE INDEX evidence_entity_id IF NOT EXISTS FOR (e:Evidence) ON (e.entity_id)",
    },
    {
        "name": "evidence_verified",
        "query": "CREATE INDEX evidence_verified IF NOT EXISTS FOR (e:Evidence) ON (e.verified)",
    },
    # Full-text indexes for search
    {
        "name": "requirement_text_search",
        "query": """
        CREATE FULLTEXT INDEX requirement_text_search IF NOT EXISTS 
        FOR (r:Requirement) ON EACH [r.natural_language, r.summary]
        """,
    },
    {
        "name": "regulation_text_search",
        "query": """
        CREATE FULLTEXT INDEX regulation_text_search IF NOT EXISTS 
        FOR (r:Regulation) ON EACH [r.name, r.short_name]
        """,
    },
]


# =============================================================================
# Schema Application
# =============================================================================


async def apply_schema() -> dict[str, Any]:
    """
    Apply all schema constraints and indexes to Neo4j.

    Returns:
        Summary of applied schema elements
    """
    results = {
        "constraints_applied": 0,
        "constraints_failed": [],
        "indexes_applied": 0,
        "indexes_failed": [],
    }

    # Apply constraints
    for constraint in SCHEMA_CONSTRAINTS:
        try:
            await Neo4jClient.run_write_query(constraint["query"])
            results["constraints_applied"] += 1
            logger.debug(
                "constraint_applied",
                name=constraint["name"],
            )
        except Exception as e:
            error_msg = str(e)
            # Ignore "already exists" errors
            if "already exists" not in error_msg.lower():
                results["constraints_failed"].append(
                    {
                        "name": constraint["name"],
                        "error": error_msg,
                    }
                )
                logger.warning(
                    "constraint_failed",
                    name=constraint["name"],
                    error=error_msg,
                )

    # Apply indexes
    for index in SCHEMA_INDEXES:
        try:
            await Neo4jClient.run_write_query(index["query"])
            results["indexes_applied"] += 1
            logger.debug(
                "index_applied",
                name=index["name"],
            )
        except Exception as e:
            error_msg = str(e)
            # Ignore "already exists" errors
            if "already exists" not in error_msg.lower():
                results["indexes_failed"].append(
                    {
                        "name": index["name"],
                        "error": error_msg,
                    }
                )
                logger.warning(
                    "index_failed",
                    name=index["name"],
                    error=error_msg,
                )

    logger.info(
        "schema_applied",
        constraints=results["constraints_applied"],
        indexes=results["indexes_applied"],
        errors=len(results["constraints_failed"]) + len(results["indexes_failed"]),
    )

    return results


async def drop_schema() -> dict[str, Any]:
    """
    Drop all schema constraints and indexes.

    WARNING: Use with caution - this removes all constraints and indexes.

    Returns:
        Summary of dropped schema elements
    """
    results = {
        "constraints_dropped": 0,
        "indexes_dropped": 0,
    }

    # Drop constraints
    for constraint in SCHEMA_CONSTRAINTS:
        try:
            drop_query = f"DROP CONSTRAINT {constraint['name']} IF EXISTS"
            await Neo4jClient.run_write_query(drop_query)
            results["constraints_dropped"] += 1
        except Exception as e:
            logger.warning(
                "constraint_drop_failed",
                name=constraint["name"],
                error=str(e),
            )

    # Drop indexes
    for index in SCHEMA_INDEXES:
        try:
            drop_query = f"DROP INDEX {index['name']} IF EXISTS"
            await Neo4jClient.run_write_query(drop_query)
            results["indexes_dropped"] += 1
        except Exception as e:
            logger.warning(
                "index_drop_failed",
                name=index["name"],
                error=str(e),
            )

    logger.info(
        "schema_dropped",
        constraints=results["constraints_dropped"],
        indexes=results["indexes_dropped"],
    )

    return results


async def get_schema_info() -> dict[str, Any]:
    """
    Get current schema information from Neo4j.

    Returns:
        Current constraints and indexes
    """
    # Get constraints
    constraints = await Neo4jClient.run_query("SHOW CONSTRAINTS")

    # Get indexes
    indexes = await Neo4jClient.run_query("SHOW INDEXES")

    return {
        "constraints": constraints,
        "indexes": indexes,
    }
