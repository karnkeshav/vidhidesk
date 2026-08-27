-- Migration: 0023_account_autolock_payment_toggle.sql
-- Description: Turns account_security (0022) into a free-trial paywall:
-- login_started_at is now written once (first login only -- see
-- app/routers/auth.py) rather than reset on every sign-in, and a new
-- payment_received flag permanently bypasses the 5-day trial window in
-- app/auth.py::_check_account_not_locked once flipped. There is
-- deliberately no policy granting the authenticated role write access to
-- this column -- payment_received is only ever flipped by hand, in the
-- Supabase Table Editor (service-role/postgres context, bypasses RLS),
-- after Nitesh has actually received payment from that advocate.
-- Idempotent: safe to re-run.

ALTER TABLE public.account_security
    ADD COLUMN IF NOT EXISTS payment_received boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.account_security.payment_received IS
    'Flip to true by hand in the Supabase Table Editor once payment is received. Permanently bypasses the 5-day free-trial window for this user (app/auth.py::_check_account_not_locked) -- no re-login required, takes effect on that user''s next request (subject to the backend''s <=60s in-process cache).';

COMMENT ON COLUMN public.account_security.login_started_at IS
    'Set once, on this user''s very first POST /api/auth/session-start call (free-trial start) -- never overwritten on later logins. See app/routers/auth.py.';
