"""
ZK-SNARK Proof Verification
===========================

Verify ZK-SNARK compliance proofs off-chain and on-chain.

Version: 1.0.0
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from shared.logging import get_logger
from shared.zk.models import (
    ProofWithMetadata,
    VerificationResult,
    ZKProof,
)

logger = get_logger(__name__)

DEFAULT_BUILD_DIR = Path(__file__).parent.parent.parent / "circuits" / "build"


class ComplianceVerifier:
    """
    ZK-SNARK proof verifier.
    
    Supports both off-chain verification (via snarkjs) and
    on-chain verification (via smart contract).
    """
    
    def __init__(self, build_dir: str | Path | None = None):
        """
        Initialize the verifier.
        
        Args:
            build_dir: Path to circuit build directory
        """
        self.build_dir = Path(build_dir) if build_dir else DEFAULT_BUILD_DIR
    
    async def verify_off_chain(
        self,
        proof: ProofWithMetadata,
    ) -> VerificationResult:
        """
        Verify a proof off-chain using snarkjs.
        
        Args:
            proof: The proof to verify
        
        Returns:
            VerificationResult with verification status
        """
        circuit_name = proof.metadata.circuit_name
        vkey_path = self.build_dir / circuit_name / "verification_key.json"
        
        if not vkey_path.exists():
            return VerificationResult(
                valid=False,
                verification_time_ms=0,
                error=f"Verification key not found: {vkey_path}",
            )
        
        # Write proof and public signals to temp files
        circuit_dir = self.build_dir / circuit_name
        proof_file = circuit_dir / "verify_proof_temp.json"
        public_file = circuit_dir / "verify_public_temp.json"
        
        try:
            with open(proof_file, "w") as f:
                json.dump(proof.proof.model_dump(), f)
            with open(public_file, "w") as f:
                json.dump(proof.public_signals.signals, f)
            
            start_time = time.time()
            
            # Run snarkjs verify
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "npx", "snarkjs", "groth16", "verify",
                    str(vkey_path),
                    str(public_file),
                    str(proof_file),
                ],
                capture_output=True,
                text=True,
                cwd=self.build_dir.parent,
            )
            
            verification_time_ms = int((time.time() - start_time) * 1000)
            
            # Check result
            is_valid = "OK" in result.stdout or result.returncode == 0
            
            logger.info(
                "zk_proof_verified",
                circuit=circuit_name,
                valid=is_valid,
                verification_time_ms=verification_time_ms,
            )
            
            return VerificationResult(
                valid=is_valid,
                commitment=proof.commitment,
                verification_time_ms=verification_time_ms,
                error=result.stderr if not is_valid else None,
            )
            
        finally:
            # Cleanup
            for temp_file in [proof_file, public_file]:
                if temp_file.exists():
                    temp_file.unlink()
    
    async def verify_on_chain(
        self,
        proof: ProofWithMetadata,
        contract_address: str,
        rpc_url: str,
    ) -> VerificationResult:
        """
        Verify a proof on-chain via smart contract.
        
        Args:
            proof: The proof to verify
            contract_address: Address of ComplianceVerifier contract
            rpc_url: Ethereum RPC URL
        
        Returns:
            VerificationResult with transaction details
        """
        # This would use web3.py to call the smart contract
        # For now, return a placeholder
        
        logger.info(
            "zk_on_chain_verification_not_implemented",
            contract=contract_address,
        )
        
        return VerificationResult(
            valid=False,
            verification_time_ms=0,
            error="On-chain verification not yet implemented",
        )


# Convenience functions

async def verify_threshold_proof(
    proof: ProofWithMetadata,
    build_dir: str | Path | None = None,
) -> VerificationResult:
    """
    Verify a threshold compliance proof.
    
    Args:
        proof: The proof to verify
        build_dir: Optional path to circuit build directory
    
    Returns:
        VerificationResult
    """
    verifier = ComplianceVerifier(build_dir)
    return await verifier.verify_off_chain(proof)


async def verify_range_proof(
    proof: ProofWithMetadata,
    build_dir: str | Path | None = None,
) -> VerificationResult:
    """Verify a range proof."""
    verifier = ComplianceVerifier(build_dir)
    return await verifier.verify_off_chain(proof)


async def verify_tier_proof(
    proof: ProofWithMetadata,
    build_dir: str | Path | None = None,
) -> VerificationResult:
    """Verify a tier membership proof."""
    verifier = ComplianceVerifier(build_dir)
    return await verifier.verify_off_chain(proof)


def generate_solidity_calldata(proof: ProofWithMetadata) -> dict[str, Any]:
    """
    Generate calldata for on-chain verification.
    
    Returns:
        Dictionary with proof array and public inputs for Solidity
    """
    calldata = proof.proof.to_calldata()
    public_inputs = proof.public_signals.to_int_list()
    
    return {
        "proof": calldata,
        "publicInputs": public_inputs,
        "solidityCall": f"verifyProof({calldata}, {public_inputs})",
    }

