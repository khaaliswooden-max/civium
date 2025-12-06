"""
Tier Assignment Service
=======================

Automatic compliance tier assignment based on entity characteristics.

Tier Criteria:
- BASIC: Small entities, single jurisdiction, low-risk sectors
- STANDARD: Medium entities, multiple jurisdictions, moderate-risk sectors
- ADVANCED: Large entities, regulated sectors, high-risk profile

Version: 0.1.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from shared.logging import get_logger


logger = get_logger(__name__)


class ComplianceTier(str, Enum):
    """Compliance complexity tiers."""

    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class RiskLevel(str, Enum):
    """Entity risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# Tier Criteria Configuration
# =============================================================================


@dataclass
class TierCriteria:
    """Criteria used for tier determination."""

    # Size thresholds
    large_employee_count: int = 250
    medium_employee_count: int = 50
    small_employee_count: int = 10

    large_revenue: float = 50_000_000  # $50M
    medium_revenue: float = 10_000_000  # $10M

    # High-risk sectors requiring ADVANCED tier
    advanced_sectors: set[str] = field(
        default_factory=lambda: {
            "FINANCE",
            "BANKING",
            "INSURANCE",
            "HEALTHCARE",
            "PHARMACEUTICALS",
            "DEFENSE",
            "GOVERNMENT",
            "CRITICAL_INFRASTRUCTURE",
            "ENERGY",
            "NUCLEAR",
        }
    )

    # Standard-risk sectors requiring at least STANDARD tier
    standard_sectors: set[str] = field(
        default_factory=lambda: {
            "TECHNOLOGY",
            "TELECOMMUNICATIONS",
            "MANUFACTURING",
            "TRANSPORT",
            "LOGISTICS",
            "RETAIL",
            "REAL_ESTATE",
        }
    )

    # High-risk jurisdictions requiring ADVANCED tier
    advanced_jurisdictions: set[str] = field(
        default_factory=lambda: {
            "US",  # Heavy regulatory environment
            "EU",  # GDPR and other regulations
            "UK",  # Post-Brexit regulations
            "SG",  # Financial hub
            "HK",  # Financial hub
        }
    )

    # Number of jurisdictions that triggers tier upgrade
    multi_jurisdiction_threshold: int = 3

    # Risk factors that trigger tier upgrade
    risk_factors: dict[str, int] = field(
        default_factory=lambda: {
            "processes_personal_data": 1,
            "processes_sensitive_data": 2,
            "cross_border_transfers": 1,
            "government_contractor": 2,
            "publicly_traded": 1,
            "critical_infrastructure": 2,
            "handles_minors_data": 2,
            "automated_decision_making": 1,
        }
    )


@dataclass
class TierRecommendation:
    """Result of tier determination."""

    recommended_tier: ComplianceTier
    confidence: float  # 0.0 to 1.0
    risk_level: RiskLevel

    # Factors that influenced the decision
    factors: list[dict[str, Any]] = field(default_factory=list)

    # Alternative tiers considered
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    # Required capabilities for recommended tier
    required_capabilities: list[str] = field(default_factory=list)

    # Upgrade path if entity grows
    upgrade_triggers: list[str] = field(default_factory=list)


# =============================================================================
# Tier Service
# =============================================================================


