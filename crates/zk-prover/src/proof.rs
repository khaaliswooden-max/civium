//! Proof types and serialization

use ark_bn254::{Bn254, Fr, G1Affine, G2Affine};
use ark_groth16::Proof as Groth16Proof;
use ark_serialize::{CanonicalDeserialize, CanonicalSerialize};
use serde::{Deserialize, Serialize};

use crate::error::{ProverError, Result};

/// A Groth16 proof for the BN254 curve
#[derive(Clone, Debug)]
pub struct Proof {
    /// The underlying arkworks proof
    pub inner: Groth16Proof<Bn254>,
}

impl Proof {
    /// Create from arkworks proof
    pub fn new(inner: Groth16Proof<Bn254>) -> Self {
        Self { inner }
    }

    /// Serialize to bytes
    pub fn to_bytes(&self) -> Result<Vec<u8>> {
        let mut bytes = Vec::new();
        self.inner.serialize_compressed(&mut bytes)?;
        Ok(bytes)
    }

    /// Deserialize from bytes
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        let inner = Groth16Proof::deserialize_compressed(bytes)?;
        Ok(Self { inner })
    }

    /// Convert to hex string
    pub fn to_hex(&self) -> Result<String> {
        Ok(hex::encode(self.to_bytes()?))
    }

    /// Convert from hex string
    pub fn from_hex(hex_str: &str) -> Result<Self> {
        let bytes = hex::decode(hex_str)
            .map_err(|e| ProverError::InvalidProofFormat { reason: e.to_string() })?;
        Self::from_bytes(&bytes)
    }

    /// Convert to JSON-serializable format (compatible with snarkjs)
    pub fn to_json(&self) -> Result<ProofJson> {
        let mut a_bytes = Vec::new();
        self.inner.a.serialize_uncompressed(&mut a_bytes)?;

        let mut b_bytes = Vec::new();
        self.inner.b.serialize_uncompressed(&mut b_bytes)?;

        let mut c_bytes = Vec::new();
        self.inner.c.serialize_uncompressed(&mut c_bytes)?;

        Ok(ProofJson {
            pi_a: Self::g1_to_strings(&self.inner.a),
            pi_b: Self::g2_to_strings(&self.inner.b),
            pi_c: Self::g1_to_strings(&self.inner.c),
            protocol: "groth16".into(),
            curve: "bn128".into(),
        })
    }

    /// Convert G1 point to string array
    fn g1_to_strings(point: &G1Affine) -> Vec<String> {
        let x = point.x.to_string();
        let y = point.y.to_string();
        vec![x, y, "1".into()]
    }

    /// Convert G2 point to string array  
    fn g2_to_strings(point: &G2Affine) -> Vec<Vec<String>> {
        let x0 = point.x.c0.to_string();
        let x1 = point.x.c1.to_string();
        let y0 = point.y.c0.to_string();
        let y1 = point.y.c1.to_string();
        vec![vec![x0, x1], vec![y0, y1], vec!["1".into(), "0".into()]]
    }

    /// Generate Solidity calldata for on-chain verification
    pub fn to_solidity_calldata(&self, public_inputs: &[Fr]) -> Result<SolidityCalldata> {
        // Proof points
        let a = Self::g1_to_uint256(&self.inner.a);
        let b = Self::g2_to_uint256(&self.inner.b);
        let c = Self::g1_to_uint256(&self.inner.c);

        // Public inputs
        let inputs: Vec<String> = public_inputs
            .iter()
            .map(|f| f.to_string())
            .collect();

        Ok(SolidityCalldata {
            a,
            b,
            c,
            inputs,
        })
    }

    /// Convert G1 point to uint256 array
    fn g1_to_uint256(point: &G1Affine) -> [String; 2] {
        [point.x.to_string(), point.y.to_string()]
    }

    /// Convert G2 point to uint256 array
    fn g2_to_uint256(point: &G2Affine) -> [[String; 2]; 2] {
        [
            [point.x.c1.to_string(), point.x.c0.to_string()],
            [point.y.c1.to_string(), point.y.c0.to_string()],
        ]
    }
}

/// Proof with its public inputs
#[derive(Clone, Debug)]
pub struct ProofWithPublicInputs {
    /// The ZK proof
    pub proof: Proof,
    /// Public input signals
    pub public_inputs: Vec<Fr>,
    /// Circuit name
    pub circuit: String,
}

impl ProofWithPublicInputs {
    /// Create new proof with inputs
    pub fn new(proof: Proof, public_inputs: Vec<Fr>, circuit: String) -> Self {
        Self {
            proof,
            public_inputs,
            circuit,
        }
    }

    /// Get the score commitment (last public output)
    pub fn score_commitment(&self) -> Option<&Fr> {
        self.public_inputs.last()
    }

    /// Convert to JSON
    pub fn to_json(&self) -> Result<ProofWithInputsJson> {
        Ok(ProofWithInputsJson {
            proof: self.proof.to_json()?,
            public_inputs: self.public_inputs.iter().map(|f| f.to_string()).collect(),
            circuit: self.circuit.clone(),
        })
    }
}

/// JSON-serializable proof format (compatible with snarkjs)
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProofJson {
    /// Proof point A (G1)
    pub pi_a: Vec<String>,
    /// Proof point B (G2)
    pub pi_b: Vec<Vec<String>>,
    /// Proof point C (G1)
    pub pi_c: Vec<String>,
    /// Protocol identifier
    pub protocol: String,
    /// Curve identifier
    pub curve: String,
}

/// JSON format with public inputs
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ProofWithInputsJson {
    /// The proof
    pub proof: ProofJson,
    /// Public inputs as decimal strings
    pub public_inputs: Vec<String>,
    /// Circuit name
    pub circuit: String,
}

/// Solidity-compatible calldata
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SolidityCalldata {
    /// Proof point A
    pub a: [String; 2],
    /// Proof point B
    pub b: [[String; 2]; 2],
    /// Proof point C
    pub c: [String; 2],
    /// Public inputs
    pub inputs: Vec<String>,
}

impl SolidityCalldata {
    /// Format as Solidity function call
    pub fn to_solidity_call(&self) -> String {
        format!(
            "verifyProof(\n  [{}, {}],\n  [[{}, {}], [{}, {}]],\n  [{}, {}],\n  [{}]\n)",
            self.a[0],
            self.a[1],
            self.b[0][0],
            self.b[0][1],
            self.b[1][0],
            self.b[1][1],
            self.c[0],
            self.c[1],
            self.inputs.join(", ")
        )
    }
}

