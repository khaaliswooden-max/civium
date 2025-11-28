// ==============================================================================
// CIVIUM MongoDB Initialization Script
// ==============================================================================
// This script runs automatically when the MongoDB container is first created.
// It sets up the initial collections and indexes for regulatory documents.
// ==============================================================================

// Switch to civium_regulations database
db = db.getSiblingDB('civium_regulations');

// ==============================================================================
// Collection: regulations
// ==============================================================================
db.createCollection('regulations', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['_id', 'name', 'jurisdiction', 'effective_date', 'created_at'],
            properties: {
                _id: {
                    bsonType: 'string',
                    description: 'Unique regulation identifier (e.g., REG-GDPR)'
                },
                name: {
                    bsonType: 'string',
                    description: 'Full name of the regulation'
                },
                short_name: {
                    bsonType: 'string',
                    description: 'Common abbreviation'
                },
                jurisdiction: {
                    bsonType: 'string',
                    description: 'Primary jurisdiction code'
                },
                jurisdictions: {
                    bsonType: 'array',
                    items: { bsonType: 'string' },
                    description: 'All applicable jurisdictions'
                },
                sectors: {
                    bsonType: 'array',
                    items: { bsonType: 'string' },
                    description: 'Applicable sectors'
                },
                effective_date: {
                    bsonType: 'date',
                    description: 'When the regulation became effective'
                },
                sunset_date: {
                    bsonType: ['date', 'null'],
                    description: 'Expiration date if applicable'
                },
                source_url: {
                    bsonType: 'string',
                    description: 'Original document URL'
                },
                source_hash: {
                    bsonType: 'string',
                    description: 'SHA-256 hash of source document'
                },
                raw_text: {
                    bsonType: 'string',
                    description: 'Full text of the regulation'
                },
                rml: {
                    bsonType: 'object',
                    description: 'Regulatory Markup Language representation'
                },
                parsing_metadata: {
                    bsonType: 'object',
                    properties: {
                        parser_version: { bsonType: 'string' },
                        model_used: { bsonType: 'string' },
                        confidence_score: { bsonType: 'double' },
                        parsed_at: { bsonType: 'date' }
                    }
                },
                created_at: {
                    bsonType: 'date'
                },
                updated_at: {
                    bsonType: 'date'
                }
            }
        }
    }
});

// Indexes for regulations
db.regulations.createIndex({ 'jurisdiction': 1 });
db.regulations.createIndex({ 'jurisdictions': 1 });
db.regulations.createIndex({ 'sectors': 1 });
db.regulations.createIndex({ 'effective_date': 1 });
db.regulations.createIndex({ 'created_at': -1 });
db.regulations.createIndex({ 'name': 'text', 'short_name': 'text', 'raw_text': 'text' });

// ==============================================================================
// Collection: requirements
// ==============================================================================
db.createCollection('requirements', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['_id', 'regulation_id', 'natural_language', 'tier', 'created_at'],
            properties: {
                _id: {
                    bsonType: 'string',
                    description: 'Unique requirement identifier'
                },
                regulation_id: {
                    bsonType: 'string',
                    description: 'Parent regulation ID'
                },
                article_ref: {
                    bsonType: 'string',
                    description: 'Article/section reference'
                },
                natural_language: {
                    bsonType: 'string',
                    description: 'Human-readable requirement text'
                },
                formal_logic: {
                    bsonType: 'string',
                    description: 'Formal logic representation'
                },
                tier: {
                    enum: ['basic', 'standard', 'advanced'],
                    description: 'Compliance tier'
                },
                verification_method: {
                    enum: ['self_attestation', 'document_review', 'cryptographic_proof', 'on_site_audit'],
                    description: 'How compliance is verified'
                },
                penalty: {
                    bsonType: 'object',
                    properties: {
                        monetary_max: { bsonType: 'number' },
                        formula: { bsonType: 'string' },
                        imprisonment_max_years: { bsonType: 'number' }
                    }
                },
                embeddings: {
                    bsonType: 'object',
                    properties: {
                        model: { bsonType: 'string' },
                        vector: { bsonType: 'array', items: { bsonType: 'double' } },
                        created_at: { bsonType: 'date' }
                    }
                },
                parsing_metadata: {
                    bsonType: 'object'
                },
                created_at: {
                    bsonType: 'date'
                },
                updated_at: {
                    bsonType: 'date'
                }
            }
        }
    }
});

// Indexes for requirements
db.requirements.createIndex({ 'regulation_id': 1 });
db.requirements.createIndex({ 'tier': 1 });
db.requirements.createIndex({ 'verification_method': 1 });
db.requirements.createIndex({ 'created_at': -1 });
db.requirements.createIndex({ 'natural_language': 'text' });

// ==============================================================================
// Collection: regulatory_changes
// ==============================================================================
db.createCollection('regulatory_changes', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['regulation_id', 'change_type', 'detected_at'],
            properties: {
                regulation_id: {
                    bsonType: 'string'
                },
                requirement_id: {
                    bsonType: ['string', 'null']
                },
                change_type: {
                    enum: ['created', 'updated', 'deleted', 'superseded']
                },
                previous_version: {
                    bsonType: 'object'
                },
                new_version: {
                    bsonType: 'object'
                },
                diff: {
                    bsonType: 'object',
                    description: 'Computed difference'
                },
                detected_at: {
                    bsonType: 'date'
                },
                effective_at: {
                    bsonType: 'date'
                },
                notification_sent: {
                    bsonType: 'bool',
                    description: 'Whether stakeholders were notified'
                }
            }
        }
    }
});

