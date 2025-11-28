/**
 * ZK-SNARK Proof Generation Script
 * =================================
 * 
 * Generates proofs for Civium compliance circuits using snarkjs.
 * 
 * Usage:
 *   node prove.js <circuit_name> <input_file> [output_dir]
 * 
 * Examples:
 *   node prove.js compliance_threshold input.json ./output
 * 
 * Input file format:
 *   {
 *     "threshold": 8000,
 *     "entityHash": "1234567890123456789",
 *     "score": 8500,
 *     "salt": "9876543210987654321"
 *   }
 * 
 * Output:
 *   - proof.json: The ZK proof
 *   - public.json: Public inputs/outputs
 * 
 * @version 1.0.0
 */

const snarkjs = require("snarkjs");
const fs = require("fs");
const path = require("path");

/**
 * Generate a ZK-SNARK proof
 * 
 * @param {string} circuitName - Name of the circuit
 * @param {object} input - Input signals
 * @param {string} buildDir - Directory containing compiled circuit
 * @returns {Promise<{proof: object, publicSignals: string[]}>}
 */
async function generateProof(circuitName, input, buildDir) {
    const wasmPath = path.join(buildDir, circuitName, `${circuitName}_js`, `${circuitName}.wasm`);
    const zkeyPath = path.join(buildDir, circuitName, "proving_key.zkey");
    
    // Verify files exist
    if (!fs.existsSync(wasmPath)) {
        throw new Error(`WASM file not found: ${wasmPath}`);
    }
    if (!fs.existsSync(zkeyPath)) {
        throw new Error(`Proving key not found: ${zkeyPath}`);
    }
    
    console.log(`Generating proof for circuit: ${circuitName}`);
    console.log(`Input signals:`, JSON.stringify(input, null, 2));
    
    const startTime = Date.now();
    
    // Generate the proof
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(
        input,
        wasmPath,
        zkeyPath
    );
    
    const duration = Date.now() - startTime;
    console.log(`Proof generated in ${duration}ms`);
    
    return { proof, publicSignals, duration };
}

/**
 * Verify a ZK-SNARK proof
 * 
 * @param {string} circuitName - Name of the circuit
 * @param {object} proof - The proof object
 * @param {string[]} publicSignals - Public signals
 * @param {string} buildDir - Directory containing verification key
 * @returns {Promise<boolean>}
 */
async function verifyProof(circuitName, proof, publicSignals, buildDir) {
    const vkeyPath = path.join(buildDir, circuitName, "verification_key.json");
    
    if (!fs.existsSync(vkeyPath)) {
        throw new Error(`Verification key not found: ${vkeyPath}`);
    }
    
    const vkey = JSON.parse(fs.readFileSync(vkeyPath, "utf8"));
    
    console.log("Verifying proof...");
    const startTime = Date.now();
    
    const isValid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
    
    const duration = Date.now() - startTime;
    console.log(`Verification completed in ${duration}ms`);
    console.log(`Proof is ${isValid ? "VALID" : "INVALID"}`);
    
    return isValid;
}

/**
 * Generate Solidity calldata for on-chain verification
 * 
 * @param {object} proof - The proof object
 * @param {string[]} publicSignals - Public signals
 * @returns {Promise<string>}
 */
async function generateCalldata(proof, publicSignals) {
    const calldata = await snarkjs.groth16.exportSolidityCallData(proof, publicSignals);
    return calldata;
}

/**
 * Main CLI handler
 */
async function main() {
    const args = process.argv.slice(2);
    
    if (args.length < 2) {
        console.log(`
ZK-SNARK Proof Generator for Civium Compliance

Usage:
  node prove.js <circuit_name> <input_file> [output_dir]

Arguments:
  circuit_name  Name of the circuit (e.g., compliance_threshold)
  input_file    JSON file with input signals
  output_dir    Output directory (default: ./output)

Example:
  node prove.js compliance_threshold input.json ./proofs
        `);
        process.exit(1);
    }
    
    const circuitName = args[0];
    const inputFile = args[1];
    const outputDir = args[2] || "./output";
    
    // Paths
    const scriptsDir = __dirname;
    const circuitsDir = path.dirname(scriptsDir);
    const buildDir = path.join(circuitsDir, "build");
    
    // Read input
    if (!fs.existsSync(inputFile)) {
        console.error(`Input file not found: ${inputFile}`);
        process.exit(1);
    }
    
    const input = JSON.parse(fs.readFileSync(inputFile, "utf8"));
    
    try {
        // Generate proof
        const { proof, publicSignals, duration } = await generateProof(
            circuitName,
            input,
            buildDir
        );
        
        // Verify proof
        const isValid = await verifyProof(circuitName, proof, publicSignals, buildDir);
        
        if (!isValid) {
            console.error("ERROR: Generated proof failed verification!");
            process.exit(1);
        }
        
        // Generate calldata
        const calldata = await generateCalldata(proof, publicSignals);
        
        // Create output directory
        fs.mkdirSync(outputDir, { recursive: true });
        
        // Write outputs
        const proofPath = path.join(outputDir, "proof.json");
        const publicPath = path.join(outputDir, "public.json");
        const calldataPath = path.join(outputDir, "calldata.txt");
        const metadataPath = path.join(outputDir, "metadata.json");
        
        fs.writeFileSync(proofPath, JSON.stringify(proof, null, 2));
        fs.writeFileSync(publicPath, JSON.stringify(publicSignals, null, 2));
        fs.writeFileSync(calldataPath, calldata);
        fs.writeFileSync(metadataPath, JSON.stringify({
            circuit: circuitName,
            timestamp: new Date().toISOString(),
            provingTimeMs: duration,
            proofValid: isValid,
            publicSignals: publicSignals,
        }, null, 2));
        
        console.log(`\nOutputs written to: ${outputDir}`);
        console.log(`  - proof.json: ZK proof`);
        console.log(`  - public.json: Public signals`);
        console.log(`  - calldata.txt: Solidity calldata`);
        console.log(`  - metadata.json: Proof metadata`);
        
        // Performance check
        if (duration > 5000) {
            console.warn(`\nWARNING: Proving time (${duration}ms) exceeds 5s target!`);
        } else {
            console.log(`\n✓ Proving time within target: ${duration}ms < 5000ms`);
        }
        
    } catch (error) {
        console.error("Error generating proof:", error.message);
        process.exit(1);
    }
}

// Export for programmatic use
module.exports = {
    generateProof,
    verifyProof,
    generateCalldata,
};

// Run CLI if called directly
if (require.main === module) {
    main().catch(console.error);
}

