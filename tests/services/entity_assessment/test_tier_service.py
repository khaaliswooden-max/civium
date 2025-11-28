"""
Tier Service Tests
==================

Tests for the automatic tier assignment service.

Version: 0.1.0
"""

import pytest

from services.entity_assessment.services.tier import (
    TierService,
    TierCriteria,
    TierRecommendation,
    ComplianceTier,
    RiskLevel,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tier_service() -> TierService:
    """Get a tier service with default criteria."""
    return TierService()


@pytest.fixture
def custom_tier_service() -> TierService:
    """Get a tier service with custom criteria."""
    criteria = TierCriteria(
        large_employee_count=100,  # Lower threshold
        medium_employee_count=20,
        large_revenue=10_000_000,
        medium_revenue=1_000_000,
        multi_jurisdiction_threshold=2,
    )
    return TierService(criteria)


# =============================================================================
# Basic Tier Determination Tests
# =============================================================================


class TestTierDetermination:
    """Tests for basic tier determination."""

    def test_basic_tier_for_small_entity(self, tier_service: TierService) -> None:
        """Small entity with no risk factors gets BASIC tier."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        assert recommendation.recommended_tier == ComplianceTier.BASIC
        assert recommendation.confidence > 0.5

    def test_standard_tier_for_medium_entity(self, tier_service: TierService) -> None:
        """Medium entity gets STANDARD tier."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="medium",
            employee_count=150,
            annual_revenue=15_000_000,
            jurisdictions=["US", "CA"],
            sectors=["TECHNOLOGY"],
        )

        assert recommendation.recommended_tier == ComplianceTier.STANDARD

    def test_advanced_tier_for_large_entity(self, tier_service: TierService) -> None:
        """Large entity gets ADVANCED tier."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="large",
            employee_count=500,
            annual_revenue=100_000_000,
            jurisdictions=["US", "EU", "UK"],
            sectors=["MANUFACTURING"],
        )

        assert recommendation.recommended_tier == ComplianceTier.ADVANCED

    def test_advanced_tier_for_regulated_sector(self, tier_service: TierService) -> None:
        """Entity in regulated sector gets ADVANCED tier regardless of size."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="small",
            employee_count=25,
            annual_revenue=2_000_000,
            jurisdictions=["US"],
            sectors=["FINANCE"],  # Regulated sector
        )

        assert recommendation.recommended_tier == ComplianceTier.ADVANCED

    def test_healthcare_triggers_advanced(self, tier_service: TierService) -> None:
        """Healthcare sector triggers ADVANCED tier."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=15,
            annual_revenue=1_000_000,
            jurisdictions=["US"],
            sectors=["HEALTHCARE"],
        )

        assert recommendation.recommended_tier == ComplianceTier.ADVANCED


# =============================================================================
# Size-Based Tier Tests
# =============================================================================


class TestSizeBasedTier:
    """Tests for size-based tier determination."""

    def test_large_employee_count_triggers_advanced(
        self, tier_service: TierService
    ) -> None:
        """Large employee count triggers ADVANCED tier."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size=None,
            employee_count=300,  # Above 250 threshold
            annual_revenue=None,
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        # Should get Advanced due to employee count
        factors = [f for f in recommendation.factors if f["factor"] == "size"]
        assert len(factors) == 1
        assert "Large entity" in factors[0]["reason"]

    def test_large_revenue_triggers_advanced(self, tier_service: TierService) -> None:
        """Large revenue triggers ADVANCED tier."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size=None,
            employee_count=None,
            annual_revenue=60_000_000,  # Above $50M threshold
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        factors = [f for f in recommendation.factors if f["factor"] == "size"]
        assert len(factors) == 1
        assert "revenue" in factors[0]["reason"].lower()

    def test_medium_employee_count(self, tier_service: TierService) -> None:
        """Medium employee count results in STANDARD tier."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size=None,
            employee_count=100,  # Between 50-249
            annual_revenue=None,
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        factors = [f for f in recommendation.factors if f["factor"] == "size"]
        assert len(factors) == 1
        assert "Medium entity" in factors[0]["reason"]


# =============================================================================
# Jurisdiction-Based Tier Tests
# =============================================================================


