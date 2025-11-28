-- =============================================================================
-- Migration: Entity Management Schema
-- Version: 003
-- Description: Full PostgreSQL schema for entity management and compliance assessments
-- Author: Civium
-- Date: 2024-01-01
-- =============================================================================

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS core;

-- =============================================================================
-- ENUMS
-- =============================================================================

-- Entity type enum
DO $$ BEGIN
    CREATE TYPE core.entity_type AS ENUM (
        'corporation', 'sme', 'startup', 'government',
        'non_profit', 'individual', 'partnership', 'subsidiary'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Entity size enum
DO $$ BEGIN
    CREATE TYPE core.entity_size AS ENUM (
        'micro', 'small', 'medium', 'large'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Compliance tier enum
DO $$ BEGIN
    CREATE TYPE core.compliance_tier AS ENUM (
        'basic', 'standard', 'advanced'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Assessment status enum
DO $$ BEGIN
    CREATE TYPE core.assessment_status AS ENUM (
        'draft', 'in_progress', 'pending_review',
        'approved', 'rejected', 'completed', 'archived'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Assessment type enum
DO $$ BEGIN
    CREATE TYPE core.assessment_type AS ENUM (
        'initial', 'periodic', 'triggered',
        'remediation', 'audit', 'self_assessment'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Item status enum
DO $$ BEGIN
    CREATE TYPE core.item_status AS ENUM (
        'compliant', 'non_compliant', 'partial',
        'not_applicable', 'pending', 'remediation'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Evidence type enum
DO $$ BEGIN
    CREATE TYPE core.evidence_type AS ENUM (
        'document', 'attestation', 'certificate', 'audit_report',
        'screenshot', 'log', 'record', 'contract', 'training', 'zk_proof'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Evidence status enum
DO $$ BEGIN
    CREATE TYPE core.evidence_status AS ENUM (
        'pending', 'verified', 'rejected', 'expired', 'superseded'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Score type enum
DO $$ BEGIN
    CREATE TYPE core.score_type AS ENUM (
        'overall', 'jurisdiction', 'sector', 'regulation', 'tier', 'risk'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- =============================================================================
-- ENTITIES TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.entities (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Basic info
    name VARCHAR(255) NOT NULL,
    legal_name VARCHAR(500),
    entity_type core.entity_type NOT NULL DEFAULT 'corporation',
    size core.entity_size DEFAULT 'small',
    
    -- Location and scope
    primary_jurisdiction VARCHAR(10) NOT NULL,
    jurisdictions VARCHAR(10)[] DEFAULT '{}',
    sectors VARCHAR(50)[] DEFAULT '{}',
    
    -- Business details
    employee_count INTEGER,
    annual_revenue NUMERIC(20, 2),
    founding_date TIMESTAMPTZ,
    
    -- External identifiers
    registration_number VARCHAR(100),
    tax_id VARCHAR(50),
    lei VARCHAR(20),  -- Legal Entity Identifier
    did VARCHAR(100), -- Decentralized Identifier
    external_id VARCHAR(100),
    
    -- Compliance status
    compliance_tier core.compliance_tier NOT NULL DEFAULT 'basic',
    compliance_score NUMERIC(5, 4) CHECK (compliance_score >= 0 AND compliance_score <= 1),
    risk_score NUMERIC(5, 4) CHECK (risk_score >= 0 AND risk_score <= 1),
    tier_override BOOLEAN DEFAULT false,
    tier_override_reason TEXT,
    
    -- Assessment tracking
    last_assessment_id UUID,
    last_assessment_at TIMESTAMPTZ,
    next_assessment_due TIMESTAMPTZ,
    assessment_frequency_days INTEGER DEFAULT 90,
    
    -- Requirement counts (cached)
    total_requirements INTEGER DEFAULT 0,
    compliant_requirements INTEGER DEFAULT 0,
    non_compliant_requirements INTEGER DEFAULT 0,
    pending_requirements INTEGER DEFAULT 0,
    
    -- Contact info
    primary_contact_name VARCHAR(255),
    primary_contact_email VARCHAR(255),
    primary_contact_phone VARCHAR(50),
    
    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state_province VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(2),  -- ISO 3166-1 alpha-2
    
    -- Additional data
    metadata JSONB DEFAULT '{}',
    tags VARCHAR(50)[] DEFAULT '{}',
    notes TEXT,
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMPTZ  -- Soft delete
);

-- Entity indexes
CREATE INDEX IF NOT EXISTS ix_entities_name ON core.entities (name);
CREATE INDEX IF NOT EXISTS ix_entities_jurisdiction ON core.entities (primary_jurisdiction);
CREATE INDEX IF NOT EXISTS ix_entities_tier ON core.entities (compliance_tier);
CREATE INDEX IF NOT EXISTS ix_entities_type ON core.entities (entity_type);
CREATE INDEX IF NOT EXISTS ix_entities_created ON core.entities (created_at);
CREATE INDEX IF NOT EXISTS ix_entities_jurisdictions ON core.entities USING GIN (jurisdictions);
CREATE INDEX IF NOT EXISTS ix_entities_sectors ON core.entities USING GIN (sectors);
CREATE INDEX IF NOT EXISTS ix_entities_active ON core.entities (id) WHERE deleted_at IS NULL;

-- =============================================================================
-- ASSESSMENTS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.assessments (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Entity relationship
    entity_id UUID NOT NULL REFERENCES core.entities(id) ON DELETE CASCADE,
    
    -- Assessment info
    assessment_type core.assessment_type NOT NULL DEFAULT 'periodic',
    status core.assessment_status NOT NULL DEFAULT 'draft',
    
    -- Scope
    jurisdictions VARCHAR(10)[],
    sectors VARCHAR(50)[],
    regulation_ids VARCHAR(50)[],
    
    -- Dates
    assessment_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    due_date TIMESTAMPTZ,
    valid_until TIMESTAMPTZ,
    
    -- Results
    overall_score NUMERIC(5, 4) CHECK (overall_score >= 0 AND overall_score <= 1),
    risk_level VARCHAR(20),
    
    -- Counts
    total_items INTEGER DEFAULT 0,
    compliant_items INTEGER DEFAULT 0,
    non_compliant_items INTEGER DEFAULT 0,
    partial_items INTEGER DEFAULT 0,
    not_applicable_items INTEGER DEFAULT 0,
    pending_items INTEGER DEFAULT 0,
    
    -- People
    assessor_id UUID,
    assessor_name VARCHAR(255),
    reviewer_id UUID,
    reviewer_name VARCHAR(255),
    approver_id UUID,
    approver_name VARCHAR(255),
    
    -- Notes
    summary TEXT,
    findings TEXT,
    recommendations TEXT,
    attachments JSONB DEFAULT '[]',
    
    -- Configuration
    methodology VARCHAR(100),
    confidence_level NUMERIC(5, 4),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

-- Assessment indexes
CREATE INDEX IF NOT EXISTS ix_assessments_entity ON core.assessments (entity_id);
CREATE INDEX IF NOT EXISTS ix_assessments_status ON core.assessments (status);
CREATE INDEX IF NOT EXISTS ix_assessments_type ON core.assessments (assessment_type);
CREATE INDEX IF NOT EXISTS ix_assessments_date ON core.assessments (assessment_date);
CREATE INDEX IF NOT EXISTS ix_assessments_entity_status ON core.assessments (entity_id, status);

-- =============================================================================
-- ASSESSMENT ITEMS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.assessment_items (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationships
    assessment_id UUID NOT NULL REFERENCES core.assessments(id) ON DELETE CASCADE,
    requirement_id VARCHAR(100) NOT NULL,
    regulation_id VARCHAR(100),
    
    -- Requirement context (cached)
    requirement_text TEXT,
    requirement_tier VARCHAR(20),
    article_ref VARCHAR(100),
    
    -- Assessment result
    status core.item_status NOT NULL DEFAULT 'pending',
    score NUMERIC(5, 4),
    
    -- Evidence
    evidence_ids UUID[] DEFAULT '{}',
    evidence_summary TEXT,
    
    -- Assessment details
    assessed_at TIMESTAMPTZ,
    assessed_by UUID,
    assessment_method VARCHAR(50),
    
    -- Findings
    finding TEXT,
    gap_description TEXT,
    risk_impact VARCHAR(20),
    
    -- Remediation
    remediation_required BOOLEAN DEFAULT false,
    remediation_plan TEXT,
    remediation_due_date TIMESTAMPTZ,
    remediation_status VARCHAR(50),
    
    -- Notes
    notes TEXT,
    internal_notes TEXT,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Assessment item indexes
CREATE INDEX IF NOT EXISTS ix_assessment_items_assessment ON core.assessment_items (assessment_id);
CREATE INDEX IF NOT EXISTS ix_assessment_items_requirement ON core.assessment_items (requirement_id);
CREATE INDEX IF NOT EXISTS ix_assessment_items_status ON core.assessment_items (status);
CREATE UNIQUE INDEX IF NOT EXISTS ix_assessment_items_composite ON core.assessment_items (assessment_id, requirement_id);

-- =============================================================================
-- EVIDENCE TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.evidence (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Entity relationship
    entity_id UUID NOT NULL REFERENCES core.entities(id) ON DELETE CASCADE,
    
    -- Evidence info
    title VARCHAR(255) NOT NULL,
    description TEXT,
    evidence_type core.evidence_type NOT NULL DEFAULT 'document',
    status core.evidence_status NOT NULL DEFAULT 'pending',
    
    -- Requirements supported
    requirement_ids VARCHAR(100)[] DEFAULT '{}',
    regulation_ids VARCHAR(100)[] DEFAULT '{}',
    
    -- File information
    file_name VARCHAR(255),
    file_path VARCHAR(500),
    file_size INTEGER,
    file_type VARCHAR(100),
    content_hash VARCHAR(64),
    
    -- Cryptographic proofs
    zk_proof TEXT,
    signature TEXT,
    signer_did VARCHAR(100),
    
    -- Validity period
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    is_perpetual BOOLEAN DEFAULT false,
    
    -- Verification
    verified BOOLEAN DEFAULT false,
    verified_at TIMESTAMPTZ,
    verified_by UUID,
    verifier_name VARCHAR(255),
    verification_method VARCHAR(50),
    verification_notes TEXT,
    
    -- Coverage
    coverage_percentage INTEGER DEFAULT 100,
    
    -- Source
    source VARCHAR(255),
    source_url VARCHAR(500),
    external_id VARCHAR(100),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    tags VARCHAR(50)[] DEFAULT '{}',
    
    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    updated_by UUID,
    deleted_at TIMESTAMPTZ
);

-- Evidence indexes
CREATE INDEX IF NOT EXISTS ix_evidence_entity ON core.evidence (entity_id);
CREATE INDEX IF NOT EXISTS ix_evidence_type ON core.evidence (evidence_type);
CREATE INDEX IF NOT EXISTS ix_evidence_status ON core.evidence (status);
CREATE INDEX IF NOT EXISTS ix_evidence_created ON core.evidence (created_at);
CREATE INDEX IF NOT EXISTS ix_evidence_expiry ON core.evidence (valid_until);
CREATE INDEX IF NOT EXISTS ix_evidence_active ON core.evidence (id) WHERE deleted_at IS NULL;

-- =============================================================================
-- SCORE HISTORY TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.score_history (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Entity relationship
    entity_id UUID NOT NULL REFERENCES core.entities(id) ON DELETE CASCADE,
    
    -- Score info
    score_type core.score_type NOT NULL DEFAULT 'overall',
    scope VARCHAR(100),
    
    -- The score
    score NUMERIC(5, 4) NOT NULL CHECK (score >= 0 AND score <= 1),
    previous_score NUMERIC(5, 4),
    
    -- Change tracking
    change NUMERIC(6, 4),
    change_percentage NUMERIC(7, 4),
    
    -- Context
    assessment_id UUID,
    reason VARCHAR(255),
    
    -- Breakdown
    breakdown JSONB DEFAULT '{}',
    
    -- Statistics
    total_requirements NUMERIC(10, 0),
    compliant_count NUMERIC(10, 0),
    non_compliant_count NUMERIC(10, 0),
    
    -- Timestamp
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- Score history indexes
CREATE INDEX IF NOT EXISTS ix_score_history_entity ON core.score_history (entity_id);
CREATE INDEX IF NOT EXISTS ix_score_history_type ON core.score_history (score_type);
CREATE INDEX IF NOT EXISTS ix_score_history_recorded ON core.score_history (recorded_at);
CREATE INDEX IF NOT EXISTS ix_score_history_entity_type ON core.score_history (entity_id, score_type);

-- =============================================================================
-- REQUIREMENTS CACHE TABLE (for efficient querying without Neo4j)
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.requirements (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Reference
    regulation_id VARCHAR(100) NOT NULL,
    
    -- Content
    text TEXT NOT NULL,
    tier VARCHAR(20) NOT NULL DEFAULT 'basic',
    article_ref VARCHAR(100),
    
    -- Scope
    jurisdictions VARCHAR(10)[] DEFAULT '{}',
    sectors VARCHAR(50)[] DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    
    -- Timestamps
    effective_from TIMESTAMPTZ,
    effective_until TIMESTAMPTZ,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Requirements indexes
CREATE INDEX IF NOT EXISTS ix_requirements_regulation ON core.requirements (regulation_id);
CREATE INDEX IF NOT EXISTS ix_requirements_tier ON core.requirements (tier);
CREATE INDEX IF NOT EXISTS ix_requirements_active ON core.requirements (is_active);
CREATE INDEX IF NOT EXISTS ix_requirements_jurisdictions ON core.requirements USING GIN (jurisdictions);
CREATE INDEX IF NOT EXISTS ix_requirements_sectors ON core.requirements USING GIN (sectors);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION core.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
DROP TRIGGER IF EXISTS entities_updated_at ON core.entities;
CREATE TRIGGER entities_updated_at
    BEFORE UPDATE ON core.entities
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at();

DROP TRIGGER IF EXISTS assessments_updated_at ON core.assessments;
CREATE TRIGGER assessments_updated_at
    BEFORE UPDATE ON core.assessments
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at();

DROP TRIGGER IF EXISTS assessment_items_updated_at ON core.assessment_items;
CREATE TRIGGER assessment_items_updated_at
    BEFORE UPDATE ON core.assessment_items
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at();

DROP TRIGGER IF EXISTS evidence_updated_at ON core.evidence;
CREATE TRIGGER evidence_updated_at
    BEFORE UPDATE ON core.evidence
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at();

DROP TRIGGER IF EXISTS requirements_updated_at ON core.requirements;
CREATE TRIGGER requirements_updated_at
    BEFORE UPDATE ON core.requirements
    FOR EACH ROW
    EXECUTE FUNCTION core.update_updated_at();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE core.entities IS 'Regulated entities subject to compliance requirements';
COMMENT ON TABLE core.assessments IS 'Point-in-time compliance assessments';
COMMENT ON TABLE core.assessment_items IS 'Individual requirement assessments within an assessment';
COMMENT ON TABLE core.evidence IS 'Supporting evidence for compliance claims';
COMMENT ON TABLE core.score_history IS 'Historical compliance scores for trend analysis';
COMMENT ON TABLE core.requirements IS 'Cached requirements from compliance graph';

