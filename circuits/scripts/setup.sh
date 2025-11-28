#!/bin/bash
# =============================================================================
# ZK-SNARK Trusted Setup Script
# =============================================================================
# 
# This script performs the trusted setup ceremony for all Civium circuits.
# 
# Prerequisites:
#   - Node.js 18+
#   - circom 2.1.6+
#   - snarkjs 0.7+
#
# Usage:
#   ./setup.sh [circuit_name]
#   
# Examples:
#   ./setup.sh                      # Setup all circuits
#   ./setup.sh compliance_threshold # Setup single circuit
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CIRCUITS_DIR="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$CIRCUITS_DIR/build"
PTAU_DIR="$CIRCUITS_DIR/ptau"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v circom &> /dev/null; then
        log_error "circom not found. Install with: npm install -g circom"
        exit 1
    fi
    
    if ! command -v snarkjs &> /dev/null; then
        log_error "snarkjs not found. Install with: npm install -g snarkjs"
        exit 1
    fi
    
    if ! command -v node &> /dev/null; then
        log_error "Node.js not found"
        exit 1
    fi
    
    log_info "All prerequisites satisfied"
}

# Download Powers of Tau if not present
download_ptau() {
    mkdir -p "$PTAU_DIR"
    
    # Using powersOfTau28_hez_final_14.ptau (suitable for circuits up to 2^14 constraints)
    # This is sufficient for our compliance circuits
    local PTAU_FILE="$PTAU_DIR/powersOfTau28_hez_final_14.ptau"
    
    if [ -f "$PTAU_FILE" ]; then
        log_info "Powers of Tau file already exists"
        return
    fi
    
    log_info "Downloading Powers of Tau (this may take a while)..."
    curl -L -o "$PTAU_FILE" \
        "https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_14.ptau"
    
    log_info "Powers of Tau downloaded successfully"
}

# Compile a single circuit
compile_circuit() {
    local circuit_name=$1
    local circuit_file="$CIRCUITS_DIR/${circuit_name}.circom"
    local build_subdir="$BUILD_DIR/$circuit_name"
    
    if [ ! -f "$circuit_file" ]; then
        log_error "Circuit file not found: $circuit_file"
        return 1
    fi
    
    mkdir -p "$build_subdir"
    
    log_info "Compiling circuit: $circuit_name"
    
    # Compile circom to R1CS, WASM, and C++
    circom "$circuit_file" \
        --r1cs \
        --wasm \
        --sym \
        --c \
        -o "$build_subdir" \
        -l "$CIRCUITS_DIR/../node_modules"
    
    log_info "Circuit $circuit_name compiled successfully"
    
    # Display circuit info
    snarkjs r1cs info "$build_subdir/${circuit_name}.r1cs"
}

# Generate proving and verification keys
generate_keys() {
    local circuit_name=$1
    local build_subdir="$BUILD_DIR/$circuit_name"
    local ptau_file="$PTAU_DIR/powersOfTau28_hez_final_14.ptau"
    
    log_info "Generating keys for: $circuit_name"
    
    # Phase 2: Circuit-specific setup
    log_info "Starting Groth16 setup (Phase 2)..."
    snarkjs groth16 setup \
        "$build_subdir/${circuit_name}.r1cs" \
        "$ptau_file" \
        "$build_subdir/${circuit_name}_0000.zkey"
    
    # Contribute to ceremony (in production, multiple parties would contribute)
    log_info "Contributing to ceremony..."
    snarkjs zkey contribute \
        "$build_subdir/${circuit_name}_0000.zkey" \
        "$build_subdir/${circuit_name}_0001.zkey" \
        --name="Civium Phase 2 contribution" \
        -v -e="$(head -c 64 /dev/urandom | xxd -p)"
    
    # Export final zkey
    log_info "Exporting final proving key..."
    snarkjs zkey export verificationkey \
        "$build_subdir/${circuit_name}_0001.zkey" \
        "$build_subdir/verification_key.json"
    
    # Rename final zkey
    mv "$build_subdir/${circuit_name}_0001.zkey" "$build_subdir/proving_key.zkey"
    rm -f "$build_subdir/${circuit_name}_0000.zkey"
    
    # Export Solidity verifier
    log_info "Generating Solidity verifier..."
    snarkjs zkey export solidityverifier \
        "$build_subdir/proving_key.zkey" \
        "$build_subdir/${circuit_name}_verifier.sol"
    
    log_info "Keys generated successfully for: $circuit_name"
}

# Verify the setup
verify_setup() {
    local circuit_name=$1
    local build_subdir="$BUILD_DIR/$circuit_name"
    local ptau_file="$PTAU_DIR/powersOfTau28_hez_final_14.ptau"
    
    log_info "Verifying setup for: $circuit_name"
    
    snarkjs zkey verify \
        "$build_subdir/${circuit_name}.r1cs" \
        "$ptau_file" \
        "$build_subdir/proving_key.zkey"
    
    log_info "Setup verified successfully"
}

# Process a single circuit
process_circuit() {
    local circuit_name=$1
    
    log_info "=========================================="
    log_info "Processing circuit: $circuit_name"
    log_info "=========================================="
    
    compile_circuit "$circuit_name"
    generate_keys "$circuit_name"
    verify_setup "$circuit_name"
    
    log_info "Circuit $circuit_name setup complete!"
}

# Main
main() {
    local circuit_name="${1:-}"
    
    log_info "Civium ZK-SNARK Setup Script"
    log_info "=============================="
    
    check_prerequisites
    download_ptau
    
    mkdir -p "$BUILD_DIR"
    
    if [ -n "$circuit_name" ]; then
        # Process single circuit
        process_circuit "$circuit_name"
    else
        # Process all circuits
        for circuit_file in "$CIRCUITS_DIR"/*.circom; do
            if [ -f "$circuit_file" ]; then
                local name=$(basename "$circuit_file" .circom)
                process_circuit "$name"
            fi
        done
    fi
    
    log_info "=============================="
    log_info "Setup complete!"
    log_info "=============================="
}

main "$@"

