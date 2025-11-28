-- ==============================================================================
-- CIVIUM PostgreSQL Initialization Script
-- ==============================================================================
-- This script runs automatically when the PostgreSQL container is first created.
-- It sets up the initial database schema for the Entity Assessment Service.
-- ==============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- GIN indexes for JSONB

-- ==============================================================================
-- Schema: core
-- ==============================================================================
CREATE SCHEMA IF NOT EXISTS core;

-- Compliance Tiers enum
CREATE TYPE core.compliance_tier AS ENUM ('basic', 'standard', 'advanced');

-- Entity Types enum
CREATE TYPE core.entity_type AS ENUM (
    'individual',
    'corporation',
    'partnership',
    'non_profit',
    'government',
    'supranational'
);

-- Assessment Status enum
CREATE TYPE core.assessment_status AS ENUM (
    'draft',
    'in_progress',
    'pending_review',
    'approved',
    'rejected',
    'expired'
);

-- ==============================================================================
-- Table: entities
-- ==============================================================================
CREATE TABLE IF NOT EXISTS core.entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id VARCHAR(100) UNIQUE,  -- e.g., LEI, DUNS
    name VARCHAR(500) NOT NULL,
    entity_type core.entity_type NOT NULL,
    
    -- Classification
    sectors TEXT[] NOT NULL DEFAULT '{}',
    jurisdictions TEXT[] NOT NULL DEFAULT '{}',
    size VARCHAR(50),  -- micro, small, medium, large
    
    -- Compliance
    compliance_tier core.compliance_tier NOT NULL DEFAULT 'basic',
    compliance_score DECIMAL(3, 2) CHECK (compliance_score >= 0 AND compliance_score <= 5),
    risk_score DECIMAL(3, 2) CHECK (risk_score >= 0 AND risk_score <= 1),
    
    -- Metadata
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_assessment_at TIMESTAMPTZ,
    
    -- Soft delete
    deleted_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_entities_external_id ON core.entities(external_id);
CREATE INDEX idx_entities_name_trgm ON core.entities USING gin(name gin_trgm_ops);
CREATE INDEX idx_entities_entity_type ON core.entities(entity_type);
CREATE INDEX idx_entities_compliance_tier ON core.entities(compliance_tier);
CREATE INDEX idx_entities_sectors ON core.entities USING gin(sectors);
CREATE INDEX idx_entities_jurisdictions ON core.entities USING gin(jurisdictions);
CREATE INDEX idx_entities_compliance_score ON core.entities(compliance_score);
CREATE INDEX idx_entities_created_at ON core.entities(created_at);
CREATE INDEX idx_entities_deleted_at ON core.entities(deleted_at) WHERE deleted_at IS NULL;

-- ==============================================================================
-- Table: assessments
-- ==============================================================================
CREATE TABLE IF NOT EXISTS core.assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES core.entities(id) ON DELETE CASCADE,
    
    -- Assessment details
    assessment_type VARCHAR(100) NOT NULL,  -- e.g., 'annual_review', 'incident_response'
    status core.assessment_status NOT NULL DEFAULT 'draft',
    
    -- Scores
    overall_score DECIMAL(3, 2) CHECK (overall_score >= 0 AND overall_score <= 5),
    criterion_scores JSONB NOT NULL DEFAULT '[]',
    
    -- Evidence
    evidence_refs TEXT[] NOT NULL DEFAULT '{}',
    
    -- Workflow
    assessor_id UUID,
    reviewer_id UUID,
    
    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_assessments_entity_id ON core.assessments(entity_id);
CREATE INDEX idx_assessments_status ON core.assessments(status);
CREATE INDEX idx_assessments_assessment_type ON core.assessments(assessment_type);
CREATE INDEX idx_assessments_started_at ON core.assessments(started_at);
CREATE INDEX idx_assessments_expires_at ON core.assessments(expires_at);

