/**
 * Compliance Score Range Proof Circuit
 * =====================================
 * 
 * ZK-SNARK circuit to prove a compliance score is within a specified range
 * WITHOUT revealing the actual score.
 * 
 * Use case: Prove "Entity X has compliance score in [0.70, 0.90]" to determine
 * tier classification without revealing exact score.
 * 
 * Score representation:
 * - Scores are fixed-point: 10000 = 1.0000 (4 decimal places)
 * 
 * Public inputs:
 * - minScore: Minimum of range (inclusive)
 * - maxScore: Maximum of range (inclusive)
 * - entityHash: Poseidon hash of entity identifier
 * 
 * Private inputs:
 * - score: The actual compliance score
 * - salt: Random salt for commitment
 * 
 * Version: 1.0.0
 * Author: Civium Compliance Engine
 */

pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";
include "circomlib/circuits/bitify.circom";

/**
 * Range proof: Proves minScore <= score <= maxScore
 */
template ComplianceRangeProof() {
    // =========================================================================
    // Public Inputs
    // =========================================================================
    
    // Range bounds (0-10000)
    signal input minScore;
    signal input maxScore;
    
    // Entity identifier hash
    signal input entityHash;
    
    // =========================================================================
    // Private Inputs
    // =========================================================================
    
    signal input score;
    signal input salt;
    
    // =========================================================================
    // Outputs
    // =========================================================================
    
    signal output scoreCommitment;
    
    // =========================================================================
    // Constraints
    // =========================================================================
    
    // 1. Validate all inputs are in valid score range [0, 10000]
    component scoreBits = Num2Bits(14);
    scoreBits.in <== score;
    
    component minBits = Num2Bits(14);
    minBits.in <== minScore;
    
    component maxBits = Num2Bits(14);
    maxBits.in <== maxScore;
    
    // 2. Check score >= minScore
    component geqMin = GreaterEqThan(14);
    geqMin.in[0] <== score;
    geqMin.in[1] <== minScore;
    geqMin.out === 1;
    
    // 3. Check score <= maxScore
    component leqMax = LessEqThan(14);
    leqMax.in[0] <== score;
    leqMax.in[1] <== maxScore;
    leqMax.out === 1;
    
    // 4. Verify maxScore <= 10000
    component maxValid = LessEqThan(14);
    maxValid.in[0] <== maxScore;
    maxValid.in[1] <== 10000;
    maxValid.out === 1;
    
    // 5. Verify minScore <= maxScore (valid range)
    component validRange = LessEqThan(14);
    validRange.in[0] <== minScore;
    validRange.in[1] <== maxScore;
    validRange.out === 1;
    
    // 6. Compute commitment
    component commitment = Poseidon(3);
    commitment.inputs[0] <== score;
    commitment.inputs[1] <== salt;
    commitment.inputs[2] <== entityHash;
    
    scoreCommitment <== commitment.out;
}

component main {public [minScore, maxScore, entityHash]} = ComplianceRangeProof();

