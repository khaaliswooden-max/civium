"""
Unit Tests for ZK-SNARK Prover
==============================

Tests for the Python ZK proof generation and verification.

Version: 1.0.0
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from shared.zk.models import (
    ProofType,
    ZKProof,
    PublicSignals,
    ProofMetadata,
    ProofWithMetadata,
    VerificationResult,
    ThresholdProofRequest,
    RangeProofRequest,
    TierProofRequest,
)
from shared.zk.prover import ComplianceProver, ThresholdInput, RangeInput, TierInput


class TestZKModels:
    """Tests for ZK data models."""
    
    def test_zkproof_to_calldata(self):
        """Test converting proof to Solidity calldata."""
        proof = ZKProof(
            pi_a=["123", "456", "1"],
            pi_b=[["789", "101"], ["112", "131"], ["1", "0"]],
            pi_c=["415", "161", "1"],
        )
        
        calldata = proof.to_calldata()
        
        assert len(calldata) == 8
        assert calldata[0] == 123
        assert calldata[1] == 456
        assert calldata[2] == 789
    
    def test_zkproof_hex_roundtrip(self):
        """Test hex serialization roundtrip."""
        original = ZKProof(
            pi_a=["123", "456", "1"],
            pi_b=[["789", "101"], ["112", "131"], ["1", "0"]],
            pi_c=["415", "161", "1"],
        )
        
        hex_str = original.to_hex()
        restored = ZKProof.from_hex(hex_str)
        
        assert restored.pi_a == original.pi_a
        assert restored.pi_b == original.pi_b
        assert restored.pi_c == original.pi_c
    
    def test_public_signals_commitment(self):
        """Test extracting commitment from public signals."""
        signals = PublicSignals(signals=["8000", "12345", "99999"])
        
        assert signals.commitment == "99999"
        assert signals.to_int_list() == [8000, 12345, 99999]
    
    def test_threshold_proof_request_validation(self):
        """Test threshold proof request validation."""
        # Valid request
        request = ThresholdProofRequest(
            entity_id="LEI-123",
            score=8500,
            threshold=8000,
        )
        assert request.score == 8500
        
        # Invalid: score below threshold
        with pytest.raises(ValueError, match="does not meet threshold"):
            ThresholdProofRequest(
                entity_id="LEI-123",
                score=7500,
                threshold=8000,
            )
        
        # Invalid: score out of range
        with pytest.raises(ValueError):
            ThresholdProofRequest(
                entity_id="LEI-123",
                score=15000,  # > 10000
                threshold=8000,
            )
    
    def test_range_proof_request_validation(self):
        """Test range proof request validation."""
        # Valid request
        request = RangeProofRequest(
            entity_id="LEI-123",
            score=8000,
            min_score=7000,
            max_score=9000,
        )
        assert request.score == 8000
        
        # Invalid: score outside range
        with pytest.raises(ValueError, match="not in range"):
            RangeProofRequest(
                entity_id="LEI-123",
                score=6500,  # Below min
                min_score=7000,
                max_score=9000,
            )
        
        # Invalid: max < min
        with pytest.raises(ValueError, match="must be >="):
            RangeProofRequest(
                entity_id="LEI-123",
                score=8000,
                min_score=9000,
                max_score=7000,  # max < min
            )
    
    def test_tier_proof_request_validation(self):
        """Test tier proof request validation."""
        # Valid tier 1 request
        request = TierProofRequest(
            entity_id="LEI-123",
            score=9700,
            tier=1,
        )
        assert request.tier == 1
        
        # Valid tier 5 request
        request = TierProofRequest(
            entity_id="LEI-123",
            score=3000,
            tier=5,
        )
        assert request.tier == 5
        
        # Invalid: score doesn't match tier
        with pytest.raises(ValueError, match="not in tier"):
            TierProofRequest(
                entity_id="LEI-123",
                score=8000,  # Tier 3 score
                tier=1,      # Claims tier 1
            )
        
        # Invalid tier number
        with pytest.raises(ValueError):
            TierProofRequest(
                entity_id="LEI-123",
                score=5000,
                tier=6,  # Invalid
            )


class TestComplianceProver:
    """Tests for the compliance prover."""
    
    def test_hash_entity_id(self):
        """Test entity ID hashing."""
        prover = ComplianceProver.__new__(ComplianceProver)
        prover.build_dir = None
        
        hash1 = prover._hash_entity_id("LEI-123456789")
        hash2 = prover._hash_entity_id("LEI-123456789")
        hash3 = prover._hash_entity_id("LEI-987654321")
        
        # Deterministic
        assert hash1 == hash2
        
        # Different inputs produce different hashes
        assert hash1 != hash3
        
        # Result is a decimal string
        assert hash1.isdigit()
    
    def test_generate_salt(self):
        """Test salt generation."""
        prover = ComplianceProver.__new__(ComplianceProver)
        
        salt1 = prover._generate_salt()
        salt2 = prover._generate_salt()
        
        # Random each time
        assert salt1 != salt2
        
        # Is a decimal string
        assert salt1.isdigit()
    
    @pytest.mark.asyncio
    async def test_prove_threshold_validation(self):
        """Test threshold proof input validation."""
        prover = ComplianceProver.__new__(ComplianceProver)
        prover.build_dir = None
        prover._validate_setup = lambda: None
        
        # Score below threshold
        with pytest.raises(ValueError, match="does not meet threshold"):
            await prover.prove_threshold(
                score=7500,
                threshold=8000,
                entity_id="LEI-123",
            )
        
        # Score out of range
        with pytest.raises(ValueError, match="must be <= 10000"):
            await prover.prove_threshold(
                score=12000,
                threshold=8000,
                entity_id="LEI-123",
            )
    
    @pytest.mark.asyncio
    async def test_prove_range_validation(self):
        """Test range proof input validation."""
        prover = ComplianceProver.__new__(ComplianceProver)
        prover.build_dir = None
        prover._validate_setup = lambda: None
        
        # Score outside range
        with pytest.raises(ValueError, match="not in range"):
            await prover.prove_range(
                score=6000,
                min_score=7000,
                max_score=9000,
                entity_id="LEI-123",
            )
    
    @pytest.mark.asyncio
    async def test_prove_tier_validation(self):
        """Test tier proof input validation."""
        prover = ComplianceProver.__new__(ComplianceProver)
        prover.build_dir = None
        prover._validate_setup = lambda: None
        
        # Invalid tier
        with pytest.raises(ValueError, match="Invalid tier"):
            await prover.prove_tier(
                score=8000,
                tier=6,
                entity_id="LEI-123",
            )
        
        # Score doesn't match tier
        with pytest.raises(ValueError, match="not in tier"):
            await prover.prove_tier(
                score=8000,  # Tier 3
                tier=1,      # Claims tier 1
                entity_id="LEI-123",
            )


class TestThresholdInput:
    """Tests for ThresholdInput dataclass."""
    
    def test_threshold_input_creation(self):
        """Test creating a threshold input."""
        input_data = ThresholdInput(
            threshold=8000,
            entity_hash="12345678901234567890",
            score=8500,
            salt="98765432109876543210",
        )
        
        assert input_data.threshold == 8000
        assert input_data.score == 8500


class TestRangeInput:
    """Tests for RangeInput dataclass."""
    
    def test_range_input_creation(self):
        """Test creating a range input."""
        input_data = RangeInput(
            min_score=7000,
            max_score=9000,
            entity_hash="12345678901234567890",
            score=8000,
            salt="98765432109876543210",
        )
        
        assert input_data.min_score == 7000
        assert input_data.max_score == 9000
        assert input_data.score == 8000


class TestTierInput:
    """Tests for TierInput dataclass."""
    
    def test_tier_input_creation(self):
        """Test creating a tier input."""
        input_data = TierInput(
            target_tier=2,
            entity_hash="12345678901234567890",
            score=8700,
            salt="98765432109876543210",
        )
        
        assert input_data.target_tier == 2
        assert input_data.score == 8700


class TestVerificationResult:
    """Tests for VerificationResult model."""
    
    def test_verification_result_valid(self):
        """Test valid verification result."""
        result = VerificationResult(
            valid=True,
            commitment="123456789",
            verification_time_ms=50,
        )
        
        assert result.valid is True
        assert result.commitment == "123456789"
        assert result.error is None
    
    def test_verification_result_invalid(self):
        """Test invalid verification result."""
        result = VerificationResult(
            valid=False,
            verification_time_ms=50,
            error="Proof verification failed",
        )
        
        assert result.valid is False
        assert result.error == "Proof verification failed"


# Benchmark test vectors
BENCHMARK_INPUTS = [
    # Threshold proofs
    {"circuit": "threshold", "score": 8500, "threshold": 8000},
    {"circuit": "threshold", "score": 9999, "threshold": 9500},
    {"circuit": "threshold", "score": 5001, "threshold": 5000},
    # Range proofs
    {"circuit": "range", "score": 8000, "min": 7000, "max": 9000},
    {"circuit": "range", "score": 5000, "min": 0, "max": 10000},
    # Tier proofs
    {"circuit": "tier", "score": 9700, "tier": 1},
    {"circuit": "tier", "score": 8700, "tier": 2},
    {"circuit": "tier", "score": 7500, "tier": 3},
    {"circuit": "tier", "score": 6000, "tier": 4},
    {"circuit": "tier", "score": 3000, "tier": 5},
]


class TestBenchmarkInputs:
    """Test that benchmark inputs are valid."""
    
    @pytest.mark.parametrize("input_data", BENCHMARK_INPUTS)
    def test_benchmark_input_valid(self, input_data):
        """Verify all benchmark inputs are valid."""
        if input_data["circuit"] == "threshold":
            assert input_data["score"] >= input_data["threshold"]
            assert 0 <= input_data["score"] <= 10000
            assert 0 <= input_data["threshold"] <= 10000
        
        elif input_data["circuit"] == "range":
            assert input_data["min"] <= input_data["score"] <= input_data["max"]
            assert 0 <= input_data["min"] <= input_data["max"] <= 10000
        
        elif input_data["circuit"] == "tier":
            tier = input_data["tier"]
            score = input_data["score"]
            bounds = {
                1: (9500, 10000),
                2: (8500, 9499),
                3: (7000, 8499),
                4: (5000, 6999),
                5: (0, 4999),
            }
            min_score, max_score = bounds[tier]
            assert min_score <= score <= max_score

