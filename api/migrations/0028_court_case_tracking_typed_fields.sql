-- Migration: 0028_court_case_tracking_typed_fields.sql
-- Description: court_case_tracking.provider_metadata stores the whole raw
-- eCourts envelope, but CourtDataGateway.case_lookup() already extracts
-- typed, VERIFIED fields (court_name, judge, caseStatus, petitioners,
-- respondents -- confirmed against a real response 2026-09-06, see that
-- method's own docstring) that were previously only surfaced transiently
-- by GET /api/court-lookup-preview and then thrown away -- a synced
-- matter had no stable, typed way to show its own court/status/parties
-- without a caller re-parsing provider_metadata's raw JSON directly,
-- which app/services/court_data_gateway.py's module docstring explicitly
-- says should never happen outside that module. Persisting the same
-- already-verified fields app/services/court_sync.py computes on every
-- sync closes that gap -- no new/guessed fields are introduced here.

ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS court_name text;
ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS judge text;
ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS case_status text;
ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS petitioners jsonb NOT NULL DEFAULT '[]';
ALTER TABLE public.court_case_tracking ADD COLUMN IF NOT EXISTS respondents jsonb NOT NULL DEFAULT '[]';
