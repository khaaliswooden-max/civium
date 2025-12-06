"""
ZK-SNARK Data Models
====================

Pydantic models for ZK proof data.

Version: 1.0.0
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ProofType(str, Enum):
    """Types of compliance proofs."""

    THRESHOLD = "threshold"
    RANGE = "range"
    TIER = "tier"


class ZKProof(BaseModel):
    """
    A zero-knowledge proof.

    Compatible with snarkjs Groth16 proof format.
    """

    # Proof points (G1 and G2 elements)
    pi_a: list[str] = Field(..., description="Proof point A (G1)")
    pi_b: list[list[str]] = Field(..., description="Proof point B (G2)")
    pi_c: list[str] = Field(..., description="Proof point C (G1)")

    # Protocol info
    protocol: str = Field(default="groth16")
    curve: str = Field(default="bn128")

    def to_calldata(self) -> list[int]:
        """Convert to Solidity calldata format (8 uint256)."""
        return [
            int(self.pi_a[0]),
            int(self.pi_a[1]),
            int(self.pi_b[0][0]),
            int(self.pi_b[0][1]),
            int(self.pi_b[1][0]),
            int(self.pi_b[1][1]),
            int(self.pi_c[0]),
            int(self.pi_c[1]),
        ]

    def to_hex(self) -> str:
        """Convert to hex string for storage."""
        import json

        return json.dumps(self.model_dump()).encode().hex()

    @classmethod
    def from_hex(cls, hex_str: str) -> "ZKProof":
        """Create from hex string."""
        import json

        data = json.loads(bytes.fromhex(hex_str).decode())
        return cls(**data)


class PublicSignals(BaseModel):
    """Public inputs and outputs from a proof."""

    signals: list[str] = Field(..., description="Public signals as decimal strings")

    @property
    def commitment(self) -> str:
        """Get the score commitment (last signal)."""
        return self.signals[-1] if self.signals else ""

    def to_int_list(self) -> list[int]:
        """Convert to list of integers."""
        return [int(s) for s in self.signals]


class ProofMetadata(BaseModel):
    """Metadata about a generated proof."""

    proof_type: ProofType
    circuit_name: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    proving_time_ms: int = Field(..., ge=0)

    # Entity info
    entity_hash: str

    # For threshold proofs
    threshold: int | None = None

    # For range proofs
    min_score: int | None = None
    max_score: int | None = None

    # For tier proofs
    tier: int | None = None


class ProofWithMetadata(BaseModel):
    """Complete proof with metadata."""

    proof: ZKProof
    public_signals: PublicSignals
    metadata: ProofMetadata

    @property
    def commitment(self) -> str:
        """Get the score commitment."""
        return self.public_signals.commitment


class VerificationResult(BaseModel):
    """Result of proof verification."""

    valid: bool
    commitment: str | None = None
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verification_time_ms: int = Field(..., ge=0)

    # On-chain verification
    tx_hash: str | None = None
    block_number: int | None = None

    # Error info
    error: str | None = None


class ThresholdProofRequest(BaseModel):
    """Request to generate a threshold proof."""

    entity_id: str = Field(..., description="Entity identifier (e.g., LEI)")
    score: int = Field(..., ge=0, le=10000, description="Compliance score (0-10000)")
    threshold: int = Field(..., ge=0, le=10000, description="Minimum threshold")

    @field_validator("score")
    @classmethod
    def score_must_meet_threshold(cls, v: int, info) -> int:
        threshold = info.data.get("threshold", 0)
        if v < threshold:
            raise ValueError(f"Score {v} does not meet threshold {threshold}")
        return v


class RangeProofRequest(BaseModel):
    """Request to generate a range proof."""

    entity_id: str
    score: int = Field(..., ge=0, le=10000)
    min_score: int = Field(..., ge=0, le=10000)
    max_score: int = Field(..., ge=0, le=10000)

    @field_validator("max_score")
    @classmethod
    def max_must_be_gte_min(cls, v: int, info) -> int:
        min_score = info.data.get("min_score", 0)
        if v < min_score:
            raise ValueError(f"max_score {v} must be >= min_score {min_score}")
        return v

    @field_validator("score")
    @classmethod
    def score_must_be_in_range(cls, v: int, info) -> int:
        min_score = info.data.get("min_score", 0)
        max_score = info.data.get("max_score", 10000)
        if v < min_score or v > max_score:
            raise ValueError(f"Score {v} not in range [{min_score}, {max_score}]")
        return v


class TierProofRequest(BaseModel):
    """Request to generate a tier membership proof."""

    entity_id: str
    score: int = Field(..., ge=0, le=10000)
    tier: int = Field(..., ge=1, le=5, description="Target tier (1-5)")

    @field_validator("score")
    @classmethod
    def score_must_match_tier(cls, v: int, info) -> int:
        tier = info.data.get("tier", 1)
        bounds = {
            1: (9500, 10000),
            2: (8500, 9499),
            3: (7000, 8499),
            4: (5000, 6999),
            5: (0, 4999),
        }
        min_score, max_score = bounds.get(tier, (0, 10000))
        if v < min_score or v > max_score:
            raise ValueError(f"Score {v} not in tier {tier} range [{min_score}, {max_score}]")
        return v
