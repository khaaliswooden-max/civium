/**
 * ZK-SNARK Test Vectors
 * =====================
 * 
 * Comprehensive test cases for Civium compliance circuits.
 * 
 * @version 1.0.0
 */

const snarkjs = require("snarkjs");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const assert = require("assert");

// Test configuration
const BUILD_DIR = path.join(__dirname, "..", "build");
const RESULTS_DIR = path.join(__dirname, "results");

/**
 * Test vectors for compliance_threshold circuit
 */
const THRESHOLD_VECTORS = [
    // Valid proofs (score >= threshold)
    {
        name: "threshold_exact_match",
        valid: true,
        input: {
            threshold: 8000,
            entityHash: "12345678901234567890",
            score: 8000,  // Exactly at threshold
            salt: "98765432109876543210"
        }
    },
    {
        name: "threshold_above",
        valid: true,
        input: {
            threshold: 8000,
            entityHash: "12345678901234567890",
            score: 8500,  // Above threshold
            salt: "98765432109876543210"
        }
    },
    {
        name: "threshold_max_score",
        valid: true,
        input: {
            threshold: 9500,
            entityHash: "12345678901234567890",
            score: 10000,  // Maximum score
            salt: "98765432109876543210"
        }
    },
    {
        name: "threshold_zero",
        valid: true,
        input: {
            threshold: 0,
            entityHash: "12345678901234567890",
            score: 5000,
            salt: "98765432109876543210"
        }
    },
    // Invalid proofs (score < threshold) - should fail to generate
    {
        name: "threshold_below",
        valid: false,
        input: {
            threshold: 8000,
            entityHash: "12345678901234567890",
            score: 7999,  // Below threshold
            salt: "98765432109876543210"
        }
    },
    {
        name: "threshold_score_exceeds_max",
        valid: false,
        input: {
            threshold: 8000,
            entityHash: "12345678901234567890",
            score: 10001,  // Invalid: > 10000
            salt: "98765432109876543210"
        }
    }
];

/**
 * Test vectors for range_proof circuit
 */
const RANGE_VECTORS = [
    {
        name: "range_within_bounds",
        valid: true,
        input: {
            minScore: 7000,
            maxScore: 9000,
            entityHash: "12345678901234567890",
            score: 8000,  // Within range
            salt: "98765432109876543210"
        }
    },
    {
        name: "range_at_min",
        valid: true,
        input: {
            minScore: 7000,
            maxScore: 9000,
            entityHash: "12345678901234567890",
            score: 7000,  // At minimum
            salt: "98765432109876543210"
        }
    },
    {
        name: "range_at_max",
        valid: true,
        input: {
            minScore: 7000,
            maxScore: 9000,
            entityHash: "12345678901234567890",
            score: 9000,  // At maximum
            salt: "98765432109876543210"
        }
    },
    {
        name: "range_full",
        valid: true,
        input: {
            minScore: 0,
            maxScore: 10000,
            entityHash: "12345678901234567890",
            score: 5000,
            salt: "98765432109876543210"
        }
    },
    {
        name: "range_below_min",
        valid: false,
        input: {
            minScore: 7000,
            maxScore: 9000,
            entityHash: "12345678901234567890",
            score: 6999,  // Below minimum
            salt: "98765432109876543210"
        }
    },
    {
        name: "range_above_max",
        valid: false,
        input: {
            minScore: 7000,
            maxScore: 9000,
            entityHash: "12345678901234567890",
            score: 9001,  // Above maximum
            salt: "98765432109876543210"
        }
    }
];

/**
 * Test vectors for tier_membership circuit
 */
const TIER_VECTORS = [
    // Tier 1: 9500-10000 (Critical)
    {
        name: "tier_1_valid",
        valid: true,
        input: {
            targetTier: 1,
            entityHash: "12345678901234567890",
            score: 9700,
            salt: "98765432109876543210"
        }
    },
    // Tier 2: 8500-9499 (High)
    {
        name: "tier_2_valid",
        valid: true,
        input: {
            targetTier: 2,
            entityHash: "12345678901234567890",
            score: 8700,
            salt: "98765432109876543210"
        }
    },
    // Tier 3: 7000-8499 (Standard)
    {
        name: "tier_3_valid",
        valid: true,
        input: {
            targetTier: 3,
            entityHash: "12345678901234567890",
            score: 7500,
            salt: "98765432109876543210"
        }
    },
    // Tier 4: 5000-6999 (Basic)
    {
        name: "tier_4_valid",
        valid: true,
        input: {
            targetTier: 4,
            entityHash: "12345678901234567890",
            score: 6000,
            salt: "98765432109876543210"
        }
    },
    // Tier 5: 0-4999 (Minimal)
    {
        name: "tier_5_valid",
        valid: true,
        input: {
            targetTier: 5,
            entityHash: "12345678901234567890",
            score: 3000,
            salt: "98765432109876543210"
        }
    },
    // Invalid: score doesn't match tier
    {
        name: "tier_wrong_tier",
        valid: false,
        input: {
            targetTier: 1,  // Claims tier 1
            entityHash: "12345678901234567890",
            score: 8700,    // But score is tier 2
            salt: "98765432109876543210"
        }
    },
    // Invalid tier number
    {
        name: "tier_invalid_number",
        valid: false,
        input: {
            targetTier: 6,  // Invalid tier
            entityHash: "12345678901234567890",
            score: 5000,
            salt: "98765432109876543210"
        }
    }
];

