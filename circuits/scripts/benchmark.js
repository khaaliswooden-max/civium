/**
 * ZK-SNARK Benchmark Script
 * ==========================
 * 
 * Benchmarks proving time for Civium compliance circuits.
 * Target: <5 seconds proving time.
 * 
 * Usage:
 *   node benchmark.js [circuit_name] [iterations]
 * 
 * @version 1.0.0
 */

const snarkjs = require("snarkjs");
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

// Benchmark configuration
const DEFAULT_ITERATIONS = 10;
const TARGET_TIME_MS = 5000;

/**
 * Generate random field element (for testing)
 */
function randomFieldElement() {
    // Generate a random 253-bit number (within BN128 field)
    const bytes = crypto.randomBytes(32);
    bytes[0] &= 0x1F; // Ensure < 2^253
    return BigInt("0x" + bytes.toString("hex")).toString();
}

/**
 * Generate test inputs for each circuit type
 */
function generateTestInputs(circuitName) {
    const entityHash = randomFieldElement();
    const salt = randomFieldElement();
    
    switch (circuitName) {
        case "compliance_threshold":
            return {
                threshold: Math.floor(Math.random() * 5000) + 5000, // 5000-10000
                entityHash,
                score: Math.floor(Math.random() * 3000) + 7000, // 7000-10000
                salt,
            };
        
        case "range_proof":
            const minScore = Math.floor(Math.random() * 3000) + 5000; // 5000-8000
            const maxScore = minScore + Math.floor(Math.random() * 2000) + 500; // min+500 to min+2500
            return {
                minScore,
                maxScore: Math.min(maxScore, 10000),
                entityHash,
                score: Math.floor(Math.random() * (maxScore - minScore)) + minScore,
                salt,
            };
        
        case "tier_membership":
            const tier = Math.floor(Math.random() * 5) + 1; // 1-5
            // Generate score within tier bounds
            const tierBounds = {
                1: [9500, 10000],
                2: [8500, 9499],
                3: [7000, 8499],
                4: [5000, 6999],
                5: [0, 4999],
            };
            const [min, max] = tierBounds[tier];
            return {
                targetTier: tier,
                entityHash,
                score: Math.floor(Math.random() * (max - min + 1)) + min,
                salt,
            };
        
        default:
            throw new Error(`Unknown circuit: ${circuitName}`);
    }
}

/**
 * Run benchmark for a single circuit
 */
async function benchmarkCircuit(circuitName, iterations, buildDir) {
    const wasmPath = path.join(buildDir, circuitName, `${circuitName}_js`, `${circuitName}.wasm`);
    const zkeyPath = path.join(buildDir, circuitName, "proving_key.zkey");
    const vkeyPath = path.join(buildDir, circuitName, "verification_key.json");
    
    // Verify files exist
    if (!fs.existsSync(wasmPath)) {
        throw new Error(`WASM file not found: ${wasmPath}\nRun setup.sh first.`);
    }
    
    const vkey = JSON.parse(fs.readFileSync(vkeyPath, "utf8"));
    
    console.log(`\n${"=".repeat(60)}`);
    console.log(`Benchmarking: ${circuitName}`);
    console.log(`Iterations: ${iterations}`);
    console.log(`Target: <${TARGET_TIME_MS}ms`);
    console.log(`${"=".repeat(60)}\n`);
    
    const provingTimes = [];
    const verificationTimes = [];
    let successCount = 0;
    
    for (let i = 0; i < iterations; i++) {
        const input = generateTestInputs(circuitName);
        
        // Time proof generation
        const proveStart = Date.now();
        const { proof, publicSignals } = await snarkjs.groth16.fullProve(
            input,
            wasmPath,
            zkeyPath
        );
        const proveTime = Date.now() - proveStart;
        provingTimes.push(proveTime);
        
        // Time verification
        const verifyStart = Date.now();
        const isValid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
        const verifyTime = Date.now() - verifyStart;
        verificationTimes.push(verifyTime);
        
        if (isValid) successCount++;
        
        const status = proveTime < TARGET_TIME_MS ? "✓" : "✗";
        console.log(`  [${i + 1}/${iterations}] ${status} Prove: ${proveTime}ms | Verify: ${verifyTime}ms | Valid: ${isValid}`);
    }
    
    // Calculate statistics
    const stats = (times) => {
        const sorted = [...times].sort((a, b) => a - b);
        return {
            min: sorted[0],
            max: sorted[sorted.length - 1],
            mean: Math.round(times.reduce((a, b) => a + b, 0) / times.length),
            median: sorted[Math.floor(sorted.length / 2)],
            p95: sorted[Math.floor(sorted.length * 0.95)],
            p99: sorted[Math.floor(sorted.length * 0.99)],
        };
    };
    
    const proveStats = stats(provingTimes);
    const verifyStats = stats(verificationTimes);
    
    console.log(`\n${"─".repeat(60)}`);
    console.log("RESULTS:");
    console.log(`${"─".repeat(60)}`);
    
    console.log(`\nProving Time (ms):`);
    console.log(`  Min:    ${proveStats.min}`);
    console.log(`  Max:    ${proveStats.max}`);
    console.log(`  Mean:   ${proveStats.mean}`);
    console.log(`  Median: ${proveStats.median}`);
    console.log(`  P95:    ${proveStats.p95}`);
    console.log(`  P99:    ${proveStats.p99}`);
    
    console.log(`\nVerification Time (ms):`);
    console.log(`  Min:    ${verifyStats.min}`);
    console.log(`  Max:    ${verifyStats.max}`);
    console.log(`  Mean:   ${verifyStats.mean}`);
    
    console.log(`\nProof Validity: ${successCount}/${iterations} (${(successCount/iterations*100).toFixed(1)}%)`);
    
    // Check against target
    const passTarget = proveStats.p95 < TARGET_TIME_MS;
    console.log(`\n${"─".repeat(60)}`);
    if (passTarget) {
        console.log(`✅ PASS: P95 proving time (${proveStats.p95}ms) < ${TARGET_TIME_MS}ms target`);
    } else {
        console.log(`❌ FAIL: P95 proving time (${proveStats.p95}ms) >= ${TARGET_TIME_MS}ms target`);
    }
    console.log(`${"─".repeat(60)}\n`);
    
    return {
        circuit: circuitName,
        iterations,
        proving: proveStats,
        verification: verifyStats,
        successRate: successCount / iterations,
        passTarget,
    };
}

