/**
 * Compliance Score Threshold Proof Circuit
 * =========================================
 * 
 * ZK-SNARK circuit to prove a compliance score meets or exceeds a threshold
 * WITHOUT revealing the actual score.
 * 
 * Use case: Prove "Entity X has compliance score >= 0.80" without revealing
 * that the actual score is 0.8547.
 * 
 * Score representation:
 * - Scores are fixed-point: 10000 = 1.0000 (4 decimal places)
 * - Max score: 10000 (1.0000)
 * - Threshold range: 0 to 10000
 * 
 * Public inputs:
 * - threshold: The minimum required score (public)
 * - entityHash: Poseidon hash of entity identifier (public)
 * 
 * Private inputs:
 * - score: The actual compliance score (private)
 * - salt: Random salt for hiding score in commitment (private)
 * 
 * Outputs:
 * - scoreCommitment: Poseidon(score, salt) - can be published without revealing score
 * 
 * Version: 1.0.0
 * Author: Civium Compliance Engine
 */

pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";
include "circomlib/circuits/bitify.circom";

/**
 * Range check: Ensures value is within [0, max]
 * Used to verify score is a valid fixed-point value
 */
template RangeCheck(maxBits) {
    signal input value;
    signal input maxValue;
    
    // Decompose to bits to ensure value fits in maxBits
    component toBits = Num2Bits(maxBits);
    toBits.in <== value;
    
    // Check value <= maxValue
    component leq = LessEqThan(maxBits);
    leq.in[0] <== value;
    leq.in[1] <== maxValue;
    leq.out === 1;
}

/**
 * Main compliance threshold proof circuit
 * 
 * Proves: score >= threshold AND score is valid
 */
template ComplianceThreshold() {
    // =========================================================================
    // Public Inputs
    // =========================================================================
    
    // Minimum required compliance score (0-10000, representing 0.0000-1.0000)
    signal input threshold;
    
    // Poseidon hash of entity identifier (e.g., LEI, DID)
    // This links the proof to a specific entity without revealing the ID
    signal input entityHash;
    
    // =========================================================================
    // Private Inputs
    // =========================================================================
    
    // Actual compliance score (kept private)
    signal input score;
    
    // Random salt for commitment (prevents rainbow table attacks)
    signal input salt;
    
    // =========================================================================
    // Outputs
    // =========================================================================
    
    // Commitment to the score: Poseidon(score, salt, entityHash)
    // This can be stored on-chain to verify future proofs relate to same score
    signal output scoreCommitment;
    
    // =========================================================================
    // Constraints
    // =========================================================================
    
    // 1. Verify score is in valid range [0, 10000]
    //    Using 14 bits (can represent up to 16383, enough for 10000)
    component scoreRange = RangeCheck(14);
    scoreRange.value <== score;
    scoreRange.maxValue <== 10000;
    
    // 2. Verify threshold is in valid range [0, 10000]
    component thresholdRange = RangeCheck(14);
    thresholdRange.value <== threshold;
    thresholdRange.maxValue <== 10000;
    
    // 3. Prove score >= threshold
    //    Using GreaterEqThan comparator
    component geq = GreaterEqThan(14);
    geq.in[0] <== score;
    geq.in[1] <== threshold;
    
    // This constraint ensures the proof is only valid if score >= threshold
    geq.out === 1;
    
    // 4. Compute score commitment
    //    commitment = Poseidon(score, salt, entityHash)
    //    This binds the proof to both the score and the entity
    component commitment = Poseidon(3);
    commitment.inputs[0] <== score;
    commitment.inputs[1] <== salt;
    commitment.inputs[2] <== entityHash;
    
    scoreCommitment <== commitment.out;
}

// Main component with public inputs marked
component main {public [threshold, entityHash]} = ComplianceThreshold();

