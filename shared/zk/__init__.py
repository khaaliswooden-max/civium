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

from shared.zk.prover import (
    ComplianceProver,
    ThresholdInput,
    RangeInput,
    TierInput,
)
from shared.zk.verifier import (
    ComplianceVerifier,
    verify_threshold_proof,
    verify_range_proof,
    verify_tier_proof,
)
from shared.zk.models import (
    ZKProof,
    ProofMetadata,
    VerificationResult,
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