/**
 * Main CLI handler
 */
async function main() {
    const args = process.argv.slice(2);
    const circuitName = args[0];
    const iterations = parseInt(args[1]) || DEFAULT_ITERATIONS;
    
    const scriptsDir = __dirname;
    const circuitsDir = path.dirname(scriptsDir);
    const buildDir = path.join(circuitsDir, "build");
    
    console.log(`\n╔${"═".repeat(58)}╗`);
    console.log(`║  CIVIUM ZK-SNARK BENCHMARK                               ║`);
    console.log(`║  Target: <${TARGET_TIME_MS}ms proving time                            ║`);
    console.log(`╚${"═".repeat(58)}╝`);
    
    const results = [];
    
    if (circuitName) {
        // Benchmark single circuit
        const result = await benchmarkCircuit(circuitName, iterations, buildDir);
        results.push(result);
    } else {
        // Benchmark all circuits
        const circuits = ["compliance_threshold", "range_proof", "tier_membership"];
        
        for (const circuit of circuits) {
            try {
                const result = await benchmarkCircuit(circuit, iterations, buildDir);
                results.push(result);
            } catch (error) {
                console.error(`Skipping ${circuit}: ${error.message}`);
            }
        }
    }
    
    // Summary
    console.log(`\n╔${"═".repeat(58)}╗`);
    console.log(`║  BENCHMARK SUMMARY                                       ║`);
    console.log(`╚${"═".repeat(58)}╝\n`);
    
    console.log("Circuit                    | P95 Prove | Target | Status");
    console.log("─".repeat(58));
    
    for (const result of results) {
        const status = result.passTarget ? "✅ PASS" : "❌ FAIL";
        const name = result.circuit.padEnd(25);
        const p95 = `${result.proving.p95}ms`.padEnd(10);
        console.log(`${name}| ${p95}| <${TARGET_TIME_MS}ms | ${status}`);
    }
    
    console.log("");
    
    // Write results to file
    const resultsPath = path.join(buildDir, "benchmark_results.json");
    fs.writeFileSync(resultsPath, JSON.stringify({
        timestamp: new Date().toISOString(),
        targetMs: TARGET_TIME_MS,
        results,
    }, null, 2));
    
    console.log(`Results written to: ${resultsPath}`);
    
    // Exit with error if any failed
    const allPassed = results.every(r => r.passTarget);
    process.exit(allPassed ? 0 : 1);
}

main().catch(error => {
    console.error("Benchmark failed:", error);
    process.exit(1);
});

