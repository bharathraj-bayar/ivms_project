-- Migration: add processed columns to notification_queue and create offline_events/offline_locations

BEGIN;

ALTER TABLE IF EXISTS notification_queue
    ADD COLUMN IF NOT EXISTS processed BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITH TIME ZONE;

CREATE TABLE IF NOT EXISTS offline_events (
    id SERIAL PRIMARY KEY,
    event_data JSONB,
    user_email TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offline_locations (
    id SERIAL PRIMARY KEY,
    location_data JSONB,
    user_email TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

COMMIT;
