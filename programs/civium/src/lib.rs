use anchor_lang::prelude::*;

declare_id!("H1eSx6ij1Q296Tzss62AHuamn1rD4a9MkDapYu1CyvVM");

// ─── Events ──────────────────────────────��─────────────────────────────────

#[event]
pub struct ComplianceStateChange {
    pub entity_id: String,
    pub status: String,       // "COMPLIANT" | "VIOLATION" | "FLAGGED"
    pub score: u8,
    pub domain: String,       // "halal" | "esg" | "itar"
    pub evidence_hash: [u8; 32],
    pub timestamp: i64,
}

// ─── Accounts ──────────────────────────────────────────────────────────────

#[account]
pub struct ComplianceRecord {
    pub authority: Pubkey,
    pub entity_id: String,    // max 64 bytes
    pub status: String,       // max 16 bytes
    pub score: u8,
    pub domain: String,       // max 16 bytes
    pub evidence_hash: [u8; 32],
    pub timestamp: i64,
    pub bump: u8,
}

impl ComplianceRecord {
    // 8 discriminator + 32 authority + 4+64 entity_id + 4+16 status
    // + 1 score + 4+16 domain + 32 evidence_hash + 8 timestamp + 1 bump
    pub const LEN: usize = 8 + 32 + (4 + 64) + (4 + 16) + 1 + (4 + 16) + 32 + 8 + 1;
}

// ─── Error codes ─────────────────────────────────────────────────���─────────

#[error_code]
pub enum CiviumError {
    #[msg("Invalid status: must be COMPLIANT, VIOLATION, or FLAGGED")]
    InvalidStatus,
    #[msg("Invalid domain: must be halal, esg, or itar")]
    InvalidDomain,
    #[msg("Score must be between 0 and 100")]
    InvalidScore,
    #[msg("Entity ID must not be empty")]
    EmptyEntityId,
    #[msg("Unauthorized: signer is not the record authority")]
    Unauthorized,
}

// ─── Program ───────────────────────���───────────────────────────────────────

#[program]
pub mod civium {
    use super::*;

    /// Create a new compliance record for an entity.
    /// Emits ComplianceStateChange so the ZWM indexer can pick it up.
    pub fn evaluate_compliance(
        ctx: Context<EvaluateCompliance>,
        entity_id: String,
        status: String,
        score: u8,
        domain: String,
        evidence_hash: [u8; 32],
    ) -> Result<()> {
        // Validate inputs
        require!(!entity_id.is_empty(), CiviumError::EmptyEntityId);
        require!(score <= 100, CiviumError::InvalidScore);
        require!(
            matches!(status.as_str(), "COMPLIANT" | "VIOLATION" | "FLAGGED"),
            CiviumError::InvalidStatus
        );
        require!(
            matches!(domain.as_str(), "halal" | "esg" | "itar"),
            CiviumError::InvalidDomain
        );

        let record = &mut ctx.accounts.compliance_record;
        let clock = Clock::get()?;

        record.authority = ctx.accounts.authority.key();
        record.entity_id = entity_id.clone();
        record.status = status.clone();
        record.score = score;
        record.domain = domain.clone();
        record.evidence_hash = evidence_hash;
        record.timestamp = clock.unix_timestamp;
        record.bump = ctx.bumps.compliance_record;

        emit!(ComplianceStateChange {
            entity_id,
            status,
            score,
            domain,
            evidence_hash,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }

    /// Update an existing compliance record.
    /// Emits ComplianceStateChange so the ZWM indexer creates a new snapshot.
    pub fn update_compliance(
        ctx: Context<UpdateCompliance>,
        status: String,
        score: u8,
        domain: String,
        evidence_hash: [u8; 32],
    ) -> Result<()> {
        require!(score <= 100, CiviumError::InvalidScore);
        require!(
            matches!(status.as_str(), "COMPLIANT" | "VIOLATION" | "FLAGGED"),
            CiviumError::InvalidStatus
        );
        require!(
            matches!(domain.as_str(), "halal" | "esg" | "itar"),
            CiviumError::InvalidDomain
        );

        let record = &mut ctx.accounts.compliance_record;
        require!(
            record.authority == ctx.accounts.authority.key(),
            CiviumError::Unauthorized
        );

        let clock = Clock::get()?;
        let entity_id = record.entity_id.clone();

        record.status = status.clone();
        record.score = score;
        record.domain = domain.clone();
        record.evidence_hash = evidence_hash;
        record.timestamp = clock.unix_timestamp;

        emit!(ComplianceStateChange {
            entity_id,
            status,
            score,
            domain,
            evidence_hash,
            timestamp: clock.unix_timestamp,
        });

        Ok(())
    }
}

// ─── Instruction Contexts ──────────────────────────────���───────────────────

#[derive(Accounts)]
#[instruction(entity_id: String)]
pub struct EvaluateCompliance<'info> {
    #[account(
        init,
        payer = authority,
        space = ComplianceRecord::LEN,
        seeds = [b"compliance", entity_id.as_bytes()],
        bump,
    )]
    pub compliance_record: Account<'info, ComplianceRecord>,

    #[account(mut)]
    pub authority: Signer<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct UpdateCompliance<'info> {
    #[account(
        mut,
        seeds = [b"compliance", compliance_record.entity_id.as_bytes()],
        bump = compliance_record.bump,
    )]
    pub compliance_record: Account<'info, ComplianceRecord>,

    pub authority: Signer<'info>,
}
