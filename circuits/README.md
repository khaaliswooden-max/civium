# ZK-SNARK Compliance Circuits

Zero-knowledge proof circuits for Civium compliance verification.

## Overview

This module implements ZK-SNARK circuits using circom and Groth16 proving system to enable privacy-preserving compliance verification:

- **Prove compliance without revealing sensitive data**
- **Verify proofs on-chain efficiently (~250k gas)**
- **Target proving time: <5 seconds**

## Circuits

### 1. Compliance Threshold (`compliance_threshold.circom`)

Proves that a compliance score meets or exceeds a threshold without revealing the actual score.

**Public Inputs:**
- `threshold` - Minimum required score (0-10000)
- `entityHash` - Poseidon hash of entity identifier

**Private Inputs:**
- `score` - Actual compliance score
- `salt` - Random salt for commitment

**Output:**
- `scoreCommitment` - Poseidon(score, salt, entityHash)

**Use Case:** "Prove Entity X has compliance score ≥ 85% without revealing the exact score."

### 2. Range Proof (`range_proof.circom`)

Proves a score falls within a specified range.

**Public Inputs:**
- `minScore` - Lower bound (inclusive)
- `maxScore` - Upper bound (inclusive)
- `entityHash` - Entity identifier hash

**Use Case:** "Prove Entity X has a score between 70% and 90%."

### 3. Tier Membership (`tier_membership.circom`)

Proves membership in a specific compliance tier.

**Tiers:**
| Tier | Name | Score Range |
|------|------|-------------|
| 1 | Critical | 95.00% - 100.00% |
| 2 | High | 85.00% - 94.99% |
| 3 | Standard | 70.00% - 84.99% |
| 4 | Basic | 50.00% - 69.99% |
| 5 | Minimal | 0.00% - 49.99% |

**Use Case:** "Prove Entity X is Tier 2 compliant without revealing exact score."

## Setup

### Prerequisites

```bash
# Install circom
npm install -g circom

# Install snarkjs
npm install -g snarkjs

# Install dependencies
cd circuits
npm install
```

### Trusted Setup

Run the setup script to compile circuits and generate proving/verification keys:

```bash
# Setup all circuits
npm run setup

# Or setup individual circuit
npm run setup:threshold
npm run setup:range
npm run setup:tier
```

This will:
1. Download Powers of Tau ceremony file
2. Compile circom circuits to R1CS + WASM
3. Generate circuit-specific proving keys (Phase 2)
4. Export Solidity verifier contracts

### Directory Structure After Setup

```
circuits/
├── build/
│   ├── compliance_threshold/
│   │   ├── compliance_threshold_js/
│   │   │   └── compliance_threshold.wasm
│   │   ├── compliance_threshold.r1cs
│   │   ├── compliance_threshold.sym
│   │   ├── proving_key.zkey
│   │   ├── verification_key.json
│   │   └── compliance_threshold_verifier.sol
│   ├── range_proof/
│   │   └── ...
│   └── tier_membership/
│       └── ...
├── ptau/
│   └── powersOfTau28_hez_final_14.ptau
└── ...
```

## Usage

### Generate a Proof (Node.js)

```javascript
const { generateProof, verifyProof } = require('./scripts/prove');

const input = {
    threshold: 8000,        // 80%
    entityHash: "12345...", // Poseidon hash of entity ID
    score: 8547,            // 85.47%
    salt: "98765..."        // Random salt
};

const { proof, publicSignals, duration } = await generateProof(
    'compliance_threshold',
    input,
    './build'
);

console.log(`Proof generated in ${duration}ms`);
console.log('Score commitment:', publicSignals[2]);

// Verify
const isValid = await verifyProof(
    'compliance_threshold',
    proof,
    publicSignals,
    './build'
);

console.log('Proof valid:', isValid);
```

### Generate a Proof (Python)

```python
from shared.zk import ComplianceProver

prover = ComplianceProver()

# Generate threshold proof
proof = await prover.prove_threshold(
    score=8547,
    threshold=8000,
    entity_id="LEI-123456789ABCDEF",
)

print(f"Proving time: {proof.metadata.proving_time_ms}ms")
print(f"Commitment: {proof.commitment}")

# Get Solidity calldata
calldata = proof.proof.to_calldata()
```

