//! # Civium ZK-SNARK Prover
//!
//! High-performance Rust implementation for ZK-SNARK proof generation
//! in the Civium compliance verification system.
//!
//! ## Features
//!
//! - **Compliance Threshold Proofs**: Prove score >= threshold without revealing score
//! - **Range Proofs**: Prove score is within a range
//! - **Tier Membership Proofs**: Prove membership in a compliance tier
//!
//! ## Performance
//!
//! Target: <5 seconds proving time for all circuit types
//!
//! ## Example
//!
//! ```rust,ignore
//! use civium_zk_prover::{ComplianceProver, ThresholdInput};
//!
//! let prover = ComplianceProver::new("./circuits/build")?;
//!
//! let input = ThresholdInput {
//!     threshold: 8000,
//!     entity_hash: "123...".into(),
//!     score: 8500,
//!     salt: "456...".into(),
//! };
//!
//! let (proof, public_signals) = prover.prove_threshold(&input)?;
//! ```

#![warn(clippy::all, clippy::pedantic)]
#![allow(clippy::module_name_repetitions)]
#![allow(clippy::must_use_candidate)]

pub mod circuits;
pub mod error;
pub mod poseidon;
pub mod proof;
pub mod prover;
pub mod types;
pub mod verifier;

// Re-exports
pub use error::{ProverError, Result};
pub use proof::{Proof, ProofWithPublicInputs};
pub use prover::ComplianceProver;
pub use types::{RangeInput, ThresholdInput, TierInput};
pub use verifier::ComplianceVerifier;

#[cfg(feature = "python")]
mod python;

#[cfg(feature = "wasm")]
mod wasm;

