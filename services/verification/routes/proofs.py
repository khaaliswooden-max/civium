"""
ZK Proof Generation Routes
==========================

API endpoints for generating zero-knowledge proofs.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from shared.logging import get_logger
from shared.zk.models import ProofType
from shared.zk.prover import ComplianceProver


logger = get_logger(__name__)
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class ThresholdProofRequest(BaseModel):
    """Request to generate a threshold proof."""

    entity_id: str = Field(..., description="Entity identifier (e.g., LEI)")
    score: int = Field(..., ge=0, le=10000, description="Actual compliance score")
    threshold: int = Field(..., ge=0, le=10000, description="Minimum required score")

    model_config = {
        "json_schema_extra": {
            "examples": [{"entity_id": "LEI-549300EXAMPLE", "score": 8500, "threshold": 8000}]
        }
    }


class RangeProofRequest(BaseModel):
    """Request to generate a range proof."""

    entity_id: str = Field(..., description="Entity identifier")
    score: int = Field(..., ge=0, le=10000, description="Actual compliance score")
    min_score: int = Field(..., ge=0, le=10000, description="Minimum of range")
    max_score: int = Field(..., ge=0, le=10000, description="Maximum of range")


class TierProofRequest(BaseModel):
    """Request to generate a tier membership proof."""

    entity_id: str = Field(..., description="Entity identifier")
    score: int = Field(..., ge=0, le=10000, description="Actual compliance score")
    tier: int = Field(..., ge=1, le=5, description="Target compliance tier (1-5)")


class ProofResponse(BaseModel):
    """Response containing a generated proof."""

    success: bool
    proof_id: str
    proof_type: str
    proof: dict[str, Any]
    public_signals: list[str]
    proving_time_ms: int
    entity_hash: str


class ProofStatusResponse(BaseModel):
    """Response for proof status check."""

    proof_id: str
    status: str
    proof_type: str | None = None
    created_at: str | None = None
    verified: bool | None = None


# ============================================================================
# Proof Generation Endpoints
# ============================================================================


@router.post("/threshold", response_model=ProofResponse)
async def generate_threshold_proof(request: ThresholdProofRequest) -> ProofResponse:
    """
    Generate a ZK proof that entity's score meets or exceeds a threshold.

    This proof allows an entity to prove they meet a compliance threshold
    without revealing their actual score.

    Args:
        request: Threshold proof request containing entity_id, score, and threshold

    Returns:
        ProofResponse containing the generated proof and metadata
    """
    logger.info(
        "generating_threshold_proof",
        entity_id=request.entity_id,
        threshold=request.threshold,
    )

    try:
        prover = ComplianceProver()
        result = await prover.prove_threshold(
            score=request.score,
            threshold=request.threshold,
            entity_id=request.entity_id,
        )

        return ProofResponse(
            success=True,
            proof_id=f"proof-{result.metadata.entity_hash[:16]}",
            proof_type=ProofType.THRESHOLD.value,
            proof=result.proof.model_dump(),
            public_signals=result.public_signals.signals,
            proving_time_ms=result.metadata.proving_time_ms,
            entity_hash=result.metadata.entity_hash,
        )

    except ValueError as e:
        logger.warning("threshold_proof_validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except FileNotFoundError as e:
        logger.error("circuit_files_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK circuit files not available. Run circuit setup first.",
        ) from e
    except Exception as e:
        logger.error("threshold_proof_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Proof generation failed",
        ) from e


@router.post("/range", response_model=ProofResponse)
async def generate_range_proof(request: RangeProofRequest) -> ProofResponse:
    """
    Generate a ZK proof that entity's score is within a range.

    This proof allows an entity to prove their score falls within a
    specific range without revealing the exact score.

    Args:
        request: Range proof request containing entity_id, score, and range bounds

    Returns:
        ProofResponse containing the generated proof
    """
    logger.info(
        "generating_range_proof",
        entity_id=request.entity_id,
        range=f"[{request.min_score}, {request.max_score}]",
    )

    try:
        prover = ComplianceProver()
        result = await prover.prove_range(
            score=request.score,
            min_score=request.min_score,
            max_score=request.max_score,
            entity_id=request.entity_id,
        )

        return ProofResponse(
            success=True,
            proof_id=f"proof-{result.metadata.entity_hash[:16]}",
            proof_type=ProofType.RANGE.value,
            proof=result.proof.model_dump(),
            public_signals=result.public_signals.signals,
            proving_time_ms=result.metadata.proving_time_ms,
            entity_hash=result.metadata.entity_hash,
        )

    except ValueError as e:
        logger.warning("range_proof_validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except FileNotFoundError as e:
        logger.error("circuit_files_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK circuit files not available",
        ) from e
    except Exception as e:
        logger.error("range_proof_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Proof generation failed",
        ) from e


@router.post("/tier", response_model=ProofResponse)
async def generate_tier_proof(request: TierProofRequest) -> ProofResponse:
    """
    Generate a ZK proof of tier membership.

    This proof allows an entity to prove they belong to a specific
    compliance tier without revealing their exact score.

    Tier definitions:
    - Tier 1 (Exemplary): 9500-10000
    - Tier 2 (Strong): 8500-9499
    - Tier 3 (Adequate): 7000-8499
    - Tier 4 (Developing): 5000-6999
    - Tier 5 (Non-Compliant): 0-4999

    Args:
        request: Tier proof request containing entity_id, score, and target tier

    Returns:
        ProofResponse containing the generated proof
    """
    logger.info(
        "generating_tier_proof",
        entity_id=request.entity_id,
        tier=request.tier,
    )

    try:
        prover = ComplianceProver()
        result = await prover.prove_tier(
            score=request.score,
            tier=request.tier,
            entity_id=request.entity_id,
        )

        return ProofResponse(
            success=True,
            proof_id=f"proof-{result.metadata.entity_hash[:16]}",
            proof_type=ProofType.TIER.value,
            proof=result.proof.model_dump(),
            public_signals=result.public_signals.signals,
            proving_time_ms=result.metadata.proving_time_ms,
            entity_hash=result.metadata.entity_hash,
        )

    except ValueError as e:
        logger.warning("tier_proof_validation_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except FileNotFoundError as e:
        logger.error("circuit_files_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ZK circuit files not available",
        ) from e
    except Exception as e:
        logger.error("tier_proof_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Proof generation failed",
        ) from e


@router.get("/{proof_id}", response_model=ProofStatusResponse)
async def get_proof_status(proof_id: str) -> ProofStatusResponse:
    """
    Get the status of a previously generated proof.

    Args:
        proof_id: The proof identifier

    Returns:
        ProofStatusResponse containing proof status information
    """
    # TODO: Implement proof storage and retrieval
    logger.info("get_proof_status", proof_id=proof_id)

    return ProofStatusResponse(
        proof_id=proof_id,
        status="stored",
        proof_type=None,
        created_at=None,
        verified=None,
    )
