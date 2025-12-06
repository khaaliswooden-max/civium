"""
Proof Verification Routes
=========================

API endpoints for verifying zero-knowledge proofs.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.logging import get_logger
from shared.zk.models import ZKProof
from shared.zk.verifier import ComplianceVerifier


logger = get_logger(__name__)
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class VerifyProofRequest(BaseModel):
    """Request to verify a ZK proof."""

    proof: dict[str, Any] = Field(..., description="The proof object")
    public_signals: list[str] = Field(..., description="Public signals from proof")
    circuit_name: str = Field(
        ...,
        description="Circuit name: compliance_threshold, range_proof, or tier_membership",
    )


class VerifyProofResponse(BaseModel):
    """Response from proof verification."""

    valid: bool
    circuit_name: str
    verification_time_ms: int
    public_signals: list[str]
    message: str


class BatchVerifyRequest(BaseModel):
    """Request to verify multiple proofs."""

    proofs: list[VerifyProofRequest] = Field(..., min_length=1, max_length=100)


class BatchVerifyResponse(BaseModel):
    """Response from batch verification."""

    total: int
    valid: int
    invalid: int
    results: list[VerifyProofResponse]


# ============================================================================
# Verification Endpoints
# ============================================================================


@router.post("/proof", response_model=VerifyProofResponse)
async def verify_proof(request: VerifyProofRequest) -> VerifyProofResponse:
    """
    Verify a zero-knowledge proof.

    This endpoint verifies that a proof is valid for the given public signals
    and circuit. It does NOT check the proof against blockchain records.

    Args:
        request: Verification request containing proof and public signals

    Returns:
        VerifyProofResponse indicating if the proof is valid
    """
    logger.info(
        "verifying_proof",
        circuit=request.circuit_name,
        num_signals=len(request.public_signals),
    )

    try:
        verifier = ComplianceVerifier()

        # Parse proof
        zk_proof = ZKProof(**request.proof)

        # Verify
        result = await verifier.verify(
            proof=zk_proof,
            public_signals=request.public_signals,
            circuit_name=request.circuit_name,
        )

        return VerifyProofResponse(
            valid=result.valid,
            circuit_name=request.circuit_name,
            verification_time_ms=result.verification_time_ms,
            public_signals=request.public_signals,
            message="Proof is valid" if result.valid else "Proof is invalid",
        )

    except FileNotFoundError as e:
        logger.error("verification_key_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification key not available",
        ) from e
    except Exception as e:
        logger.error("proof_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Proof verification failed",
        ) from e


@router.post("/batch", response_model=BatchVerifyResponse)
async def verify_batch(request: BatchVerifyRequest) -> BatchVerifyResponse:
    """
    Verify multiple proofs in batch.

    This endpoint verifies multiple proofs efficiently. All proofs are
    verified independently.

    Args:
        request: Batch verification request containing multiple proofs

    Returns:
        BatchVerifyResponse with results for each proof
    """
    logger.info("batch_verification", count=len(request.proofs))

    results: list[VerifyProofResponse] = []
    valid_count = 0

    verifier = ComplianceVerifier()

    for proof_request in request.proofs:
        try:
            zk_proof = ZKProof(**proof_request.proof)
            result = await verifier.verify(
                proof=zk_proof,
                public_signals=proof_request.public_signals,
                circuit_name=proof_request.circuit_name,
            )

            if result.valid:
                valid_count += 1

            results.append(
                VerifyProofResponse(
                    valid=result.valid,
                    circuit_name=proof_request.circuit_name,
                    verification_time_ms=result.verification_time_ms,
                    public_signals=proof_request.public_signals,
                    message="Proof is valid" if result.valid else "Proof is invalid",
                )
            )

        except Exception as e:
            logger.warning("batch_proof_failed", error=str(e))
            results.append(
                VerifyProofResponse(
                    valid=False,
                    circuit_name=proof_request.circuit_name,
                    verification_time_ms=0,
                    public_signals=proof_request.public_signals,
                    message=f"Verification error: {e!s}",
                )
            )

    return BatchVerifyResponse(
        total=len(request.proofs),
        valid=valid_count,
        invalid=len(request.proofs) - valid_count,
        results=results,
    )


@router.post("/on-chain/{proof_id}")
async def verify_on_chain(proof_id: str) -> dict[str, Any]:
    """
    Verify a proof against on-chain records.

    This endpoint checks if a proof has been recorded on the blockchain
    and retrieves its verification status.

    Args:
        proof_id: The proof identifier

    Returns:
        On-chain verification status
    """
    logger.info("on_chain_verification", proof_id=proof_id)

    # TODO: Implement on-chain verification via blockchain client
    return {
        "proof_id": proof_id,
        "on_chain": False,
        "block_number": None,
        "transaction_hash": None,
        "verified": None,
        "message": "On-chain verification not yet implemented",
    }
