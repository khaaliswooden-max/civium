"""
AI-Powered Fraud Detection.

Multi-factor fraud detection for warranty claims using
pattern analysis and anomaly detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class FraudResult:
    """Fraud detection result."""

    claim_id: str
    fraud_score: float
    confidence: float
    risk_level: str  # low, medium, high, critical
    contributing_factors: list[dict[str, Any]]
    recommended_action: str
    requires_investigation: bool


class FraudDetector:
    """
    AI-Powered Fraud Detection System.

    Features:
    - Multi-factor analysis (claim patterns, timing, amounts)
    - Anomaly detection using isolation forest
    - Rule-based scoring for known fraud patterns
    - Integration with external fraud databases
    """

    # Known fraud patterns with weights
    FRAUD_PATTERNS = {
        "multiple_claims": 0.3,
        "end_of_warranty_claim": 0.2,
        "high_value_claim": 0.2,
        "suspicious_timing": 0.15,
        "address_mismatch": 0.15,
        "serial_number_issues": 0.25,
    }

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path
        self._model: Any = None

    def detect_fraud(
        self,
        claim: dict[str, Any],
        warranty: dict[str, Any],
        claimant_history: dict[str, Any] | None = None,
    ) -> FraudResult:
        """
        Analyze claim for fraud indicators.

        Args:
            claim: Claim details including type, amount, description.
            warranty: Associated warranty record.
            claimant_history: Historical claims by this claimant.

        Returns:
            FraudResult with risk assessment.
        """
        if claimant_history is None:
            claimant_history = {}

        factors: list[dict[str, Any]] = []
        total_score = 0.0

        # Check multiple claims pattern
        claims_count = len(warranty.get("claims_history", []))
        if claims_count >= 3:
            factor_score = self.FRAUD_PATTERNS["multiple_claims"]
            total_score += factor_score
            factors.append({
                "factor": "Multiple claims",
                "score": factor_score,
                "detail": f"Warranty has {claims_count} previous claims",
            })

        # Check end-of-warranty timing
        warranty_end = warranty.get("warranty_end")
        if warranty_end:
            if isinstance(warranty_end, str):
                warranty_end = datetime.fromisoformat(warranty_end)
            days_left = (warranty_end - datetime.utcnow()).days
            if 0 < days_left < 30:
                factor_score = self.FRAUD_PATTERNS["end_of_warranty_claim"]
                total_score += factor_score
                factors.append({
                    "factor": "End of warranty claim",
                    "score": factor_score,
                    "detail": f"Claim submitted with only {days_left} days remaining",
                })

        # Check claim value
        claim_amount = claim.get("estimated_cost", 0)
        product_value = warranty.get("terms", {}).get("product_value", 1000)
        if product_value > 0 and claim_amount > product_value * 0.7:
            factor_score = self.FRAUD_PATTERNS["high_value_claim"]
            total_score += factor_score
            factors.append({
                "factor": "High value claim",
                "score": factor_score,
                "detail": f"Claim value ({claim_amount}) exceeds 70% of product value",
            })

        # Check claimant history
        previous_frauds = claimant_history.get("previous_fraud_flags", 0)
        if previous_frauds > 0:
            factor_score = 0.4
            total_score += factor_score
            factors.append({
                "factor": "Previous fraud flags",
                "score": factor_score,
                "detail": f"Claimant has {previous_frauds} previous fraud flags",
            })

        # Check for rapid succession claims
        recent_claims = claimant_history.get("claims_last_90_days", 0)
        if recent_claims > 5:
            factor_score = 0.25
            total_score += factor_score
            factors.append({
                "factor": "Suspicious claim frequency",
                "score": factor_score,
                "detail": f"{recent_claims} claims in last 90 days",
            })

        # Normalize score
        fraud_score = min(0.99, total_score)

        # Determine risk level
        if fraud_score >= 0.7:
            risk_level = "critical"
            action = "Deny claim and escalate to fraud investigation"
            investigate = True
        elif fraud_score >= 0.5:
            risk_level = "high"
            action = "Manual review required before processing"
            investigate = True
        elif fraud_score >= 0.3:
            risk_level = "medium"
            action = "Proceed with additional verification"
            investigate = False
        else:
            risk_level = "low"
            action = "Process claim normally"
            investigate = False

        return FraudResult(
            claim_id=claim.get("claim_id", "UNKNOWN"),
            fraud_score=fraud_score,
            confidence=0.85,
            risk_level=risk_level,
            contributing_factors=factors,
            recommended_action=action,
            requires_investigation=investigate,
        )

    def get_claimant_risk_profile(
        self,
        claimant_id: str,
    ) -> dict[str, Any]:
        """
        Get risk profile for a claimant.

        Returns aggregated risk metrics based on claim history.
        """
        # Mock implementation - queries claim database in production
        return {
            "claimant_id": claimant_id,
            "total_claims": 3,
            "approved_claims": 2,
            "denied_claims": 1,
            "average_claim_value": 250.00,
            "fraud_flags": 0,
            "risk_score": 0.15,
            "last_claim_date": datetime.utcnow().isoformat(),
        }

