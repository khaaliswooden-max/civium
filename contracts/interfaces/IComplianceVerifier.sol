// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title IComplianceVerifier
 * @notice Interface for ZK-SNARK compliance verification
 */
interface IComplianceVerifier {
    /**
     * @notice Verify a compliance threshold proof
     * @param _proof The Groth16 proof
     * @param _threshold The minimum score threshold
     * @param _entityHash Hash of entity identifier
     * @return commitment The score commitment
     */
    function verifyThreshold(
        uint256[8] calldata _proof,
        uint256 _threshold,
        uint256 _entityHash
    ) external returns (uint256 commitment);
    
    /**
     * @notice Verify a range proof
     */
    function verifyRange(
        uint256[8] calldata _proof,
        uint256 _minScore,
        uint256 _maxScore,
        uint256 _entityHash
    ) external returns (uint256 commitment);
    
    /**
     * @notice Verify a tier membership proof
     */
    function verifyTier(
        uint256[8] calldata _proof,
        uint8 _tier,
        uint256 _entityHash
    ) external returns (uint256 commitment);
    
    /**
     * @notice Check if entity has valid verification
     */
    function hasValidVerification(
        uint256 _entityHash,
        uint256 _maxAge
    ) external view returns (bool valid);
    
    /**
     * @notice Get latest commitment for entity
     */
    function latestCommitments(uint256 _entityHash) external view returns (uint256);
    
    /**
     * @notice Get last verification time for entity
     */
    function lastVerificationTime(uint256 _entityHash) external view returns (uint256);
}

