-- Migration: 0022_account_autolock.sql
-- Description: Rolling 5-day login-window autolock. Tracks when the
-- current login window started so the backend can force re-authentication
-- once it lapses (see app/auth.py::_check_account_not_locked). Reset only
-- via the service-role key from POST /api/auth/session-start, called
-- right after a fresh sign-in (web/src/app/login/page.tsx) -- there is
-- deliberately no INSERT/UPDATE policy for the authenticated role, so a
-- caller holding a stale-but-still-cryptographically-valid access token
-- cannot extend their own lock window from the client SDK.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS public.account_security (
    user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    login_started_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.account_security ENABLE ROW LEVEL SECURITY;

-- Owner can read their own window (e.g. a future "locks in N days" UI
-- hint); only the service role (bypasses RLS) can write it.
DROP POLICY IF EXISTS account_security_select_owner ON public.account_security;
CREATE POLICY account_security_select_owner ON public.account_security
    FOR SELECT USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.handle_account_security_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_account_security_updated_at ON public.account_security;
CREATE TRIGGER set_account_security_updated_at
    BEFORE UPDATE ON public.account_security
    FOR EACH ROW EXECUTE FUNCTION public.handle_account_security_updated_at();
