-- Migration: add user_devices and notification_history tables for FCM integration
-- Run this against the IVMS Postgres DB (TimescaleDB compatible)

BEGIN;

-- Table to store device push tokens per user
CREATE TABLE IF NOT EXISTS user_devices (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    device_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    fcm_token TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    last_seen TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_user_devices_email ON user_devices(email);
CREATE INDEX IF NOT EXISTS idx_user_devices_device_id ON user_devices(device_id);

-- History of notifications dispatched to users/devices
CREATE TABLE IF NOT EXISTS notification_history (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT,
    email TEXT,
    device_id TEXT,
    title TEXT,
    body TEXT,
    payload JSONB,
    severity TEXT,
    event_type TEXT,
    delivered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    delivered_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_notification_history_tenant ON notification_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_notification_history_email ON notification_history(email);

COMMIT;
