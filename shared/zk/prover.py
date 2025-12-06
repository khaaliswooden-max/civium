"""
ZK-SNARK Proof Generation
=========================

Python wrapper for generating ZK-SNARK compliance proofs.

Uses snarkjs via subprocess for proof generation (primary method)
or the Rust library via PyO3 for performance (when available).

Version: 1.0.0
"""

import asyncio
import hashlib
import json
import secrets
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.logging import get_logger
from shared.zk.models import (
    ProofMetadata,
    ProofType,
    ProofWithMetadata,
    PublicSignals,
    ZKProof,
)


logger = get_logger(__name__)

# Default circuit build directory
DEFAULT_BUILD_DIR = Path(__file__).parent.parent.parent / "circuits" / "build"


@dataclass
class ThresholdInput:
    """Input for threshold proof."""

    threshold: int
    entity_hash: str
    score: int
    salt: str


@dataclass
class RangeInput:
    """Input for range proof."""

    min_score: int
    max_score: int
    entity_hash: str
    score: int
    salt: str


@dataclass
class TierInput:
    """Input for tier proof."""

    target_tier: int
    entity_hash: str
    score: int
    salt: str


class ComplianceProver:
    """
    ZK-SNARK proof generator for compliance verification.

    Usage:
        prover = ComplianceProver()

        proof = await prover.prove_threshold(
            score=8500,
            threshold=8000,
            entity_id="LEI-123456789",
        )
    """

    def __init__(self, build_dir: str | Path | None = None):
        """
        Initialize the prover.

        Args:
            build_dir: Path to circuit build directory.
                      Defaults to circuits/build/
        """
        self.build_dir = Path(build_dir) if build_dir else DEFAULT_BUILD_DIR
        self._validate_setup()

    def _validate_setup(self) -> None:
        """Validate that required circuit files exist."""
        if not self.build_dir.exists():
            logger.warning(
                "zk_circuit_build_dir_not_found",
                path=str(self.build_dir),
            )

    def _hash_entity_id(self, entity_id: str) -> str:
        """
        Hash entity ID to a field element.

        Uses SHA-256 and reduces mod field order.
        """
        # SHA-256 hash
        digest = hashlib.sha256(entity_id.encode()).digest()

        # Convert to integer
        hash_int = int.from_bytes(digest, "big")

        # BN254 scalar field order
        field_order = 21888242871839275222246405745257275088548364400416034343698204186575808495617

        # Reduce mod field order
        return str(hash_int % field_order)

    def _generate_salt(self) -> str:
        """Generate a random salt as a field element."""
        # Generate 31 bytes (< 32 to stay under field order)
        salt_bytes = secrets.token_bytes(31)
        return str(int.from_bytes(salt_bytes, "big"))

    async def _run_snarkjs(
        self,
        circuit_name: str,
        input_data: dict[str, Any],
    ) -> tuple[dict, list[str], int]:
        """
        Run snarkjs to generate a proof.

        Returns:
            Tuple of (proof_json, public_signals, proving_time_ms)
        """
        circuit_dir = self.build_dir / circuit_name
        wasm_path = circuit_dir / f"{circuit_name}_js" / f"{circuit_name}.wasm"
        zkey_path = circuit_dir / "proving_key.zkey"

        if not wasm_path.exists():
            raise FileNotFoundError(f"Circuit WASM not found: {wasm_path}")
        if not zkey_path.exists():
            raise FileNotFoundError(f"Proving key not found: {zkey_path}")

        # Write input to temp file
        input_file = circuit_dir / "input_temp.json"
        with open(input_file, "w") as f:
            json.dump(input_data, f)

        try:
            start_time = time.time()

            # Run snarkjs
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "npx",
                    "snarkjs",
                    "groth16",
                    "fullprove",
                    str(input_file),
                    str(wasm_path),
                    str(zkey_path),
                    str(circuit_dir / "proof_temp.json"),
                    str(circuit_dir / "public_temp.json"),
                ],
                capture_output=True,
                text=True,
                cwd=self.build_dir.parent,
            )

            proving_time_ms = int((time.time() - start_time) * 1000)

            if result.returncode != 0:
                logger.error(
                    "snarkjs_proof_generation_failed",
                    stderr=result.stderr,
                    circuit=circuit_name,
                )
                raise RuntimeError(f"Proof generation failed: {result.stderr}")

            # Read outputs
            with open(circuit_dir / "proof_temp.json") as f:
                proof_json = json.load(f)
            with open(circuit_dir / "public_temp.json") as f:
                public_signals = json.load(f)

            logger.info(
                "zk_proof_generated",
                circuit=circuit_name,
                proving_time_ms=proving_time_ms,
            )

            return proof_json, public_signals, proving_time_ms

        finally:
            # Cleanup temp files
            for temp_file in ["input_temp.json", "proof_temp.json", "public_temp.json"]:
                temp_path = circuit_dir / temp_file
                if temp_path.exists():
                    temp_path.unlink()

    async def prove_threshold(
        self,
        score: int,
        threshold: int,
        entity_id: str,
        salt: str | None = None,
    ) -> ProofWithMetadata:
        """
        Generate a proof that score >= threshold.

        Args:
            score: Actual compliance score (0-10000)
            threshold: Minimum required score
            entity_id: Entity identifier (e.g., LEI)
            salt: Optional salt (generated if not provided)

        Returns:
            ProofWithMetadata containing the proof and metadata

        Raises:
            ValueError: If score < threshold or values out of range
        """
        if score < threshold:
            raise ValueError(f"Score {score} does not meet threshold {threshold}")
        if score > 10000 or threshold > 10000:
            raise ValueError("Score and threshold must be <= 10000")

        entity_hash = self._hash_entity_id(entity_id)
        salt = salt or self._generate_salt()

        input_data = {
            "threshold": threshold,
            "entityHash": entity_hash,
            "score": score,
            "salt": salt,
        }

        proof_json, public_signals, proving_time_ms = await self._run_snarkjs(
            "compliance_threshold",
            input_data,
        )

        return ProofWithMetadata(
            proof=ZKProof(**proof_json),
            public_signals=PublicSignals(signals=public_signals),
            metadata=ProofMetadata(
                proof_type=ProofType.THRESHOLD,
                circuit_name="compliance_threshold",
                proving_time_ms=proving_time_ms,
                entity_hash=entity_hash,
                threshold=threshold,
            ),
        )

    async def prove_range(
        self,
        score: int,
        min_score: int,
        max_score: int,
        entity_id: str,
        salt: str | None = None,
    ) -> ProofWithMetadata:
        """
        Generate a proof that min_score <= score <= max_score.

        Args:
            score: Actual compliance score
            min_score: Minimum of range (inclusive)
            max_score: Maximum of range (inclusive)
            entity_id: Entity identifier
            salt: Optional salt

        Returns:
            ProofWithMetadata containing the proof
        """
        if score < min_score or score > max_score:
            raise ValueError(f"Score {score} not in range [{min_score}, {max_score}]")

        entity_hash = self._hash_entity_id(entity_id)
        salt = salt or self._generate_salt()

        input_data = {
            "minScore": min_score,
            "maxScore": max_score,
            "entityHash": entity_hash,
            "score": score,
            "salt": salt,
        }

        proof_json, public_signals, proving_time_ms = await self._run_snarkjs(
            "range_proof",
            input_data,
        )

        return ProofWithMetadata(
            proof=ZKProof(**proof_json),
            public_signals=PublicSignals(signals=public_signals),
            metadata=ProofMetadata(
                proof_type=ProofType.RANGE,
                circuit_name="range_proof",
                proving_time_ms=proving_time_ms,
                entity_hash=entity_hash,
                min_score=min_score,
                max_score=max_score,
            ),
        )

    async def prove_tier(
        self,
        score: int,
        tier: int,
        entity_id: str,
        salt: str | None = None,
    ) -> ProofWithMetadata:
        """
        Generate a proof of tier membership.

        Args:
            score: Actual compliance score
            tier: Target tier (1-5)
            entity_id: Entity identifier
            salt: Optional salt

        Returns:
            ProofWithMetadata containing the proof
        """
        tier_bounds = {
            1: (9500, 10000),
            2: (8500, 9499),
            3: (7000, 8499),
            4: (5000, 6999),
            5: (0, 4999),
        }

        if tier not in tier_bounds:
            raise ValueError(f"Invalid tier {tier}, must be 1-5")

        min_score, max_score = tier_bounds[tier]
        if score < min_score or score > max_score:
            raise ValueError(f"Score {score} not in tier {tier} range [{min_score}, {max_score}]")

        entity_hash = self._hash_entity_id(entity_id)
        salt = salt or self._generate_salt()

        input_data = {
            "targetTier": tier,
            "entityHash": entity_hash,
            "score": score,
            "salt": salt,
        }

        proof_json, public_signals, proving_time_ms = await self._run_snarkjs(
            "tier_membership",
            input_data,
        )

        return ProofWithMetadata(
            proof=ZKProof(**proof_json),
            public_signals=PublicSignals(signals=public_signals),
            metadata=ProofMetadata(
                proof_type=ProofType.TIER,
                circuit_name="tier_membership",
                proving_time_ms=proving_time_ms,
                entity_hash=entity_hash,
                tier=tier,
            ),
        )