// Indexes for regulatory_changes
db.regulatory_changes.createIndex({ 'regulation_id': 1 });
db.regulatory_changes.createIndex({ 'change_type': 1 });
db.regulatory_changes.createIndex({ 'detected_at': -1 });
db.regulatory_changes.createIndex({ 'effective_at': 1 });

// ==============================================================================
// Collection: parsing_corrections
// ==============================================================================
// Stores human expert corrections for self-improvement loop
db.createCollection('parsing_corrections', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['requirement_id', 'correction_type', 'original_value', 'corrected_value', 'created_at'],
            properties: {
                requirement_id: {
                    bsonType: 'string'
                },
                correction_type: {
                    enum: ['text_extraction', 'classification', 'formal_logic', 'tier_assignment', 'other']
                },
                original_value: {
                    bsonType: ['string', 'object']
                },
                corrected_value: {
                    bsonType: ['string', 'object']
                },
                expert_rationale: {
                    bsonType: 'string'
                },
                expert_id: {
                    bsonType: 'string'
                },
                model_version: {
                    bsonType: 'string',
                    description: 'Model version that produced the original'
                },
                used_for_training: {
                    bsonType: 'bool',
                    description: 'Whether this correction has been used for retraining'
                },
                created_at: {
                    bsonType: 'date'
                }
            }
        }
    }
});

// Indexes for parsing_corrections
db.parsing_corrections.createIndex({ 'requirement_id': 1 });
db.parsing_corrections.createIndex({ 'correction_type': 1 });
db.parsing_corrections.createIndex({ 'used_for_training': 1 });
db.parsing_corrections.createIndex({ 'created_at': -1 });

// ==============================================================================
// Collection: ingestion_jobs
// ==============================================================================
db.createCollection('ingestion_jobs', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['status', 'source_type', 'created_at'],
            properties: {
                source_type: {
                    enum: ['url', 'file', 'api']
                },
                source_url: {
                    bsonType: 'string'
                },
                file_path: {
                    bsonType: 'string'
                },
                status: {
                    enum: ['pending', 'processing', 'completed', 'failed']
                },
                progress: {
                    bsonType: 'object',
                    properties: {
                        total_steps: { bsonType: 'int' },
                        completed_steps: { bsonType: 'int' },
                        current_step: { bsonType: 'string' }
                    }
                },
                result: {
                    bsonType: 'object',
                    properties: {
                        regulation_id: { bsonType: 'string' },
                        requirements_count: { bsonType: 'int' }
                    }
                },
                error: {
                    bsonType: 'object',
                    properties: {
                        message: { bsonType: 'string' },
                        stack_trace: { bsonType: 'string' }
                    }
                },
                created_at: {
                    bsonType: 'date'
                },
                started_at: {
                    bsonType: 'date'
                },
                completed_at: {
                    bsonType: 'date'
                }
            }
        }
    }
});

// Indexes for ingestion_jobs
db.ingestion_jobs.createIndex({ 'status': 1 });
db.ingestion_jobs.createIndex({ 'created_at': -1 });

// ==============================================================================
// Seed Data: Example Regulation (GDPR)
// ==============================================================================
db.regulations.insertOne({
    _id: 'REG-GDPR',
    name: 'General Data Protection Regulation',
    short_name: 'GDPR',
    jurisdiction: 'EU',
    jurisdictions: ['EU', 'DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'PL', 'SE', 'AT', 'IE'],
    sectors: ['ALL'],
    effective_date: new Date('2018-05-25'),
    sunset_date: null,
    source_url: 'https://eur-lex.europa.eu/eli/reg/2016/679/oj',
    source_hash: 'sha256:placeholder',
    rml: {
        version: '1.0',
        requirements_count: 99,
        governance_layer: 4
    },
    parsing_metadata: {
        parser_version: '0.1.0',
        model_used: 'manual',
        confidence_score: 1.0,
        parsed_at: new Date()
    },
    created_at: new Date(),
    updated_at: new Date()
});

// Insert example requirement
db.requirements.insertOne({
    _id: 'REQ-GDPR-6-1-a',
    regulation_id: 'REG-GDPR',
    article_ref: 'Article 6(1)(a)',
    natural_language: 'Processing shall be lawful only if and to the extent that the data subject has given consent to the processing of his or her personal data for one or more specific purposes.',
    formal_logic: 'lawful(processing) <- consent_given(data_subject, processing.purposes)',
    tier: 'basic',
    verification_method: 'cryptographic_proof',
    penalty: {
        monetary_max: 20000000,
        formula: 'MAX(20000000, 0.04 * global_annual_turnover)'
    },
    parsing_metadata: {
        parser_version: '0.1.0',
        model_used: 'manual',
        confidence_score: 1.0
    },
    created_at: new Date(),
    updated_at: new Date()
});

// ==============================================================================
// Create application user
// ==============================================================================
db.createUser({
    user: 'civium_app',
    pwd: 'civium_app_password',
    roles: [
        { role: 'readWrite', db: 'civium_regulations' }
    ]
});

print('CIVIUM MongoDB initialization completed successfully.');

