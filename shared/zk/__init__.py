"""
ZK-SNARK Integration Module
===========================

Python bindings for ZK-SNARK compliance verification.

Usage:
    from shared.zk import ComplianceProver, verify_threshold_proof

    # Generate a proof
    prover = ComplianceProver()
    proof = await prover.prove_threshold(
        score=8500,
        threshold=8000,
        entity_id="LEI-123456789",
    )

    # Verify proof
    is_valid = await verify_threshold_proof(proof)

Version: 1.0.0
"""

from shared.zk.models import (
    ProofMetadata,
    VerificationResult,
    ZKProof,
)
from shared.zk.prover import (
    ComplianceProver,
    RangeInput,
    ThresholdInput,
    TierInput,
)
from shared.zk.verifier import (
    ComplianceVerifier,
    verify_range_proof,
    verify_threshold_proof,
    verify_tier_proof,
)


__all__ = [
    # Prover
    "ComplianceProver",
    "ThresholdInput",
    "RangeInput",
    "TierInput",
    # Verifier
    "ComplianceVerifier",
    "verify_threshold_proof",
    "verify_range_proof",
    "verify_tier_proof",
    # Models
    "ZKProof",
    "ProofMetadata",
    "VerificationResult",
]
