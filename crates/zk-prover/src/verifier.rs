//! ZK-SNARK proof verification

use std::fs;
use std::path::Path;

use ark_bn254::{Bn254, Fr};
use ark_groth16::{Groth16, VerifyingKey};
use ark_serialize::CanonicalDeserialize;
use ark_snark::SNARK;
use serde::Deserialize;
use tracing::{debug, info, instrument};

use crate::error::{ProverError, Result};
use crate::proof::{Proof, ProofWithPublicInputs};
use crate::prover::Circuit;

/// ZK-SNARK proof verifier
pub struct ComplianceVerifier {
    /// Base path to circuit build directory
    build_dir: String,
    /// Cached verification keys
    threshold_vk: Option<VerifyingKey<Bn254>>,
    range_vk: Option<VerifyingKey<Bn254>>,
    tier_vk: Option<VerifyingKey<Bn254>>,
}

impl ComplianceVerifier {
    /// Create a new verifier
    pub fn new(build_dir: impl AsRef<str>) -> Result<Self> {
        let build_dir = build_dir.as_ref().to_string();

        if !Path::new(&build_dir).exists() {
            return Err(ProverError::CircuitNotFound { path: build_dir });
        }

        Ok(Self {
            build_dir,
            threshold_vk: None,
            range_vk: None,
            tier_vk: None,
        })
    }

    /// Load verification key from JSON file (snarkjs format)
    fn load_verification_key(&self, circuit: &Circuit) -> Result<VerifyingKey<Bn254>> {
        let name = circuit.file_name();
        let vkey_path = format!("{}/{}/verification_key.json", self.build_dir, name);

        if !Path::new(&vkey_path).exists() {
            return Err(ProverError::CircuitNotFound { path: vkey_path });
        }

        debug!("Loading verification key from: {}", vkey_path);

        let vkey_json = fs::read_to_string(&vkey_path)?;
        let vkey_data: VerificationKeyJson = serde_json::from_str(&vkey_json)?;

        Self::parse_verification_key(&vkey_data)
    }

    /// Parse snarkjs verification key format
    fn parse_verification_key(data: &VerificationKeyJson) -> Result<VerifyingKey<Bn254>> {
        // In production, implement full parsing of snarkjs vkey format
        // For now, return error indicating verification key needs parsing
        Err(ProverError::SetupError {
            reason: format!(
                "VKey parsing not fully implemented - protocol: {}, curve: {}",
                data.protocol, data.curve
            ),
        })
    }

    /// Verify a threshold compliance proof
    #[instrument(skip(self, proof))]
    pub fn verify_threshold(&self, proof: &ProofWithPublicInputs) -> Result<bool> {
        if proof.circuit != Circuit::Threshold.file_name() {
            return Err(ProverError::InvalidProofFormat {
                reason: format!(
                    "Expected threshold proof, got {}",
                    proof.circuit
                ),
            });
        }

        self.verify_proof(&Circuit::Threshold, proof)
    }

    /// Verify a range compliance proof
    #[instrument(skip(self, proof))]
    pub fn verify_range(&self, proof: &ProofWithPublicInputs) -> Result<bool> {
        if proof.circuit != Circuit::Range.file_name() {
            return Err(ProverError::InvalidProofFormat {
                reason: format!("Expected range proof, got {}", proof.circuit),
            });
        }

        self.verify_proof(&Circuit::Range, proof)
    }

    /// Verify a tier membership proof
    #[instrument(skip(self, proof))]
    pub fn verify_tier(&self, proof: &ProofWithPublicInputs) -> Result<bool> {
        if proof.circuit != Circuit::Tier.file_name() {
            return Err(ProverError::InvalidProofFormat {
                reason: format!("Expected tier proof, got {}", proof.circuit),
            });
        }

        self.verify_proof(&Circuit::Tier, proof)
    }

    /// Generic proof verification
    fn verify_proof(&self, circuit: &Circuit, proof: &ProofWithPublicInputs) -> Result<bool> {
        info!("Verifying {} proof", circuit.file_name());

        let vk = self.load_verification_key(circuit)?;

        let is_valid = Groth16::<Bn254>::verify(&vk, &proof.public_inputs, &proof.proof.inner)
            .map_err(|e| ProverError::VerificationFailed {
                reason: e.to_string(),
            })?;

        info!("Proof verification result: {}", is_valid);

        Ok(is_valid)
    }

    /// Verify proof using raw bytes and public inputs
    pub fn verify_raw(
        &self,
        circuit: &Circuit,
        proof_bytes: &[u8],
        public_inputs: &[Fr],
    ) -> Result<bool> {
        let proof = Proof::from_bytes(proof_bytes)?;
        let vk = self.load_verification_key(circuit)?;

        Groth16::<Bn254>::verify(&vk, public_inputs, &proof.inner).map_err(|e| {
            ProverError::VerificationFailed {
                reason: e.to_string(),
            }
        })
    }
}

/// snarkjs verification key JSON format
#[derive(Debug, Deserialize)]
struct VerificationKeyJson {
    protocol: String,
    curve: String,
    #[serde(rename = "nPublic")]
    n_public: u32,
    vk_alpha_1: Vec<String>,
    vk_beta_2: Vec<Vec<String>>,
    vk_gamma_2: Vec<Vec<String>>,
    vk_delta_2: Vec<Vec<String>>,
    #[serde(rename = "vk_alphabeta_12")]
    vk_alphabeta_12: Vec<Vec<Vec<String>>>,
    #[serde(rename = "IC")]
    ic: Vec<Vec<String>>,
}

/// Verify a threshold proof (convenience function)
pub fn verify_compliance_threshold(
    build_dir: &str,
    proof: &ProofWithPublicInputs,
) -> Result<bool> {
    let verifier = ComplianceVerifier::new(build_dir)?;
    verifier.verify_threshold(proof)
}