class TestJurisdictionBasedTier:
    """Tests for jurisdiction-based tier determination."""

    def test_multi_jurisdiction_triggers_standard(
        self, tier_service: TierService
    ) -> None:
        """Multiple jurisdictions trigger at least STANDARD tier."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US", "CA", "UK", "AU"],  # 4 jurisdictions
            sectors=["RETAIL"],
        )

        # Multi-jurisdiction should push toward STANDARD
        factors = [f for f in recommendation.factors if f["factor"] == "jurisdiction"]
        assert len(factors) == 1
        assert factors[0]["count"] == 4

    def test_regulated_jurisdictions_trigger_upgrade(
        self, tier_service: TierService
    ) -> None:
        """Presence in regulated jurisdictions triggers tier upgrade."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US", "EU"],  # Both are regulated
            sectors=["RETAIL"],
        )

        factors = [f for f in recommendation.factors if f["factor"] == "jurisdiction"]
        assert len(factors) == 1


# =============================================================================
# Risk Factor Tests
# =============================================================================


class TestRiskFactors:
    """Tests for risk factor evaluation."""

    def test_high_risk_factors_trigger_advanced(
        self, tier_service: TierService
    ) -> None:
        """High risk factors push toward ADVANCED tier."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US"],
            sectors=["RETAIL"],
            risk_factors={
                "processes_personal_data": True,
                "processes_sensitive_data": True,
                "government_contractor": True,
            },
        )

        # Risk factors should influence the recommendation
        factors = [f for f in recommendation.factors if f["factor"] == "risk_factors"]
        assert len(factors) == 1
        assert factors[0]["total_risk_score"] >= 4

    def test_government_contractor_risk(self, tier_service: TierService) -> None:
        """Government contractor status adds significant risk."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US"],
            sectors=["RETAIL"],
            risk_factors={
                "government_contractor": True,
            },
        )

        factors = [f for f in recommendation.factors if f["factor"] == "risk_factors"]
        assert len(factors) == 1
        # Government contractor adds weight of 2
        assert any(
            f["factor"] == "government_contractor" and f["weight"] == 2
            for f in factors[0].get("active_factors", [])
        )


# =============================================================================
# Risk Level Tests
# =============================================================================


class TestRiskLevel:
    """Tests for risk level determination."""

    def test_low_risk_level(self, tier_service: TierService) -> None:
        """Low-risk entity gets low risk level."""
        recommendation = tier_service.determine_tier(
            entity_type="individual",
            size="micro",
            employee_count=1,
            annual_revenue=50_000,
            jurisdictions=["US"],
            sectors=[],
        )

        assert recommendation.risk_level == RiskLevel.LOW

    def test_high_risk_level_from_factors(self, tier_service: TierService) -> None:
        """Multiple risk factors result in high risk level."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="large",
            employee_count=500,
            annual_revenue=100_000_000,
            jurisdictions=["US", "EU", "UK"],
            sectors=["FINANCE"],
            risk_factors={
                "processes_sensitive_data": True,
                "cross_border_transfers": True,
                "critical_infrastructure": True,
            },
        )

        assert recommendation.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)


# =============================================================================
# Confidence and Alternatives Tests
# =============================================================================


class TestConfidenceAndAlternatives:
    """Tests for confidence scores and alternative recommendations."""

    def test_high_confidence_for_clear_case(self, tier_service: TierService) -> None:
        """Clear cases should have high confidence."""
        # Large regulated entity - clearly ADVANCED
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="large",
            employee_count=1000,
            annual_revenue=500_000_000,
            jurisdictions=["US", "EU"],
            sectors=["FINANCE", "BANKING"],
            risk_factors={
                "processes_sensitive_data": True,
                "government_contractor": True,
            },
        )

        assert recommendation.confidence >= 0.7

    def test_alternatives_provided(self, tier_service: TierService) -> None:
        """Alternatives should be provided when applicable."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="medium",
            employee_count=100,
            annual_revenue=15_000_000,
            jurisdictions=["US"],
            sectors=["TECHNOLOGY"],
        )

        # Should have at least one alternative
        assert len(recommendation.alternatives) >= 0


# =============================================================================
# Required Capabilities Tests
# =============================================================================


class TestRequiredCapabilities:
    """Tests for required capabilities output."""

    def test_basic_tier_capabilities(self, tier_service: TierService) -> None:
        """BASIC tier has appropriate capabilities."""
        recommendation = tier_service.determine_tier(
            entity_type="individual",
            size="micro",
            employee_count=1,
            annual_revenue=50_000,
            jurisdictions=["US"],
            sectors=[],
        )

        if recommendation.recommended_tier == ComplianceTier.BASIC:
            assert "Self-attestation support" in recommendation.required_capabilities

    def test_advanced_tier_capabilities(self, tier_service: TierService) -> None:
        """ADVANCED tier includes advanced capabilities."""
        recommendation = tier_service.determine_tier(
            entity_type="corporation",
            size="large",
            employee_count=500,
            annual_revenue=100_000_000,
            jurisdictions=["US", "EU"],
            sectors=["FINANCE"],
        )

        assert recommendation.recommended_tier == ComplianceTier.ADVANCED
        assert "Continuous monitoring" in recommendation.required_capabilities
        assert "Zero-knowledge proofs" in recommendation.required_capabilities


