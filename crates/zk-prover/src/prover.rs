//! ZK-SNARK proof generation

use std::path::Path;
use std::fs;
use std::time::Instant;

use ark_bn254::{Bn254, Fr};
use ark_circom::{CircomBuilder, CircomConfig};
use ark_groth16::{Groth16, ProvingKey};
use ark_snark::SNARK;
use ark_std::rand::thread_rng;
use num_bigint::BigUint;
use tracing::{debug, info, instrument};

use crate::error::{ProverError, Result};
use crate::proof::{Proof, ProofWithPublicInputs};
use crate::types::{RangeInput, ThresholdInput, TierInput};

/// Circuit identifiers
pub enum Circuit {
    /// Compliance threshold proof
    Threshold,
    /// Range proof
    Range,
    /// Tier membership proof
    Tier,
}

impl Circuit {
    /// Get circuit file name
    pub fn file_name(&self) -> &str {
        match self {
            Self::Threshold => "compliance_threshold",
            Self::Range => "range_proof",
            Self::Tier => "tier_membership",
        }
    }
}

/// High-performance ZK-SNARK prover for compliance verification
pub struct ComplianceProver {
    /// Base path to circuit build directory
    build_dir: String,
    /// Cached proving keys
    threshold_pk: Option<ProvingKey<Bn254>>,
    range_pk: Option<ProvingKey<Bn254>>,
    tier_pk: Option<ProvingKey<Bn254>>,
}

impl ComplianceProver {
    /// Create a new prover with the given circuit build directory
    pub fn new(build_dir: impl AsRef<str>) -> Result<Self> {
        let build_dir = build_dir.as_ref().to_string();
        
        if !Path::new(&build_dir).exists() {
            return Err(ProverError::CircuitNotFound {
                path: build_dir,
            });
        }

        Ok(Self {
            build_dir,
            threshold_pk: None,
            range_pk: None,
            tier_pk: None,
        })
    }

    /// Load proving key for a circuit
    fn load_proving_key(&self, circuit: &Circuit) -> Result<ProvingKey<Bn254>> {
        let name = circuit.file_name();
        let zkey_path = format!("{}/{}/proving_key.zkey", self.build_dir, name);

        if !Path::new(&zkey_path).exists() {
            return Err(ProverError::CircuitNotFound { path: zkey_path });
        }

        debug!("Loading proving key from: {}", zkey_path);

        let zkey_data = fs::read(&zkey_path)?;
        
        // Parse snarkjs zkey format
        // Note: In production, use ark-circom's zkey parser
        let pk = Self::parse_zkey(&zkey_data)?;
        
        Ok(pk)
    }

    /// Parse snarkjs zkey file format
    fn parse_zkey(_data: &[u8]) -> Result<ProvingKey<Bn254>> {
        // In production, use ark-circom's built-in zkey parser
        // For now, return a placeholder error indicating setup is needed
        Err(ProverError::SetupError {
            reason: "ZKey parsing not implemented - use CircomBuilder for full integration".into(),
        })
    }

