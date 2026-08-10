-- Migration: 0017_citations_match_confidence.sql
-- Description: Sprint 3.6 Phase 5 (TICKET-17/18) — citation reliability.
-- (1) match_confidence: exposes _best_match()'s own word-overlap score
--     (previously computed internally and discarded) so "verified" carries
--     a confidence signal, not just a bare boolean.
-- (2) Certification-round evidence (Sprint 3.5.6): a real, well-known case
--     (Anathula Sudhakar v. P. Buchi Reddy) came back "unverified" live,
--     then "verified" on an immediate independent retry — the live Indian
--     Kanoon search is non-deterministic call-to-call, and this table
--     previously cached that first, transiently-wrong "unverified" result
--     forever (no retry path existed once status="unverified" was cached).
--     app/services/citations.py now only trusts a cached "verified" row as
--     final; a cached "unverified" row gets one fresh live re-attempt
--     before falling back to it. This column lets that retry logic record
--     how many times a citation has been re-checked, for observability.

ALTER TABLE public.citations ADD COLUMN IF NOT EXISTS match_confidence double precision;
ALTER TABLE public.citations ADD COLUMN IF NOT EXISTS recheck_count integer NOT NULL DEFAULT 0;
