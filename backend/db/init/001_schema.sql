-- CoA Tracker schema (ALCOA+ aware, pgvector-backed RAG)

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================================================
-- Users & auth
-- =========================================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    role            TEXT NOT NULL DEFAULT 'viewer'
                    CHECK (role IN ('admin','analyst','viewer')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_uidx ON users (lower(email));

-- =========================================================================
-- Reference entities
-- =========================================================================
CREATE TABLE IF NOT EXISTS laboratories (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                        TEXT NOT NULL,
    location                    TEXT,
    address                     TEXT,
    accreditation_body          TEXT,
    accreditation_number        TEXT,
    accreditation_standard      TEXT,
    accreditation_valid_until   DATE,
    contact_email               TEXT,
    contact_phone               TEXT,
    notes                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS laboratories_name_uidx ON laboratories (lower(name));

CREATE TABLE IF NOT EXISTS service_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    contact_name    TEXT,
    contact_email   TEXT,
    contact_phone   TEXT,
    agreement_ref   TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS service_providers_name_uidx ON service_providers (lower(name));

CREATE TABLE IF NOT EXISTS email_sources (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label             TEXT NOT NULL,
    imap_host         TEXT NOT NULL,
    imap_port         INT NOT NULL DEFAULT 993,
    username          TEXT NOT NULL,
    password_enc      TEXT NOT NULL,
    folder            TEXT NOT NULL DEFAULT 'INBOX',
    sender_filter     TEXT,
    subject_filter    TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    last_polled_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================================
-- CoA core
-- =========================================================================
CREATE TABLE IF NOT EXISTS coas (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Document Identity
    doc_code                    TEXT,
    batch_number                TEXT,
    sample_id                   TEXT,

    -- Product
    product_name                TEXT,
    product_specification       TEXT,
    strain_name                 TEXT,
    potency                     TEXT,

    -- Lab
    laboratory_id               UUID REFERENCES laboratories(id) ON DELETE SET NULL,
    service_provider_id         UUID REFERENCES service_providers(id) ON DELETE SET NULL,

    -- Manufacturer / source
    manufacturer_name           TEXT,
    manufacturer_address        TEXT,

    -- Temporal
    sample_receipt_date         DATE,
    analysis_start_date         DATE,
    analysis_completion_date    DATE,

    -- Outcome
    overall_status              TEXT
                                CHECK (overall_status IN ('PASS','FAIL','PENDING','REVIEW') OR overall_status IS NULL),

    -- Document metadata
    original_filename           TEXT,
    file_path                   TEXT,
    file_sha256                 TEXT,
    ingestion_method            TEXT NOT NULL
                                CHECK (ingestion_method IN ('email','upload','scan','api')),
    ingested_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Free-form extracted data + extracted text (for RAG/full-text)
    extracted_text              TEXT,
    extra_fields                JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Versioning
    version                     INT NOT NULL DEFAULT 1,
    superseded_by               UUID REFERENCES coas(id) ON DELETE SET NULL,

    -- Audit
    created_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_by                  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Generated full-text search column
    search_tsv                  TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(doc_code,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(batch_number,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(sample_id,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(product_name,'')), 'B') ||
        setweight(to_tsvector('english', coalesce(strain_name,'')), 'B') ||
        setweight(to_tsvector('english', coalesce(manufacturer_name,'')), 'C') ||
        setweight(to_tsvector('english', coalesce(extracted_text,'')), 'D')
    ) STORED
);

CREATE INDEX IF NOT EXISTS coas_search_tsv_idx ON coas USING GIN (search_tsv);
CREATE INDEX IF NOT EXISTS coas_extra_fields_idx ON coas USING GIN (extra_fields jsonb_path_ops);
CREATE INDEX IF NOT EXISTS coas_batch_lower_idx ON coas (lower(batch_number));
CREATE INDEX IF NOT EXISTS coas_doc_code_lower_idx ON coas (lower(doc_code));
CREATE INDEX IF NOT EXISTS coas_lab_idx ON coas (laboratory_id);
CREATE INDEX IF NOT EXISTS coas_status_idx ON coas (overall_status);
CREATE INDEX IF NOT EXISTS coas_completion_idx ON coas (analysis_completion_date);

-- One row per analytical parameter
CREATE TABLE IF NOT EXISTS coa_parameters (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coa_id              UUID NOT NULL REFERENCES coas(id) ON DELETE CASCADE,
    name                TEXT NOT NULL,
    method              TEXT,
    result              TEXT,
    units               TEXT,
    specification       TEXT,
    pass_fail           TEXT
                        CHECK (pass_fail IN ('PASS','FAIL','N/A') OR pass_fail IS NULL),
    sort_order          INT NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS coa_parameters_coa_idx ON coa_parameters (coa_id);
CREATE INDEX IF NOT EXISTS coa_parameters_name_idx ON coa_parameters (lower(name));

-- =========================================================================
-- Placeholders / dynamic schema
-- =========================================================================
-- A "placeholder" is a field discovered in CoAs that we want to track but
-- isn't part of the core schema yet. Auto-discovered or admin-defined.
CREATE TABLE IF NOT EXISTS placeholder_fields (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key             TEXT NOT NULL,                  -- e.g. "water_activity"
    label           TEXT NOT NULL,                  -- e.g. "Water Activity"
    data_type       TEXT NOT NULL DEFAULT 'string'  -- string|number|date|bool|enum
                    CHECK (data_type IN ('string','number','date','bool','enum')),
    enum_values     TEXT[],
    description     TEXT,
    pattern_hints   TEXT[],                         -- regex/text patterns the extractor uses
    occurrence_count INT NOT NULL DEFAULT 0,        -- how often we have seen it
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed','approved','deprecated')),
    discovered_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at     TIMESTAMPTZ,
    approved_by     UUID REFERENCES users(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS placeholder_fields_key_uidx ON placeholder_fields (lower(key));
CREATE INDEX IF NOT EXISTS placeholder_fields_status_idx ON placeholder_fields (status);

-- =========================================================================
-- RAG: per-document text chunks with embeddings
-- =========================================================================
CREATE TABLE IF NOT EXISTS coa_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    coa_id          UUID NOT NULL REFERENCES coas(id) ON DELETE CASCADE,
    chunk_index     INT NOT NULL,
    content         TEXT NOT NULL,
    embedding       vector(384),
    token_count     INT,
    page            INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS coa_chunks_coa_idx ON coa_chunks (coa_id);
-- HNSW for fast cosine search
CREATE INDEX IF NOT EXISTS coa_chunks_embedding_hnsw
    ON coa_chunks USING hnsw (embedding vector_cosine_ops);

-- =========================================================================
-- Audit log (immutable; ALCOA+)
-- =========================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_email TEXT,
    action      TEXT NOT NULL,                  -- create|update|delete|login|ingest|...
    entity      TEXT NOT NULL,                  -- coas|coa_parameters|users|...
    entity_id   TEXT,
    before      JSONB,
    after       JSONB,
    ip_address  INET,
    user_agent  TEXT
);
CREATE INDEX IF NOT EXISTS audit_log_entity_idx ON audit_log (entity, entity_id);
CREATE INDEX IF NOT EXISTS audit_log_occurred_idx ON audit_log (occurred_at DESC);

-- Prevent updates/deletes on audit_log
CREATE OR REPLACE FUNCTION audit_log_no_modify() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_no_modify();

-- =========================================================================
-- updated_at trigger helper
-- =========================================================================
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_set_updated_at ON users;
CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS coas_set_updated_at ON coas;
CREATE TRIGGER coas_set_updated_at BEFORE UPDATE ON coas
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS labs_set_updated_at ON laboratories;
CREATE TRIGGER labs_set_updated_at BEFORE UPDATE ON laboratories
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Bootstrap admin is created by the backend on startup if no users exist.
