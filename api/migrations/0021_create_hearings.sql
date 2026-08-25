-- Migration: 0021_create_hearings.sql
-- Description: Create hearings table for the Calendar / cause-list feature
-- (advocate-scheduled court appearances), owner-isolated per advocate the
-- same way advocate_profiles (0011) and matters (0001) already are.

CREATE TABLE IF NOT EXISTS public.hearings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    matter_id uuid REFERENCES public.matters(id) ON DELETE SET NULL,
    case_no text,
    title text NOT NULL,
    court text,
    bench text,
    item_no text,
    stage text,
    hearing_at timestamptz NOT NULL,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS hearings_user_id_idx ON public.hearings(user_id);
CREATE INDEX IF NOT EXISTS hearings_hearing_at_idx ON public.hearings(hearing_at);
CREATE INDEX IF NOT EXISTS hearings_matter_id_idx ON public.hearings(matter_id);

-- Enable Row-Level Security
ALTER TABLE public.hearings ENABLE ROW LEVEL SECURITY;

-- Row-Level Security Policies (Strict Owner Isolation)
CREATE POLICY hearings_select_owner ON public.hearings
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY hearings_insert_owner ON public.hearings
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY hearings_update_owner ON public.hearings
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY hearings_delete_owner ON public.hearings
    FOR DELETE USING (auth.uid() = user_id);

-- Automatic Timestamp Update Trigger Procedure
CREATE OR REPLACE FUNCTION public.handle_hearings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_hearings_updated_at ON public.hearings;
CREATE TRIGGER set_hearings_updated_at
    BEFORE UPDATE ON public.hearings
    FOR EACH ROW EXECUTE FUNCTION public.handle_hearings_updated_at();