class TierService:
    """
    Service for determining entity compliance tiers.

    Uses a multi-factor scoring system to recommend the appropriate
    compliance tier based on:
    - Entity size (employees, revenue)
    - Geographic scope (jurisdictions)
    - Industry sector
    - Risk profile
    - Regulatory exposure
    """

    def __init__(self, criteria: TierCriteria | None = None) -> None:
        """
        Initialize the tier service.

        Args:
            criteria: Custom tier criteria (uses defaults if not provided)
        """
        self.criteria = criteria or TierCriteria()

    def determine_tier(
        self,
        entity_type: str,
        size: str | None,
        employee_count: int | None,
        annual_revenue: float | None,
        jurisdictions: list[str],
        sectors: list[str],
        risk_factors: dict[str, bool] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TierRecommendation:
        """
        Determine the appropriate compliance tier for an entity.

        Args:
            entity_type: Type of entity (corporation, sme, etc.)
            size: Size category (micro, small, medium, large)
            employee_count: Number of employees
            annual_revenue: Annual revenue
            jurisdictions: List of jurisdiction codes
            sectors: List of sector codes
            risk_factors: Additional risk factors
            metadata: Additional entity metadata

        Returns:
            TierRecommendation with recommended tier and rationale
        """
        factors: list[dict[str, Any]] = []
        tier_scores = {
            ComplianceTier.BASIC: 0,
            ComplianceTier.STANDARD: 0,
            ComplianceTier.ADVANCED: 0,
        }

        risk_score = 0.0
        max_risk_score = 10.0  # Normalization factor

        # =================================================================
        # Factor 1: Entity Size
        # =================================================================
        size_tier, size_factor = self._evaluate_size(size, employee_count, annual_revenue)
        tier_scores[size_tier] += 2
        factors.append(size_factor)
        if size_tier == ComplianceTier.ADVANCED:
            risk_score += 2

        # =================================================================
        # Factor 2: Sector Risk
        # =================================================================
        sector_tier, sector_factor, sector_risk = self._evaluate_sectors(sectors)
        tier_scores[sector_tier] += 3  # Higher weight for sector
        factors.append(sector_factor)
        risk_score += sector_risk

        # =================================================================
        # Factor 3: Geographic Scope
        # =================================================================
        geo_tier, geo_factor, geo_risk = self._evaluate_jurisdictions(jurisdictions)
        tier_scores[geo_tier] += 2
        factors.append(geo_factor)
        risk_score += geo_risk

        # =================================================================
        # Factor 4: Entity Type
        # =================================================================
        type_tier, type_factor = self._evaluate_entity_type(entity_type)
        tier_scores[type_tier] += 1
        factors.append(type_factor)

        # =================================================================
        # Factor 5: Risk Factors
        # =================================================================
        if risk_factors:
            rf_tier, rf_factor, rf_risk = self._evaluate_risk_factors(risk_factors)
            tier_scores[rf_tier] += 2
            factors.append(rf_factor)
            risk_score += rf_risk

        # =================================================================
        # Determine Final Tier
        # =================================================================

        # Find the tier with highest score
        recommended_tier = max(tier_scores, key=tier_scores.get)  # type: ignore[arg-type]

        # Calculate confidence based on score difference
        scores = sorted(tier_scores.values(), reverse=True)
        if scores[0] > 0:
            score_gap = (scores[0] - scores[1]) / scores[0]
            confidence = 0.5 + (score_gap * 0.5)  # 0.5 to 1.0
        else:
            confidence = 0.5

        # Determine risk level
        normalized_risk = risk_score / max_risk_score
        if normalized_risk >= 0.7:
            risk_level = RiskLevel.CRITICAL
        elif normalized_risk >= 0.5:
            risk_level = RiskLevel.HIGH
        elif normalized_risk >= 0.25:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Build required capabilities
        required_capabilities = self._get_required_capabilities(recommended_tier)

        # Build upgrade triggers
        upgrade_triggers = self._get_upgrade_triggers(recommended_tier, factors)

        # Build alternatives
        alternatives = [
            {
                "tier": tier.value,
                "score": score,
                "reason": "Alternative based on scoring",
            }
            for tier, score in tier_scores.items()
            if tier != recommended_tier and score > 0
        ]

        recommendation = TierRecommendation(
            recommended_tier=recommended_tier,
            confidence=round(confidence, 2),
            risk_level=risk_level,
            factors=factors,
            alternatives=alternatives,
            required_capabilities=required_capabilities,
            upgrade_triggers=upgrade_triggers,
        )

        logger.info(
            "tier_determined",
            tier=recommended_tier.value,
            confidence=confidence,
            risk_level=risk_level.value,
            factor_count=len(factors),
        )

        return recommendation

    def _evaluate_size(
        self,
        size: str | None,
        employee_count: int | None,
        annual_revenue: float | None,
    ) -> tuple[ComplianceTier, dict[str, Any]]:
        """Evaluate entity size for tier determination."""
        tier = ComplianceTier.BASIC
        reason = "Default small entity"

        # Check employee count
        if employee_count is not None:
            if employee_count >= self.criteria.large_employee_count:
                tier = ComplianceTier.ADVANCED
                reason = f"Large entity ({employee_count} employees)"
            elif employee_count >= self.criteria.medium_employee_count:
                tier = ComplianceTier.STANDARD
                reason = f"Medium entity ({employee_count} employees)"
            else:
                tier = ComplianceTier.BASIC
                reason = f"Small entity ({employee_count} employees)"

        # Check revenue (can override employee count)
        if annual_revenue is not None:
            if annual_revenue >= self.criteria.large_revenue:
                if tier != ComplianceTier.ADVANCED:
                    tier = ComplianceTier.ADVANCED
                    reason = f"Large revenue (${annual_revenue:,.0f})"
            elif annual_revenue >= self.criteria.medium_revenue:
                if tier == ComplianceTier.BASIC:
                    tier = ComplianceTier.STANDARD
                    reason = f"Medium revenue (${annual_revenue:,.0f})"

        # Check size category as fallback
        if size and employee_count is None and annual_revenue is None:
            if size.lower() == "large":
                tier = ComplianceTier.ADVANCED
                reason = "Large size category"
            elif size.lower() == "medium":
                tier = ComplianceTier.STANDARD
                reason = "Medium size category"

        return tier, {
            "factor": "size",
            "tier": tier.value,
            "reason": reason,
            "employee_count": employee_count,
            "annual_revenue": annual_revenue,
        }

    def _evaluate_sectors(
        self,
        sectors: list[str],
    ) -> tuple[ComplianceTier, dict[str, Any], float]:
        """Evaluate sectors for tier determination."""
        if not sectors:
            return (
                ComplianceTier.BASIC,
                {
                    "factor": "sector",
                    "tier": "basic",
                    "reason": "No sectors specified",
                },
                0.0,
            )

        sectors_upper = {s.upper() for s in sectors}

        # Check for advanced sectors
        advanced_matches = sectors_upper & self.criteria.advanced_sectors
        if advanced_matches:
            return (
                ComplianceTier.ADVANCED,
                {
                    "factor": "sector",
                    "tier": "advanced",
                    "reason": f"Regulated sectors: {', '.join(advanced_matches)}",
                    "matched_sectors": list(advanced_matches),
                },
                3.0,
            )

        # Check for standard sectors
        standard_matches = sectors_upper & self.criteria.standard_sectors
        if standard_matches:
            return (
                ComplianceTier.STANDARD,
                {
                    "factor": "sector",
                    "tier": "standard",
                    "reason": f"Standard-risk sectors: {', '.join(standard_matches)}",
                    "matched_sectors": list(standard_matches),
                },
                1.5,
            )

        return (
            ComplianceTier.BASIC,
            {
                "factor": "sector",
                "tier": "basic",
                "reason": "Low-risk sectors",
                "sectors": sectors,
            },
            0.5,
        )

    def _evaluate_jurisdictions(
        self,
        jurisdictions: list[str],
    ) -> tuple[ComplianceTier, dict[str, Any], float]:
        """Evaluate jurisdictions for tier determination."""
        if not jurisdictions:
            return (
                ComplianceTier.BASIC,
                {
                    "factor": "jurisdiction",
                    "tier": "basic",
                    "reason": "No jurisdictions specified",
                },
                0.0,
            )

        jurisdictions_upper = {j.upper() for j in jurisdictions}
        num_jurisdictions = len(jurisdictions_upper)

        # Check for advanced jurisdictions
        advanced_matches = jurisdictions_upper & self.criteria.advanced_jurisdictions
        if advanced_matches and len(advanced_matches) >= 2:
            return (
                ComplianceTier.ADVANCED,
                {
                    "factor": "jurisdiction",
                    "tier": "advanced",
                    "reason": f"Multiple regulated jurisdictions: {', '.join(advanced_matches)}",
                    "count": num_jurisdictions,
                },
                2.5,
            )

        # Check for multi-jurisdiction
        if num_jurisdictions >= self.criteria.multi_jurisdiction_threshold:
            return (
                ComplianceTier.STANDARD,
                {
                    "factor": "jurisdiction",
                    "tier": "standard",
                    "reason": f"Multi-jurisdictional ({num_jurisdictions} jurisdictions)",
                    "count": num_jurisdictions,
                },
                1.5,
            )

        # Single advanced jurisdiction
        if advanced_matches:
            return (
                ComplianceTier.STANDARD,
                {
                    "factor": "jurisdiction",
                    "tier": "standard",
                    "reason": f"Regulated jurisdiction: {', '.join(advanced_matches)}",
                    "count": num_jurisdictions,
                },
                1.0,
            )

        return (
            ComplianceTier.BASIC,
            {
                "factor": "jurisdiction",
                "tier": "basic",
                "reason": f"Single jurisdiction: {jurisdictions[0]}",
                "count": num_jurisdictions,
            },
            0.5,
        )

    def _evaluate_entity_type(
        self,
        entity_type: str,
    ) -> tuple[ComplianceTier, dict[str, Any]]:
        """Evaluate entity type for tier determination."""
        type_lower = entity_type.lower()

        if type_lower == "government":
            return ComplianceTier.ADVANCED, {
                "factor": "entity_type",
                "tier": "advanced",
                "reason": "Government entity",
                "type": entity_type,
            }

        if type_lower in ("corporation", "subsidiary"):
            return ComplianceTier.STANDARD, {
                "factor": "entity_type",
                "tier": "standard",
                "reason": "Corporate entity",
                "type": entity_type,
            }

        if type_lower in ("sme", "startup"):
            return ComplianceTier.BASIC, {
                "factor": "entity_type",
                "tier": "basic",
                "reason": "Small/startup entity",
                "type": entity_type,
            }

        return ComplianceTier.BASIC, {
            "factor": "entity_type",
            "tier": "basic",
            "reason": f"Entity type: {entity_type}",
            "type": entity_type,
        }

    def _evaluate_risk_factors(
        self,
        risk_factors: dict[str, bool],
    ) -> tuple[ComplianceTier, dict[str, Any], float]:
        """Evaluate additional risk factors."""
        total_risk = 0
        active_factors = []

        for factor, is_active in risk_factors.items():
            if is_active and factor in self.criteria.risk_factors:
                factor_weight = self.criteria.risk_factors[factor]
                total_risk += factor_weight
                active_factors.append(
                    {
                        "factor": factor,
                        "weight": factor_weight,
                    }
                )

        if total_risk >= 4:
            tier = ComplianceTier.ADVANCED
        elif total_risk >= 2:
            tier = ComplianceTier.STANDARD
        else:
            tier = ComplianceTier.BASIC

        return (
            tier,
            {
                "factor": "risk_factors",
                "tier": tier.value,
                "reason": f"{len(active_factors)} risk factors active",
                "total_risk_score": total_risk,
                "active_factors": active_factors,
            },
            float(total_risk),
        )

    def _get_required_capabilities(
        self,
        tier: ComplianceTier,
    ) -> list[str]:
        """Get required capabilities for a tier."""
        capabilities = {
            ComplianceTier.BASIC: [
                "Self-attestation support",
                "Basic document management",
                "Annual assessment cycle",
            ],
            ComplianceTier.STANDARD: [
                "Document review workflows",
                "Quarterly assessment cycle",
                "Evidence management",
                "Multi-jurisdiction tracking",
                "Risk scoring",
            ],
            ComplianceTier.ADVANCED: [
                "Continuous monitoring",
                "Real-time compliance tracking",
                "Automated evidence collection",
                "Third-party audit support",
                "Zero-knowledge proofs",
                "Cryptographic attestations",
                "Advanced analytics",
            ],
        }

        return capabilities.get(tier, [])

    def _get_upgrade_triggers(
        self,
        current_tier: ComplianceTier,
        factors: list[dict[str, Any]],
    ) -> list[str]:
        """Get triggers that would cause a tier upgrade."""
        triggers = []

        if current_tier == ComplianceTier.BASIC:
            triggers.extend(
                [
                    f"Reach {self.criteria.medium_employee_count}+ employees",
                    f"Exceed ${self.criteria.medium_revenue:,.0f} annual revenue",
                    f"Expand to {self.criteria.multi_jurisdiction_threshold}+ jurisdictions",
                    "Enter regulated sector (Finance, Healthcare, etc.)",
                ]
            )
        elif current_tier == ComplianceTier.STANDARD:
            triggers.extend(
                [
                    f"Reach {self.criteria.large_employee_count}+ employees",
                    f"Exceed ${self.criteria.large_revenue:,.0f} annual revenue",
                    "Expand to multiple regulated jurisdictions",
                    "Process sensitive personal data",
                    "Become government contractor",
                ]
            )

        return triggers

    def calculate_tier_cost_estimate(
        self,
        tier: ComplianceTier,
        requirement_count: int,
    ) -> dict[str, Any]:
        """
        Estimate compliance cost for a tier.

        Args:
            tier: Compliance tier
            requirement_count: Number of applicable requirements

        Returns:
            Cost estimate breakdown
        """
        # Base costs per tier (annual)
        base_costs = {
            ComplianceTier.BASIC: 5000,
            ComplianceTier.STANDARD: 25000,
            ComplianceTier.ADVANCED: 100000,
        }

        # Cost per requirement per tier
        per_requirement = {
            ComplianceTier.BASIC: 50,
            ComplianceTier.STANDARD: 150,
            ComplianceTier.ADVANCED: 400,
        }

        base = base_costs.get(tier, 5000)
        req_cost = per_requirement.get(tier, 50) * requirement_count

        return {
            "tier": tier.value,
            "base_cost": base,
            "requirement_cost": req_cost,
            "total_estimate": base + req_cost,
            "requirement_count": requirement_count,
            "notes": "Estimate only - actual costs vary based on specifics",
        }
