//! Error types for the ZK prover

use thiserror::Error;

/// Result type alias for prover operations
pub type Result<T> = std::result::Result<T, ProverError>;

/// Errors that can occur during proof generation and verification
#[derive(Error, Debug)]
pub enum ProverError {
    /// Circuit file not found
    #[error("Circuit file not found: {path}")]
    CircuitNotFound { path: String },

    /// Invalid input value
    #[error("Invalid input: {field} = {value} (expected {expected})")]
    InvalidInput {
        field: String,
        value: String,
        expected: String,
    },

    /// Proof generation failed
    #[error("Proof generation failed: {reason}")]
    ProofGenerationFailed { reason: String },

    /// Proof verification failed
    #[error("Proof verification failed: {reason}")]
    VerificationFailed { reason: String },

    /// Invalid proof format
    #[error("Invalid proof format: {reason}")]
    InvalidProofFormat { reason: String },

    /// Serialization error
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// IO error
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// Witness calculation error
    #[error("Witness calculation error: {reason}")]
    WitnessError { reason: String },

    /// Setup error
    #[error("Setup error: {reason}")]
    SetupError { reason: String },

    /// Score out of range
    #[error("Score {score} out of valid range [0, 10000]")]
    ScoreOutOfRange { score: u64 },

    /// Threshold not met
    #[error("Score {score} does not meet threshold {threshold}")]
    ThresholdNotMet { score: u64, threshold: u64 },

    /// Invalid tier
    #[error("Invalid tier {tier}, must be 1-5")]
    InvalidTier { tier: u8 },

    /// Arkworks error
    #[error("Cryptographic error: {0}")]
    ArkError(String),
}

impl From<ark_serialize::SerializationError> for ProverError {
    fn from(e: ark_serialize::SerializationError) -> Self {
        Self::ArkError(e.to_string())
    }
}

impl From<ark_relations::r1cs::SynthesisError> for ProverError {
    fn from(e: ark_relations::r1cs::SynthesisError) -> Self {
        Self::ArkError(e.to_string())
    }
}