    /// Build circuit with inputs and generate proof
    #[instrument(skip(self, inputs), fields(circuit = %circuit.file_name()))]
    fn build_and_prove(
        &self,
        circuit: &Circuit,
        inputs: Vec<(String, Vec<BigUint>)>,
    ) -> Result<ProofWithPublicInputs> {
        let name = circuit.file_name();
        let wasm_path = format!("{}/{}/{}_js/{}.wasm", self.build_dir, name, name, name);
        let r1cs_path = format!("{}/{}/{}.r1cs", self.build_dir, name, name);

        // Verify files exist
        if !Path::new(&wasm_path).exists() {
            return Err(ProverError::CircuitNotFound {
                path: wasm_path,
            });
        }

        info!("Building circuit: {}", name);
        let start = Instant::now();

        // Configure circuit
        let cfg = CircomConfig::<Bn254>::new(&wasm_path, &r1cs_path)
            .map_err(|e| ProverError::SetupError {
                reason: e.to_string(),
            })?;

        // Build circuit with inputs
        let mut builder = CircomBuilder::new(cfg);
        
        for (signal_name, values) in inputs {
            builder.push_input(&signal_name, values);
        }

        let circuit = builder.build()
            .map_err(|e| ProverError::WitnessError {
                reason: e.to_string(),
            })?;

        let witness_time = start.elapsed();
        debug!("Witness generated in {:?}", witness_time);

        // Generate proof
        let prove_start = Instant::now();
        let mut rng = thread_rng();

        let (pk, _vk) = Groth16::<Bn254>::circuit_specific_setup(circuit.clone(), &mut rng)
            .map_err(|e| ProverError::SetupError {
                reason: e.to_string(),
            })?;

        let proof = Groth16::<Bn254>::prove(&pk, circuit.clone(), &mut rng)
            .map_err(|e| ProverError::ProofGenerationFailed {
                reason: e.to_string(),
            })?;

        let prove_time = prove_start.elapsed();
        let total_time = start.elapsed();

        info!(
            "Proof generated - witness: {:?}, prove: {:?}, total: {:?}",
            witness_time, prove_time, total_time
        );

        // Extract public inputs
        let public_inputs = circuit.get_public_inputs()
            .ok_or_else(|| ProverError::WitnessError {
                reason: "Failed to extract public inputs".into(),
            })?;

        Ok(ProofWithPublicInputs::new(
            Proof::new(proof),
            public_inputs,
            name.to_string(),
        ))
    }

    /// Generate a threshold compliance proof
    ///
    /// Proves that `score >= threshold` without revealing the score.
    #[instrument(skip(self, input))]
    pub fn prove_threshold(&self, input: &ThresholdInput) -> Result<ProofWithPublicInputs> {
        // Validate input
        input.validate()?;

        info!(
            "Generating threshold proof: score >= {}, entity_hash prefix: {}...",
            input.threshold,
            &input.entity_hash[..8.min(input.entity_hash.len())]
        );

        self.build_and_prove(&Circuit::Threshold, input.to_circuit_input())
    }

    /// Generate a range compliance proof
    ///
    /// Proves that `min_score <= score <= max_score` without revealing the score.
    #[instrument(skip(self, input))]
    pub fn prove_range(&self, input: &RangeInput) -> Result<ProofWithPublicInputs> {
        input.validate()?;

        info!(
            "Generating range proof: {} <= score <= {}, entity_hash prefix: {}...",
            input.min_score,
            input.max_score,
            &input.entity_hash[..8.min(input.entity_hash.len())]
        );

        self.build_and_prove(&Circuit::Range, input.to_circuit_input())
    }

    /// Generate a tier membership proof
    ///
    /// Proves that an entity belongs to a specific compliance tier.
    #[instrument(skip(self, input))]
    pub fn prove_tier(&self, input: &TierInput) -> Result<ProofWithPublicInputs> {
        input.validate()?;

        info!(
            "Generating tier proof: tier {}, entity_hash prefix: {}...",
            input.target_tier,
            &input.entity_hash[..8.min(input.entity_hash.len())]
        );

        self.build_and_prove(&Circuit::Tier, input.to_circuit_input())
    }
}

/// Convenience function to generate a threshold proof
pub fn prove_compliance_threshold(
    build_dir: &str,
    score: u64,
    threshold: u64,
    entity_hash: &str,
    salt: &str,
) -> Result<ProofWithPublicInputs> {
    let prover = ComplianceProver::new(build_dir)?;
    let input = ThresholdInput {
        threshold,
        entity_hash: entity_hash.to_string(),
        score,
        salt: salt.to_string(),
    };
    prover.prove_threshold(&input)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circuit_names() {
        assert_eq!(Circuit::Threshold.file_name(), "compliance_threshold");
        assert_eq!(Circuit::Range.file_name(), "range_proof");
        assert_eq!(Circuit::Tier.file_name(), "tier_membership");
    }
}

