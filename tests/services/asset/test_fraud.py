"""Tests for fraud detection."""

import pytest
from datetime import datetime, timedelta

from services.asset.ml.fraud.detector import (
    FraudDetector,
    FraudResult,
)


@pytest.fixture
def detector() -> FraudDetector:
    """Create fraud detector for testing."""
    return FraudDetector()


class TestFraudDetector:
    """Tests for FraudDetector."""

    def test_detect_fraud_low_risk(self, detector: FraudDetector) -> None:
        """Test detection returns low risk for normal claim."""
        claim = {
            "claim_id": "CLM-001",
            "claim_type": "repair",
            "estimated_cost": 50,
        }

        warranty = {
            "warranty_id": "WRN-001",
            "warranty_end": (datetime.utcnow() + timedelta(days=180)).isoformat(),
            "claims_history": [],
            "terms": {"product_value": 500},
        }

        result = detector.detect_fraud(claim, warranty)

        assert isinstance(result, FraudResult)
        assert result.risk_level == "low"
        assert result.fraud_score < 0.3
        assert not result.requires_investigation

    def test_detect_fraud_multiple_claims(self, detector: FraudDetector) -> None:
        """Test detection flags multiple claims pattern."""
        claim = {
            "claim_id": "CLM-002",
            "claim_type": "replacement",
            "estimated_cost": 100,
        }

        warranty = {
            "warranty_id": "WRN-002",
            "warranty_end": (datetime.utcnow() + timedelta(days=180)).isoformat(),
            "claims_history": [
                {"claim_id": "C1"},
                {"claim_id": "C2"},
                {"claim_id": "C3"},
                {"claim_id": "C4"},
            ],
            "terms": {"product_value": 500},
        }

        result = detector.detect_fraud(claim, warranty)

        assert result.fraud_score > 0.2
        assert any(f["factor"] == "Multiple claims" for f in result.contributing_factors)

    def test_detect_fraud_end_of_warranty(self, detector: FraudDetector) -> None:
        """Test detection flags end-of-warranty claims."""
        claim = {
            "claim_id": "CLM-003",
            "claim_type": "repair",
            "estimated_cost": 75,
        }

        warranty = {
            "warranty_id": "WRN-003",
            "warranty_end": (datetime.utcnow() + timedelta(days=15)).isoformat(),
            "claims_history": [],
            "terms": {"product_value": 300},
        }

        result = detector.detect_fraud(claim, warranty)

        assert any(f["factor"] == "End of warranty claim" for f in result.contributing_factors)

    def test_detect_fraud_high_value(self, detector: FraudDetector) -> None:
        """Test detection flags high-value claims."""
        claim = {
            "claim_id": "CLM-004",
            "claim_type": "replacement",
            "estimated_cost": 450,  # 90% of product value
        }

        warranty = {
            "warranty_id": "WRN-004",
            "warranty_end": (datetime.utcnow() + timedelta(days=180)).isoformat(),
            "claims_history": [],
            "terms": {"product_value": 500},
        }

        result = detector.detect_fraud(claim, warranty)

        assert any(f["factor"] == "High value claim" for f in result.contributing_factors)

    def test_detect_fraud_previous_flags(self, detector: FraudDetector) -> None:
        """Test detection considers previous fraud flags."""
        claim = {
            "claim_id": "CLM-005",
            "claim_type": "repair",
            "estimated_cost": 50,
        }

        warranty = {
            "warranty_id": "WRN-005",
            "warranty_end": (datetime.utcnow() + timedelta(days=180)).isoformat(),
            "claims_history": [],
            "terms": {"product_value": 500},
        }

        claimant_history = {
            "previous_fraud_flags": 2,
        }

        result = detector.detect_fraud(claim, warranty, claimant_history)

        assert result.fraud_score > 0.3
        assert any(f["factor"] == "Previous fraud flags" for f in result.contributing_factors)

    def test_detect_fraud_critical_risk(self, detector: FraudDetector) -> None:
        """Test detection returns critical for multiple red flags."""
        claim = {
            "claim_id": "CLM-006",
            "claim_type": "replacement",
            "estimated_cost": 900,  # Very high
        }

        warranty = {
            "warranty_id": "WRN-006",
            "warranty_end": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "claims_history": [{"c": 1}, {"c": 2}, {"c": 3}, {"c": 4}, {"c": 5}],
            "terms": {"product_value": 1000},
        }

        claimant_history = {
            "previous_fraud_flags": 1,
            "claims_last_90_days": 8,
        }

        result = detector.detect_fraud(claim, warranty, claimant_history)

        assert result.risk_level in ["high", "critical"]
        assert result.requires_investigation

    def test_get_claimant_risk_profile(self, detector: FraudDetector) -> None:
        """Test getting claimant risk profile."""
        profile = detector.get_claimant_risk_profile("USR-001")

        assert "claimant_id" in profile
        assert "total_claims" in profile
        assert "risk_score" in profile
        assert profile["claimant_id"] == "USR-001"