/**
 * Run test for a single circuit and input
 */
async function runTest(circuitName, vector) {
    const wasmPath = path.join(BUILD_DIR, circuitName, `${circuitName}_js`, `${circuitName}.wasm`);
    const zkeyPath = path.join(BUILD_DIR, circuitName, "proving_key.zkey");
    const vkeyPath = path.join(BUILD_DIR, circuitName, "verification_key.json");
    
    // Check if circuit is built
    if (!fs.existsSync(wasmPath)) {
        return {
            name: vector.name,
            status: "SKIP",
            reason: "Circuit not built",
            duration: 0
        };
    }
    
    const start = Date.now();
    
    try {
        // Generate proof
        const { proof, publicSignals } = await snarkjs.groth16.fullProve(
            vector.input,
            wasmPath,
            zkeyPath
        );
        
        // Load verification key
        const vkey = JSON.parse(fs.readFileSync(vkeyPath, "utf8"));
        
        // Verify proof
        const isValid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
        
        const duration = Date.now() - start;
        
        if (vector.valid) {
            // Expected valid proof
            return {
                name: vector.name,
                status: isValid ? "PASS" : "FAIL",
                reason: isValid ? null : "Proof verification failed",
                duration,
                publicSignals,
                expectedValid: true,
                actualValid: isValid
            };
        } else {
            // Expected invalid - shouldn't reach here if circuit constraints work
            return {
                name: vector.name,
                status: "FAIL",
                reason: "Expected constraint violation but proof generated",
                duration,
                expectedValid: false,
                actualValid: isValid
            };
        }
        
    } catch (error) {
        const duration = Date.now() - start;
        
        if (!vector.valid) {
            // Expected to fail
            return {
                name: vector.name,
                status: "PASS",
                reason: "Correctly rejected invalid input",
                duration,
                error: error.message,
                expectedValid: false
            };
        } else {
            // Unexpected failure
            return {
                name: vector.name,
                status: "FAIL",
                reason: error.message,
                duration,
                expectedValid: true
            };
        }
    }
}

/**
 * Run all tests for a circuit
 */
async function runCircuitTests(circuitName, vectors) {
    console.log(`\n${"=".repeat(60)}`);
    console.log(`Testing: ${circuitName}`);
    console.log(`${"=".repeat(60)}`);
    
    const results = [];
    
    for (const vector of vectors) {
        const result = await runTest(circuitName, vector);
        results.push(result);
        
        const status = result.status === "PASS" ? "✓" : 
                      result.status === "SKIP" ? "○" : "✗";
        
        console.log(`  ${status} ${result.name} (${result.duration}ms)`);
        if (result.reason && result.status !== "PASS") {
            console.log(`      ${result.reason}`);
        }
    }
    
    return results;
}

/**
 * Main test runner
 */
async function main() {
    console.log(`\n╔${"═".repeat(58)}╗`);
    console.log(`║  CIVIUM ZK-SNARK TEST VECTORS                            ║`);
    console.log(`╚${"═".repeat(58)}╝`);
    
    const allResults = {};
    
    // Run threshold tests
    allResults.compliance_threshold = await runCircuitTests(
        "compliance_threshold",
        THRESHOLD_VECTORS
    );
    
    // Run range tests
    allResults.range_proof = await runCircuitTests(
        "range_proof",
        RANGE_VECTORS
    );
    
    // Run tier tests
    allResults.tier_membership = await runCircuitTests(
        "tier_membership",
        TIER_VECTORS
    );
    
    // Summary
    console.log(`\n${"=".repeat(60)}`);
    console.log("SUMMARY");
    console.log(`${"=".repeat(60)}`);
    
    let totalPass = 0, totalFail = 0, totalSkip = 0;
    
    for (const [circuit, results] of Object.entries(allResults)) {
        const pass = results.filter(r => r.status === "PASS").length;
        const fail = results.filter(r => r.status === "FAIL").length;
        const skip = results.filter(r => r.status === "SKIP").length;
        
        totalPass += pass;
        totalFail += fail;
        totalSkip += skip;
        
        const status = fail > 0 ? "❌" : skip === results.length ? "○" : "✅";
        console.log(`${status} ${circuit}: ${pass}/${results.length} passed`);
    }
    
    console.log(`\nTotal: ${totalPass} passed, ${totalFail} failed, ${totalSkip} skipped`);
    
    // Save results
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    fs.writeFileSync(
        path.join(RESULTS_DIR, "test_results.json"),
        JSON.stringify({
            timestamp: new Date().toISOString(),
            results: allResults,
            summary: { totalPass, totalFail, totalSkip }
        }, null, 2)
    );
    
    console.log(`\nResults saved to: ${path.join(RESULTS_DIR, "test_results.json")}`);
    
    // Exit with error if any tests failed
    process.exit(totalFail > 0 ? 1 : 0);
}

// Export for programmatic use
module.exports = {
    THRESHOLD_VECTORS,
    RANGE_VECTORS,
    TIER_VECTORS,
    runTest,
    runCircuitTests
};

// Run if called directly
if (require.main === module) {
    main().catch(error => {
        console.error("Test runner failed:", error);
        process.exit(1);
    });
}

