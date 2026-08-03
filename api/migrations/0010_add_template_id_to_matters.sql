-- Migration 0010: Add template_id to matters table for Matter-centric loading model
ALTER TABLE matters ADD COLUMN IF NOT EXISTS template_id uuid REFERENCES templates(id);
