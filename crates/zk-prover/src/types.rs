//! Input types for ZK-SNARK circuits

use num_bigint::BigUint;
use serde::{Deserialize, Serialize};

/// Maximum valid score (1.0000 in fixed-point)
pub const MAX_SCORE: u64 = 10000;

/// Tier boundaries for compliance levels
pub mod tiers {
    /// Critical compliance tier (>= 95%)
    pub const TIER_1_MIN: u64 = 9500;
    /// High compliance tier (>= 85%)
    pub const TIER_2_MIN: u64 = 8500;
    /// Standard compliance tier (>= 70%)
    pub const TIER_3_MIN: u64 = 7000;
    /// Basic compliance tier (>= 50%)
    pub const TIER_4_MIN: u64 = 5000;
    /// Minimal compliance tier (< 50%)
    pub const TIER_5_MIN: u64 = 0;
}

/// Input for compliance threshold proof
///
/// Proves: score >= threshold
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThresholdInput {
    /// Minimum required score (0-10000, public)
    pub threshold: u64,
    /// Hash of entity identifier (public)
    pub entity_hash: String,
    /// Actual compliance score (private)
    pub score: u64,
    /// Random salt for commitment (private)
    pub salt: String,
}

impl ThresholdInput {
    /// Validate input values
    pub fn validate(&self) -> Result<(), crate::ProverError> {
        if self.score > MAX_SCORE {
            return Err(crate::ProverError::ScoreOutOfRange { score: self.score });
        }
        if self.threshold > MAX_SCORE {
            return Err(crate::ProverError::InvalidInput {
                field: "threshold".into(),
                value: self.threshold.to_string(),
                expected: format!("0-{MAX_SCORE}"),
            });
        }
        if self.score < self.threshold {
            return Err(crate::ProverError::ThresholdNotMet {
                score: self.score,
                threshold: self.threshold,
            });
        }
        Ok(())
    }

    /// Convert to circuit input format
    pub fn to_circuit_input(&self) -> Vec<(String, Vec<BigUint>)> {
        vec![
            ("threshold".into(), vec![BigUint::from(self.threshold)]),
            (
                "entityHash".into(),
                vec![BigUint::parse_bytes(self.entity_hash.as_bytes(), 10)
                    .unwrap_or_else(|| BigUint::from(0u64))],
            ),
            ("score".into(), vec![BigUint::from(self.score)]),
            (
                "salt".into(),
                vec![BigUint::parse_bytes(self.salt.as_bytes(), 10)
                    .unwrap_or_else(|| BigUint::from(0u64))],
            ),
        ]
    }
}

/// Input for compliance range proof
///
/// Proves: min_score <= score <= max_score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RangeInput {
    /// Minimum of range (inclusive, public)
    pub min_score: u64,
    /// Maximum of range (inclusive, public)
    pub max_score: u64,
    /// Hash of entity identifier (public)
    pub entity_hash: String,
    /// Actual compliance score (private)
    pub score: u64,
    /// Random salt for commitment (private)
    pub salt: String,
}

impl RangeInput {
    /// Validate input values
    pub fn validate(&self) -> Result<(), crate::ProverError> {
        if self.score > MAX_SCORE {
            return Err(crate::ProverError::ScoreOutOfRange { score: self.score });
        }
        if self.min_score > self.max_score {
            return Err(crate::ProverError::InvalidInput {
                field: "min_score".into(),
                value: self.min_score.to_string(),
                expected: format!("<= max_score ({})", self.max_score),
            });
        }
        if self.score < self.min_score || self.score > self.max_score {
            return Err(crate::ProverError::InvalidInput {
                field: "score".into(),
                value: self.score.to_string(),
                expected: format!("[{}, {}]", self.min_score, self.max_score),
            });
        }
        Ok(())
    }

