//! Poseidon hash implementation compatible with circomlib

use ark_bn254::Fr;
use ark_ff::PrimeField;
use num_bigint::BigUint;
use num_traits::Num;
use poseidon_rs::{Fr as PoseidonFr, Poseidon};

use crate::error::{ProverError, Result};

/// Poseidon hasher compatible with circomlib circuits
pub struct PoseidonHasher {
    hasher: Poseidon,
}

impl Default for PoseidonHasher {
    fn default() -> Self {
        Self::new()
    }
}

impl PoseidonHasher {
    /// Create a new Poseidon hasher
    pub fn new() -> Self {
        Self {
            hasher: Poseidon::new(),
        }
    }

    /// Hash inputs using Poseidon
    pub fn hash(&self, inputs: &[Fr]) -> Result<Fr> {
        // Convert arkworks Fr to poseidon-rs Fr
        let poseidon_inputs: Vec<PoseidonFr> = inputs
            .iter()
            .map(|f| {
                let bytes = f.to_string();
                PoseidonFr::from_str(&bytes).map_err(|e| ProverError::ArkError(e.to_string()))
            })
            .collect::<Result<Vec<_>>>()?;

        // Compute hash
        let result = self
            .hasher
            .hash(poseidon_inputs)
            .map_err(|e| ProverError::ArkError(e.to_string()))?;

        // Convert back to arkworks Fr
        let result_str = result.to_string();
        let result_biguint = BigUint::from_str_radix(&result_str, 10)
            .map_err(|e| ProverError::ArkError(e.to_string()))?;

        Fr::from_be_bytes_mod_order(&result_biguint.to_bytes_be())
            .try_into()
            .map_err(|_| ProverError::ArkError("Field element conversion failed".into()))
    }

    /// Compute score commitment: Poseidon(score, salt, entityHash)
    pub fn compute_commitment(&self, score: u64, salt: &Fr, entity_hash: &Fr) -> Result<Fr> {
        let score_fr = Fr::from(score);
        self.hash(&[score_fr, *salt, *entity_hash])
    }
}

/// Convert a decimal string to Fr
pub fn string_to_fr(s: &str) -> Result<Fr> {
    let biguint = BigUint::from_str_radix(s, 10)
        .map_err(|e| ProverError::ArkError(format!("Invalid number: {e}")))?;
    
    Ok(Fr::from_be_bytes_mod_order(&biguint.to_bytes_be()))
}

/// Convert Fr to decimal string
pub fn fr_to_string(f: &Fr) -> String {
    f.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_poseidon_hash() {
        let hasher = PoseidonHasher::new();

        // Test with known values
        let input1 = Fr::from(1u64);
        let input2 = Fr::from(2u64);

        let hash = hasher.hash(&[input1, input2]).unwrap();

        // Verify hash is deterministic
        let hash2 = hasher.hash(&[input1, input2]).unwrap();
        assert_eq!(hash, hash2);
    }

    #[test]
    fn test_commitment() {
        let hasher = PoseidonHasher::new();

        let score = 8500u64;
        let salt = Fr::from(123456789u64);
        let entity_hash = Fr::from(987654321u64);

        let commitment = hasher.compute_commitment(score, &salt, &entity_hash).unwrap();

        // Verify deterministic
        let commitment2 = hasher.compute_commitment(score, &salt, &entity_hash).unwrap();
        assert_eq!(commitment, commitment2);

        // Different inputs -> different commitment
        let commitment3 = hasher.compute_commitment(score + 1, &salt, &entity_hash).unwrap();
        assert_ne!(commitment, commitment3);
    }
}

