"""
Audit Trail Routes
==================

API endpoints for blockchain audit trail management.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from shared.blockchain import BlockchainClient
from shared.logging import get_logger


logger = get_logger(__name__)
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class AuditEntry(BaseModel):
    """Audit trail entry."""

    entry_id: str
    entity_id: str
    action: str
    timestamp: datetime
    data_hash: str
    proof_hash: str | None = None
    transaction_hash: str | None = None
    block_number: int | None = None


class CreateAuditRequest(BaseModel):
    """Request to create an audit entry."""

    entity_id: str = Field(..., description="Entity identifier")
    action: str = Field(..., description="Action being audited")
    data: dict[str, Any] = Field(..., description="Data to be hashed and recorded")
    proof_id: str | None = Field(None, description="Associated proof ID")


class CreateAuditResponse(BaseModel):
    """Response from creating an audit entry."""

    success: bool
    entry_id: str
    data_hash: str
    transaction_hash: str | None = None
    message: str


class AuditTrailResponse(BaseModel):
    """Response containing audit trail."""

    entity_id: str
    entries: list[AuditEntry]
    total: int
    has_more: bool


class VerifyAuditRequest(BaseModel):
    """Request to verify an audit entry."""

    entry_id: str
    data: dict[str, Any]


class VerifyAuditResponse(BaseModel):
    """Response from audit verification."""

    valid: bool
    entry_id: str
    stored_hash: str
    computed_hash: str
    on_chain: bool
    message: str


# ============================================================================
# Audit Trail Endpoints
# ============================================================================


@router.post("/", response_model=CreateAuditResponse)
async def create_audit_entry(request: CreateAuditRequest) -> CreateAuditResponse:
    """
    Create a new audit trail entry.

    Records an action in the audit trail with a cryptographic hash of the
    associated data. In production mode, this is also recorded on-chain.

    Args:
        request: Audit entry creation request

    Returns:
        CreateAuditResponse with entry details
    """
    logger.info(
        "creating_audit_entry",
        entity_id=request.entity_id,
        action=request.action,
    )

    import hashlib
    import json
    import uuid

    # Compute data hash
    data_json = json.dumps(request.data, sort_keys=True)
    data_hash = hashlib.sha256(data_json.encode()).hexdigest()

    entry_id = str(uuid.uuid4())

    # Record on blockchain if not in mock mode
    transaction_hash = None
    try:
        client = BlockchainClient.get_client()
        if client.is_live:
            tx_result = await client.record_audit(
                entity_id=request.entity_id,
                action=request.action,
                data_hash=data_hash,
            )
            transaction_hash = tx_result.get("transaction_hash")
    except Exception as e:
        logger.warning("blockchain_record_failed", error=str(e))

    logger.info(
        "audit_entry_created",
        entry_id=entry_id,
        data_hash=data_hash,
        on_chain=transaction_hash is not None,
    )

    return CreateAuditResponse(
        success=True,
        entry_id=entry_id,
        data_hash=data_hash,
        transaction_hash=transaction_hash,
        message="Audit entry created successfully",
    )


@router.get("/entity/{entity_id}", response_model=AuditTrailResponse)
async def get_entity_audit_trail(
    entity_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AuditTrailResponse:
    """
    Get audit trail for an entity.

    Retrieves all audit entries associated with a specific entity,
    ordered by timestamp (most recent first).

    Args:
        entity_id: Entity identifier
        limit: Maximum entries to return
        offset: Number of entries to skip

    Returns:
        AuditTrailResponse with list of audit entries
    """
    logger.info(
        "get_audit_trail",
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )

    # TODO: Implement database query for audit entries
    # For now, return empty trail
    return AuditTrailResponse(
        entity_id=entity_id,
        entries=[],
        total=0,
        has_more=False,
    )


@router.get("/{entry_id}", response_model=AuditEntry)
async def get_audit_entry(entry_id: str) -> AuditEntry:
    """
    Get a specific audit entry.

    Args:
        entry_id: Audit entry identifier

    Returns:
        AuditEntry details
    """
    logger.info("get_audit_entry", entry_id=entry_id)

    # TODO: Implement database lookup
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Audit entry {entry_id} not found",
    )


@router.post("/verify", response_model=VerifyAuditResponse)
async def verify_audit_entry(request: VerifyAuditRequest) -> VerifyAuditResponse:
    """
    Verify an audit entry against provided data.

    Computes the hash of the provided data and compares it against
    the stored hash in the audit entry.

    Args:
        request: Verification request with entry_id and data

    Returns:
        VerifyAuditResponse indicating if data matches
    """
    import hashlib
    import json

    logger.info("verify_audit_entry", entry_id=request.entry_id)

    # Compute hash of provided data
    data_json = json.dumps(request.data, sort_keys=True)
    computed_hash = hashlib.sha256(data_json.encode()).hexdigest()

    # TODO: Look up stored hash from database
    # For now, return verification pending
    return VerifyAuditResponse(
        valid=False,
        entry_id=request.entry_id,
        stored_hash="",
        computed_hash=computed_hash,
        on_chain=False,
        message="Audit entry not found",
    )


@router.get("/blockchain/{transaction_hash}")
async def get_blockchain_record(transaction_hash: str) -> dict[str, Any]:
    """
    Get audit record from blockchain.

    Retrieves the on-chain record associated with a transaction hash.

    Args:
        transaction_hash: Blockchain transaction hash

    Returns:
        On-chain record details
    """
    logger.info("get_blockchain_record", tx_hash=transaction_hash)

    try:
        client = BlockchainClient.get_client()
        record = await client.get_transaction(transaction_hash)
        return record
    except Exception as e:
        logger.error("blockchain_lookup_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_hash} not found",
        ) from e