-- ==============================================================================
-- Table: compliance_events
-- ==============================================================================
CREATE TABLE IF NOT EXISTS core.compliance_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_id UUID NOT NULL REFERENCES core.entities(id) ON DELETE CASCADE,
    assessment_id UUID REFERENCES core.assessments(id) ON DELETE SET NULL,
    
    -- Event details
    event_type VARCHAR(100) NOT NULL,  -- e.g., 'score_change', 'tier_upgrade', 'violation'
    event_data JSONB NOT NULL DEFAULT '{}',
    
    -- Severity
    severity VARCHAR(20) NOT NULL DEFAULT 'info',  -- info, warning, critical
    
    -- Timestamps
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Partitioning key (for future partitioning)
    year_month INTEGER NOT NULL DEFAULT EXTRACT(YEAR FROM NOW()) * 100 + EXTRACT(MONTH FROM NOW())
);

-- Indexes
CREATE INDEX idx_compliance_events_entity_id ON core.compliance_events(entity_id);
CREATE INDEX idx_compliance_events_event_type ON core.compliance_events(event_type);
CREATE INDEX idx_compliance_events_occurred_at ON core.compliance_events(occurred_at);
CREATE INDEX idx_compliance_events_severity ON core.compliance_events(severity);
CREATE INDEX idx_compliance_events_year_month ON core.compliance_events(year_month);

-- ==============================================================================
-- Table: users (for authentication)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS core.users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    
    -- Profile
    full_name VARCHAR(255),
    
    -- Roles
    roles TEXT[] NOT NULL DEFAULT '{"user"}',
    
    -- Entity association (optional)
    entity_id UUID REFERENCES core.entities(id) ON DELETE SET NULL,
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_users_email ON core.users(email);
CREATE INDEX idx_users_entity_id ON core.users(entity_id);
CREATE INDEX idx_users_is_active ON core.users(is_active);

-- ==============================================================================
-- Table: api_keys
-- ==============================================================================
CREATE TABLE IF NOT EXISTS core.api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    
    -- Key details
    key_hash VARCHAR(255) NOT NULL,  -- SHA-256 hash of the API key
    key_prefix VARCHAR(10) NOT NULL,  -- First 10 chars for identification
    name VARCHAR(100) NOT NULL,
    
    -- Permissions
    scopes TEXT[] NOT NULL DEFAULT '{"read"}',
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX idx_api_keys_user_id ON core.api_keys(user_id);
CREATE INDEX idx_api_keys_key_prefix ON core.api_keys(key_prefix);
CREATE INDEX idx_api_keys_is_active ON core.api_keys(is_active);

-- ==============================================================================
-- Functions: Auto-update timestamps
-- ==============================================================================
CREATE OR REPLACE FUNCTION core.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers
CREATE TRIGGER trigger_entities_updated_at
    BEFORE UPDATE ON core.entities
    FOR EACH ROW EXECUTE FUNCTION core.update_updated_at();

CREATE TRIGGER trigger_assessments_updated_at
    BEFORE UPDATE ON core.assessments
    FOR EACH ROW EXECUTE FUNCTION core.update_updated_at();

CREATE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON core.users
    FOR EACH ROW EXECUTE FUNCTION core.update_updated_at();

-- ==============================================================================
-- Initial Data: Admin User (password: changeme)
-- ==============================================================================
INSERT INTO core.users (email, hashed_password, full_name, roles, is_active, is_verified)
VALUES (
    'admin@civium.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VrNqHCv3.ZsHGa',  -- changeme
    'System Administrator',
    ARRAY['admin', 'user'],
    true,
    true
) ON CONFLICT (email) DO NOTHING;

-- ==============================================================================
-- Grants
-- ==============================================================================
GRANT ALL PRIVILEGES ON SCHEMA core TO civium;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO civium;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core TO civium;

-- ==============================================================================
-- Completion
-- ==============================================================================
DO $$
BEGIN
    RAISE NOTICE 'CIVIUM PostgreSQL initialization completed successfully.';
END $$;