### Verify On-Chain (Solidity)

```solidity
import "./ComplianceVerifier.sol";

contract MyContract {
    ComplianceVerifier public verifier;
    
    function verifyCompliance(
        uint256[8] calldata proof,
        uint256 threshold,
        uint256 entityHash
    ) external {
        uint256 commitment = verifier.verifyThreshold(
            proof,
            threshold,
            entityHash
        );
        
        // Store commitment for future reference
        entityCommitments[entityHash] = commitment;
    }
}
```

## Testing

### Run Test Vectors

```bash
npm test
```

Test vectors cover:
- Valid proofs for all circuits
- Edge cases (exact threshold, max scores)
- Invalid inputs (score below threshold, wrong tier)
- Constraint violation detection

### Run Benchmarks

```bash
npm run benchmark
```

Target: P95 proving time < 5000ms

Sample benchmark results:
```
Circuit                    | P95 Prove | Target   | Status
────────────────────────────────────────────────────────────
compliance_threshold       | 1234ms    | <5000ms  | ✅ PASS
range_proof               | 1456ms    | <5000ms  | ✅ PASS
tier_membership           | 1678ms    | <5000ms  | ✅ PASS
```

## Performance

### Proof Sizes

| Circuit | Proof Size | Public Inputs |
|---------|------------|---------------|
| Threshold | ~200 bytes | 3 (threshold, entityHash, commitment) |
| Range | ~200 bytes | 4 (min, max, entityHash, commitment) |
| Tier | ~200 bytes | 3 (tier, entityHash, commitment) |

### Gas Costs (On-Chain Verification)

| Operation | Gas |
|-----------|-----|
| Pairing check | ~200,000 |
| Public input processing | ~50,000 |
| **Total verification** | **~250,000** |

### Proving Time Targets

- **P50:** <2 seconds
- **P95:** <5 seconds
- **P99:** <10 seconds

## Security Considerations

### Trusted Setup

The Groth16 proving system requires a trusted setup ceremony:

1. **Phase 1 (Powers of Tau):** We use the Hermez network's ceremony with 54+ participants
2. **Phase 2 (Circuit-specific):** Generated per-circuit using the setup script

⚠️ **Production deployment requires:**
- Multi-party computation for Phase 2
- Documented ceremony participants
- Secure destruction of toxic waste

### Circuit Audits

Before production use:
- [ ] Internal security review
- [ ] External circuit audit
- [ ] Formal verification where possible

### Score Representation

- Scores use fixed-point: 10000 = 1.0000 (100%)
- Prevents precision loss in circuit arithmetic
- All comparisons are exact integer operations

## Integration with Civium

### Blockchain Layer

Proofs are verified on Polygon PoS via the `ComplianceVerifier` contract:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Entity Portal  │────▶│  ZK Prover       │────▶│  Polygon    │
│  (Frontend)     │     │  (Node/Rust)     │     │  Contract   │
└─────────────────┘     └──────────────────┘     └─────────────┘
         │                       │                      │
         │                       │                      │
    Score data              Proof generation     On-chain verify
    (private)               (~1-5 seconds)      (~250k gas)
```

### API Endpoints

```python
# POST /api/v1/compliance/prove
{
    "entity_id": "LEI-123456789",
    "proof_type": "threshold",
    "threshold": 8500
}

# Response
{
    "proof": {...},
    "public_signals": [...],
    "commitment": "...",
    "proving_time_ms": 1234
}
```

## Troubleshooting

### Common Issues

**"Circuit not found"**
```bash
# Run setup first
npm run setup
```

**"Constraint not satisfied"**
- Check that score meets the threshold/range/tier requirements
- Verify input values are in valid range (0-10000)

**"Proving time exceeds target"**
- Ensure Node.js 18+ for WASM performance
- Use Rust wrapper for production workloads
- Consider dedicated proving infrastructure

## References

- [circom Documentation](https://docs.circom.io/)
- [snarkjs GitHub](https://github.com/iden3/snarkjs)
- [Groth16 Paper](https://eprint.iacr.org/2016/260)
- [ADR-002: ZK Proof System](../docs/adr/ADR-002-zk-proof-system.md)