    /// Convert to circuit input format
    pub fn to_circuit_input(&self) -> Vec<(String, Vec<BigUint>)> {
        vec![
            ("minScore".into(), vec![BigUint::from(self.min_score)]),
            ("maxScore".into(), vec![BigUint::from(self.max_score)]),
            (
                "entityHash".into(),
                vec![BigUint::parse_bytes(self.entity_hash.as_bytes(), 10)
                    .unwrap_or_else(|| BigUint::from(0u64))],
            ),
            ("score".into(), vec![BigUint::from(self.score)]),
            (
                "salt".into(),
                vec![BigUint::parse_bytes(self.salt.as_bytes(), 10)
                    .unwrap_or_else(|| BigUint::from(0u64))],
            ),
        ]
    }
}

/// Input for tier membership proof
///
/// Proves: entity belongs to specified compliance tier
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TierInput {
    /// Target tier (1-5, public)
    pub target_tier: u8,
    /// Hash of entity identifier (public)
    pub entity_hash: String,
    /// Actual compliance score (private)
    pub score: u64,
    /// Random salt for commitment (private)
    pub salt: String,
}

impl TierInput {
    /// Validate input values
    pub fn validate(&self) -> Result<(), crate::ProverError> {
        if self.target_tier < 1 || self.target_tier > 5 {
            return Err(crate::ProverError::InvalidTier {
                tier: self.target_tier,
            });
        }
        if self.score > MAX_SCORE {
            return Err(crate::ProverError::ScoreOutOfRange { score: self.score });
        }

        // Check score matches tier
        let (min, max) = Self::tier_bounds(self.target_tier);
        if self.score < min || self.score > max {
            return Err(crate::ProverError::InvalidInput {
                field: "score".into(),
                value: self.score.to_string(),
                expected: format!("tier {} range [{}, {}]", self.target_tier, min, max),
            });
        }
        Ok(())
    }

    /// Get tier boundaries
    pub fn tier_bounds(tier: u8) -> (u64, u64) {
        match tier {
            1 => (tiers::TIER_1_MIN, MAX_SCORE),
            2 => (tiers::TIER_2_MIN, tiers::TIER_1_MIN - 1),
            3 => (tiers::TIER_3_MIN, tiers::TIER_2_MIN - 1),
            4 => (tiers::TIER_4_MIN, tiers::TIER_3_MIN - 1),
            5 => (tiers::TIER_5_MIN, tiers::TIER_4_MIN - 1),
            _ => (0, 0),
        }
    }

    /// Convert to circuit input format
    pub fn to_circuit_input(&self) -> Vec<(String, Vec<BigUint>)> {
        vec![
            ("targetTier".into(), vec![BigUint::from(self.target_tier)]),
            (
                "entityHash".into(),
                vec![BigUint::parse_bytes(self.entity_hash.as_bytes(), 10)
                    .unwrap_or_else(|| BigUint::from(0u64))],
            ),
            ("score".into(), vec![BigUint::from(self.score)]),
            (
                "salt".into(),
                vec![BigUint::parse_bytes(self.salt.as_bytes(), 10)
                    .unwrap_or_else(|| BigUint::from(0u64))],
            ),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_threshold_validation() {
        let valid = ThresholdInput {
            threshold: 8000,
            entity_hash: "123456789".into(),
            score: 8500,
            salt: "987654321".into(),
        };
        assert!(valid.validate().is_ok());

        let invalid_score = ThresholdInput {
            threshold: 8000,
            entity_hash: "123456789".into(),
            score: 15000, // Invalid: > 10000
            salt: "987654321".into(),
        };
        assert!(invalid_score.validate().is_err());

        let threshold_not_met = ThresholdInput {
            threshold: 8000,
            entity_hash: "123456789".into(),
            score: 7500, // Invalid: < threshold
            salt: "987654321".into(),
        };
        assert!(threshold_not_met.validate().is_err());
    }

    #[test]
    fn test_tier_bounds() {
        assert_eq!(TierInput::tier_bounds(1), (9500, 10000));
        assert_eq!(TierInput::tier_bounds(2), (8500, 9499));
        assert_eq!(TierInput::tier_bounds(3), (7000, 8499));
        assert_eq!(TierInput::tier_bounds(4), (5000, 6999));
        assert_eq!(TierInput::tier_bounds(5), (0, 4999));
    }
}

