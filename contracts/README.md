# Civium Smart Contracts

Solidity smart contracts for on-chain compliance verification.

## Contracts

### ComplianceVerifier

On-chain verification of ZK-SNARK compliance proofs using Groth16 over BN254.

**Functions:**
- `verifyThreshold(proof, threshold, entityHash)` - Verify score >= threshold
- `verifyRange(proof, minScore, maxScore, entityHash)` - Verify score in range
- `verifyTier(proof, tier, entityHash)` - Verify tier membership

**Features:**
- Replay attack prevention via proof hash tracking
- Entity commitment storage for audit trail
- Gas-efficient pairing verification (~250k gas)

### ComplianceRegistry

Registry for tracking compliance verifications across entities.

**Features:**
- Entity compliance registration
- Tier-based compliance checks
- Expiration management

### IComplianceVerifier

Interface for integration with other contracts.

## Deployment

### Prerequisites

```bash
# Install Foundry
curl -L https://foundry.paradigm.xyz | bash
foundryup

# Or use Hardhat
npm install --save-dev hardhat
```

### Setup

1. Generate verification keys (run in circuits/):
   ```bash
   npm run setup
   ```

2. Copy generated Solidity verifiers:
   ```bash
   cp circuits/build/*/verifier.sol contracts/generated/
   ```

3. Update verification key constants in `ComplianceVerifier.sol`

### Deploy

```bash
# Using Foundry
forge create --rpc-url $RPC_URL \
    --private-key $PRIVATE_KEY \
    contracts/ComplianceVerifier.sol:ComplianceVerifier

# Using Hardhat
npx hardhat deploy --network polygon
```

## Gas Costs

| Function | Gas |
|----------|-----|
| verifyThreshold | ~250,000 |
| verifyRange | ~260,000 |
| verifyTier | ~255,000 |
| First-time entity | +20,000 |

## Security

⚠️ **Production Checklist:**
- [ ] External audit of contracts
- [ ] Verification key validity check
- [ ] Multi-sig ownership
- [ ] Pausable for emergencies
- [ ] Upgrade path (proxy pattern)

## License

MIT

