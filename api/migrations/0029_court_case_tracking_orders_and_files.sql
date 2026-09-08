-- Migration: 0029_court_case_tracking_orders_and_files.sql
-- Description: Add interim_orders and filed_documents typed JSONB columns
-- to public.court_case_tracking for persisting orders and files extracted
-- from eCourts case lookup responses.
--
-- Idempotent: safe to re-run.

ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS interim_orders jsonb NOT NULL DEFAULT '[]';
ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS filed_documents jsonb NOT NULL DEFAULT '[]';
