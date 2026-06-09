-- Migration: sync tables and security tables (audit, device_fingerprints, token_families)

BEGIN;

-- Sync tables
CREATE TABLE IF NOT EXISTS sync_state (
    id SERIAL PRIMARY KEY,
    user_email TEXT NOT NULL,
    last_sequence BIGINT DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_changes (
    seq BIGSERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    record_id TEXT,
    operation TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sync_conflicts (
    id SERIAL PRIMARY KEY,
    user_email TEXT,
    record_id TEXT,
    local_payload JSONB,
    server_payload JSONB,
    resolved_payload JSONB,
    conflict_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Security tables
CREATE TABLE IF NOT EXISTS device_fingerprints (
    id SERIAL PRIMARY KEY,
    email TEXT,
    device_id TEXT,
    fingerprint JSONB,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS token_families (
    id SERIAL PRIMARY KEY,
    email TEXT,
    jti TEXT,
    family_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    path TEXT,
    method TEXT,
    status_code INTEGER,
    duration_ms INTEGER,
    ip TEXT,
    user_email TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

COMMIT;
