/**
 * Compliance Tier Membership Proof Circuit
 * =========================================
 * 
 * ZK-SNARK circuit to prove an entity belongs to a specific compliance tier
 * based on their score, without revealing the exact score.
 * 
 * Tier Definitions (configurable):
 * - Tier 1 (Critical): score >= 9500 (95%)
 * - Tier 2 (High):     score >= 8500 (85%)
 * - Tier 3 (Standard): score >= 7000 (70%)
 * - Tier 4 (Basic):    score >= 5000 (50%)
 * - Tier 5 (Minimal):  score < 5000
 * 
 * Public inputs:
 * - targetTier: The tier being proven (1-5)
 * - entityHash: Hash of entity identifier
 * 
 * Private inputs:
 * - score: Actual compliance score
 * - salt: Random salt for commitment
 * 
 * Version: 1.0.0
 * Author: Civium Compliance Engine
 */

pragma circom 2.1.6;

include "circomlib/circuits/comparators.circom";
include "circomlib/circuits/poseidon.circom";
include "circomlib/circuits/bitify.circom";
include "circomlib/circuits/mux1.circom";

/**
 * Tier boundary selector
 * Returns the minimum score required for a given tier
 */
template TierBoundary() {
    signal input tier;  // 1-5
    signal output minScore;
    signal output maxScore;
    
    // Tier boundaries (encoded as fixed-point * 10000)
    // Tier 1: [9500, 10000] - Critical
    // Tier 2: [8500, 9499]  - High  
    // Tier 3: [7000, 8499]  - Standard
    // Tier 4: [5000, 6999]  - Basic
    // Tier 5: [0, 4999]     - Minimal
    
    // Check tier is valid (1-5)
    component tierBits = Num2Bits(4);
    tierBits.in <== tier;
    
    component tierGeq1 = GreaterEqThan(4);
    tierGeq1.in[0] <== tier;
    tierGeq1.in[1] <== 1;
    tierGeq1.out === 1;
    
    component tierLeq5 = LessEqThan(4);
    tierLeq5.in[0] <== tier;
    tierLeq5.in[1] <== 5;
    tierLeq5.out === 1;
    
    // Compute boundaries based on tier
    // Using polynomial interpolation for tier -> minScore
    // tier=1 -> 9500, tier=2 -> 8500, tier=3 -> 7000, tier=4 -> 5000, tier=5 -> 0
    
    // Intermediate signals for tier comparison
    signal isTier1;
    signal isTier2;
    signal isTier3;
    signal isTier4;
    signal isTier5;
    
    component eq1 = IsEqual();
    eq1.in[0] <== tier;
    eq1.in[1] <== 1;
    isTier1 <== eq1.out;
    
    component eq2 = IsEqual();
    eq2.in[0] <== tier;
    eq2.in[1] <== 2;
    isTier2 <== eq2.out;
    
    component eq3 = IsEqual();
    eq3.in[0] <== tier;
    eq3.in[1] <== 3;
    isTier3 <== eq3.out;
    
    component eq4 = IsEqual();
    eq4.in[0] <== tier;
    eq4.in[1] <== 4;
    isTier4 <== eq4.out;
    
    component eq5 = IsEqual();
    eq5.in[0] <== tier;
    eq5.in[1] <== 5;
    isTier5 <== eq5.out;
    
    // Compute minScore = sum(isTierN * minScoreN)
    minScore <== isTier1 * 9500 + isTier2 * 8500 + isTier3 * 7000 + isTier4 * 5000 + isTier5 * 0;
    
    // Compute maxScore = sum(isTierN * maxScoreN)  
    maxScore <== isTier1 * 10000 + isTier2 * 9499 + isTier3 * 8499 + isTier4 * 6999 + isTier5 * 4999;
}

/**
 * Main tier membership proof
 */
template TierMembershipProof() {
    // =========================================================================
    // Public Inputs
    // =========================================================================
    
    signal input targetTier;  // 1-5
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
    
    // 1. Get tier boundaries
    component tierBounds = TierBoundary();
    tierBounds.tier <== targetTier;
    
    // 2. Validate score is in valid range
    component scoreBits = Num2Bits(14);
    scoreBits.in <== score;
    
    component scoreValid = LessEqThan(14);
    scoreValid.in[0] <== score;
    scoreValid.in[1] <== 10000;
    scoreValid.out === 1;
    
    // 3. Prove score >= tier minimum
    component geqMin = GreaterEqThan(14);
    geqMin.in[0] <== score;
    geqMin.in[1] <== tierBounds.minScore;
    geqMin.out === 1;
    
    // 4. Prove score <= tier maximum
    component leqMax = LessEqThan(14);
    leqMax.in[0] <== score;
    leqMax.in[1] <== tierBounds.maxScore;
    leqMax.out === 1;
    
    // 5. Compute commitment
    component commitment = Poseidon(3);
    commitment.inputs[0] <== score;
    commitment.inputs[1] <== salt;
    commitment.inputs[2] <== entityHash;
    
    scoreCommitment <== commitment.out;
}

component main {public [targetTier, entityHash]} = TierMembershipProof();

