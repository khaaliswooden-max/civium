# ADR-002: Zero-Knowledge Proof System

## Status
**Accepted** - November 2024

## Context
Civium requires cryptographic verification of compliance claims while preserving data privacy. Key requirements:
- Prove compliance without revealing sensitive data
- Verify proofs on-chain efficiently
- Support multiple proof types (membership, range, equality)
- Balance proof size vs. generation time

## Decision

### Selected: circom + snarkjs (ZK-SNARKs)

**Primary stack:**
- **Circuit language**: circom 2.1+
- **Proving system**: Groth16 (via snarkjs)
- **Verification**: Solidity verifier contracts

**Proof types to implement:**
1. **Compliance attestation**: Entity meets requirement without revealing score
2. **Range proofs**: Score is within acceptable range
3. **Membership proofs**: Entity belongs to compliant set

### Rejected Alternatives

| Alternative | Reason for Rejection |
|-------------|---------------------|
| ZK-STARKs | Larger proof sizes, newer ecosystem |
| Bulletproofs | No trusted setup but slower verification |
| PLONK | More complex setup, less tooling |
| Aztec/Noir | Promising but less mature |

## Implementation Plan

### Phase 2 (Week 5-6)
```
circuits/
├── compliance_attestation.circom  # Basic compliance proof
├── range_proof.circom             # Score range verification
└── verifiers/
    └── ComplianceVerifier.sol     # On-chain verifier
```

### Trusted Setup
- Use Powers of Tau ceremony for initial setup
- Service-specific circuits use phase 2 contributions
- Document ceremony participants

## Consequences

### Positive
- Proven security model (Groth16 is well-studied)
- Small proof sizes (~200 bytes)
- Fast on-chain verification (~250k gas)
- Large ecosystem and documentation

### Negative
- Trusted setup requirement (mitigated by ceremony)
- Circuit updates require new setup
- Prover computation intensive for complex circuits

### Trade-offs
| Aspect | Groth16 | Alternative |
|--------|---------|-------------|
| Proof size | ~200B | STARKs: ~50KB |
| Verification | Fast | STARKs: Slower |
| Setup | Trusted | STARKs: Transparent |
| Prover time | ~1-10s | Bulletproofs: Slower |

## Security Considerations
- Toxic waste from trusted setup must be destroyed
- Circuit audits before production use
- Formal verification of circuits where possible

## Related
- ADR-004: Blockchain Platform
- Phase 2, Week 5 implementation