# =============================================================================
# Upgrade Triggers Tests
# =============================================================================


class TestUpgradeTriggers:
    """Tests for upgrade trigger suggestions."""

    def test_basic_tier_upgrade_triggers(self, tier_service: TierService) -> None:
        """BASIC tier gets appropriate upgrade triggers."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        if recommendation.recommended_tier == ComplianceTier.BASIC:
            # Should suggest paths to upgrade
            assert len(recommendation.upgrade_triggers) > 0
            # Should mention employee threshold
            assert any("employee" in t.lower() for t in recommendation.upgrade_triggers)


# =============================================================================
# Cost Estimate Tests
# =============================================================================


class TestCostEstimate:
    """Tests for tier cost estimation."""

    def test_basic_tier_cost(self, tier_service: TierService) -> None:
        """BASIC tier has lowest cost."""
        estimate = tier_service.calculate_tier_cost_estimate(
            tier=ComplianceTier.BASIC,
            requirement_count=50,
        )

        assert estimate["base_cost"] == 5000
        assert estimate["requirement_cost"] == 50 * 50  # 50 reqs * $50
        assert estimate["total_estimate"] == 5000 + 2500

    def test_advanced_tier_cost(self, tier_service: TierService) -> None:
        """ADVANCED tier has highest cost."""
        estimate = tier_service.calculate_tier_cost_estimate(
            tier=ComplianceTier.ADVANCED,
            requirement_count=100,
        )

        assert estimate["base_cost"] == 100000
        assert estimate["requirement_cost"] == 100 * 400  # 100 reqs * $400
        assert estimate["total_estimate"] == 100000 + 40000

    def test_cost_scales_with_requirements(self, tier_service: TierService) -> None:
        """Cost increases with more requirements."""
        estimate_50 = tier_service.calculate_tier_cost_estimate(
            tier=ComplianceTier.STANDARD,
            requirement_count=50,
        )

        estimate_100 = tier_service.calculate_tier_cost_estimate(
            tier=ComplianceTier.STANDARD,
            requirement_count=100,
        )

        assert estimate_100["total_estimate"] > estimate_50["total_estimate"]
        assert estimate_100["requirement_cost"] == 2 * estimate_50["requirement_cost"]


# =============================================================================
# Custom Criteria Tests
# =============================================================================


class TestCustomCriteria:
    """Tests for custom tier criteria."""

    def test_custom_employee_threshold(self, custom_tier_service: TierService) -> None:
        """Custom employee threshold works correctly."""
        # With custom threshold of 100, 150 employees should be ADVANCED
        recommendation = custom_tier_service.determine_tier(
            entity_type="corporation",
            size=None,
            employee_count=150,
            annual_revenue=None,
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        factors = [f for f in recommendation.factors if f["factor"] == "size"]
        assert len(factors) == 1
        assert "Large entity" in factors[0]["reason"]

    def test_custom_jurisdiction_threshold(
        self, custom_tier_service: TierService
    ) -> None:
        """Custom jurisdiction threshold works correctly."""
        # With custom threshold of 2, 3 jurisdictions should trigger upgrade
        recommendation = custom_tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US", "CA", "UK"],  # 3 jurisdictions
            sectors=["RETAIL"],
        )

        factors = [f for f in recommendation.factors if f["factor"] == "jurisdiction"]
        assert len(factors) == 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_jurisdictions(self, tier_service: TierService) -> None:
        """Empty jurisdictions list doesn't crash."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=[],
            sectors=["RETAIL"],
        )

        assert recommendation.recommended_tier is not None

    def test_empty_sectors(self, tier_service: TierService) -> None:
        """Empty sectors list doesn't crash."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US"],
            sectors=[],
        )

        assert recommendation.recommended_tier is not None

    def test_none_values(self, tier_service: TierService) -> None:
        """None values are handled gracefully."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size=None,
            employee_count=None,
            annual_revenue=None,
            jurisdictions=["US"],
            sectors=["RETAIL"],
        )

        assert recommendation.recommended_tier is not None

    def test_case_insensitive_sectors(self, tier_service: TierService) -> None:
        """Sector matching is case-insensitive."""
        recommendation = tier_service.determine_tier(
            entity_type="sme",
            size="small",
            employee_count=10,
            annual_revenue=500_000,
            jurisdictions=["US"],
            sectors=["finance"],  # Lowercase
        )

        # Should still detect as regulated sector
        assert recommendation.recommended_tier == ComplianceTier.ADVANCED

