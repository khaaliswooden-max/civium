"""
Graph Ingestion Routes
======================

API endpoints for ingesting data into the compliance graph.

Version: 0.1.0
"""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from shared.auth import get_current_user, User
from shared.logging import get_logger

from services.compliance_graph.ingestion.rml_ingester import (
    RMLIngester,
    IngestionOptions,
    IngestionResult,
)
from services.compliance_graph.ingestion.batch_ingester import (
    BatchIngester,
    BatchResult,
    sync_regulations_to_graph,
    clear_graph,
)
from services.compliance_graph.schema.constraints import apply_schema, drop_schema, get_schema_info

logger = get_logger(__name__)

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================


class IngestRMLRequest(BaseModel):
    """Request to ingest an RML document."""

    rml_document: dict[str, Any] = Field(..., description="RML document to ingest")
    options: IngestionOptions | None = Field(default=None, description="Ingestion options")


class IngestRMLResponse(BaseModel):
    """Response from RML ingestion."""

    success: bool
    regulations_created: int
    requirements_created: int
    relationships_created: int
    errors: list[dict[str, Any]]
    duration_seconds: float


class SyncRequest(BaseModel):
    """Request to sync regulations to graph."""

    regulation_ids: list[str] | None = Field(
        default=None,
        description="Specific regulation IDs to sync (null = all)",
    )


class SyncResponse(BaseModel):
    """Response from sync operation."""

    success: bool
    documents_processed: int
    documents_succeeded: int
    documents_failed: int
    total_requirements: int
    duration_seconds: float


class SchemaResponse(BaseModel):
    """Response with schema information."""

    constraints_applied: int
    indexes_applied: int
    errors: list[dict[str, Any]]


# =============================================================================
# Ingestion Endpoints
# =============================================================================


@router.post("/rml", response_model=IngestRMLResponse)
async def ingest_rml_document(
    request: IngestRMLRequest,
    current_user: User = Depends(get_current_user),
) -> IngestRMLResponse:
    """
    Ingest a single RML document into the graph.

    Creates:
    - Regulation node
    - Requirement nodes
    - Jurisdiction nodes
    - Sector nodes
    - All relationships (BELONGS_TO, APPLIES_TO, etc.)

    Requires authentication.
    """
    options = request.options or IngestionOptions()
    ingester = RMLIngester(options)

    try:
        result = await ingester.ingest(request.rml_document)

        logger.info(
            "rml_ingested_via_api",
            regulation_id=request.rml_document.get("id"),
            requirements=result.requirements_created,
            user_id=current_user.id,
        )

        return IngestRMLResponse(
            success=result.success,
            regulations_created=result.regulations_created,
            requirements_created=result.requirements_created,
            relationships_created=result.relationships_created,
            errors=result.errors,
            duration_seconds=result.duration_seconds,
        )

    except Exception as e:
        logger.error("rml_ingestion_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.post("/sync", response_model=SyncResponse)
async def sync_to_graph(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> SyncResponse:
    """
    Sync regulations from MongoDB to Neo4j graph.

    If regulation_ids is provided, syncs only those regulations.
    Otherwise, syncs all regulations that have RML documents.

    Requires authentication.
    """
    try:
        result = await sync_regulations_to_graph(request.regulation_ids)

        logger.info(
            "graph_sync_complete",
            documents=result.documents_processed,
            requirements=result.total_requirements,
            user_id=current_user.id,
        )

        return SyncResponse(
            success=result.documents_succeeded == result.documents_processed,
            documents_processed=result.documents_processed,
            documents_succeeded=result.documents_succeeded,
            documents_failed=result.documents_failed,
            total_requirements=result.total_requirements,
            duration_seconds=result.duration_seconds,
        )

    except Exception as e:
        logger.error("graph_sync_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}",
        )


# =============================================================================
# Schema Management Endpoints
# =============================================================================


@router.post("/schema/apply", response_model=SchemaResponse)
async def apply_graph_schema(
    current_user: User = Depends(get_current_user),
) -> SchemaResponse:
    """
    Apply schema constraints and indexes to Neo4j.

    Creates:
    - Uniqueness constraints on all node IDs
    - Indexes for common query patterns
    - Full-text search indexes

    Requires authentication.
    """
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for schema operations",
        )

    try:
        result = await apply_schema()

        logger.info(
            "schema_applied_via_api",
            constraints=result["constraints_applied"],
            indexes=result["indexes_applied"],
            user_id=current_user.id,
        )

        return SchemaResponse(
            constraints_applied=result["constraints_applied"],
            indexes_applied=result["indexes_applied"],
            errors=result.get("constraints_failed", []) + result.get("indexes_failed", []),
        )

    except Exception as e:
        logger.error("schema_apply_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema application failed: {str(e)}",
        )


@router.get("/schema")
async def get_current_schema(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get current schema information from Neo4j.

    Returns constraints and indexes currently in the database.

    Requires authentication.
    """
    try:
        return await get_schema_info()
    except Exception as e:
        logger.error("schema_info_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get schema info: {str(e)}",
        )


@router.delete("/schema")
async def drop_graph_schema(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Drop all schema constraints and indexes.

    WARNING: This is a destructive operation.

    Requires admin role.
    """
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for schema operations",
        )

    try:
        result = await drop_schema()

        logger.warning(
            "schema_dropped_via_api",
            user_id=current_user.id,
        )

        return result

    except Exception as e:
        logger.error("schema_drop_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema drop failed: {str(e)}",
        )


@router.delete("/data")
async def clear_graph_data(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Clear all data from the graph.

    WARNING: This is a destructive operation that removes all nodes and relationships.

    Requires admin role.
    """
    if "admin" not in current_user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for data operations",
        )

    try:
        result = await clear_graph()

        logger.warning(
            "graph_cleared_via_api",
            user_id=current_user.id,
        )

        return result

    except Exception as e:
        logger.error("graph_clear_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph clear failed: {str(e)}",
        )

