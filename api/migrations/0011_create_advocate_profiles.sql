-- Migration: 0011_create_advocate_profiles.sql
-- Description: Create canonical advocate_profiles table for multi-module practice identity with state-scoped Bar Council uniqueness and conservative backfill

CREATE TABLE IF NOT EXISTS public.advocate_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name text,
    designation text NOT NULL DEFAULT 'Advocate',
    bar_number text,
    enrollment_state text,
    enrollment_year integer CHECK (enrollment_year >= 1950),
    primary_court text,
    high_court_roll_no text,
    aor_code text,
    firm_name text,
    phone text CHECK (phone IS NULL OR phone ~ '^\+?[1-9]\d{1,14}$'),
    office_address text,
    avatar_url text, -- Storage object URL / path (e.g. 'https://.../avatars/user.jpg'), NOT Base64
    practice_areas text[] NOT NULL DEFAULT '{}',
    states_of_practice text[] NOT NULL DEFAULT '{}',
    languages_spoken text[] NOT NULL DEFAULT '{}',
    rera_advocate_reg_no text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_advocate_profiles_bar_state UNIQUE (bar_number, enrollment_state)
);

-- Performance & Audit Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_advocate_profiles_user_id ON public.advocate_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_advocate_profiles_bar_state ON public.advocate_profiles(bar_number, enrollment_state);
CREATE INDEX IF NOT EXISTS idx_advocate_profiles_enrollment_state ON public.advocate_profiles(enrollment_state);

-- Enable Row-Level Security
ALTER TABLE public.advocate_profiles ENABLE ROW LEVEL SECURITY;

-- Row-Level Security Policies (Strict Owner Isolation)
CREATE POLICY advocate_profiles_select_owner ON public.advocate_profiles
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY advocate_profiles_insert_owner ON public.advocate_profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY advocate_profiles_update_owner ON public.advocate_profiles
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY advocate_profiles_delete_owner ON public.advocate_profiles
    FOR DELETE USING (auth.uid() = user_id);

-- Automatic Timestamp Update Trigger Procedure
CREATE OR REPLACE FUNCTION public.handle_advocate_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_advocate_profiles_updated_at ON public.advocate_profiles;
CREATE TRIGGER set_advocate_profiles_updated_at
    BEFORE UPDATE ON public.advocate_profiles
    FOR EACH ROW EXECUTE FUNCTION public.handle_advocate_profiles_updated_at();

-- Conservative Idempotent Backfill: Only backfill profiles for users with non-empty metadata
INSERT INTO public.advocate_profiles (
    user_id,
    full_name,
    designation,
    bar_number,
    enrollment_state,
    primary_court,
    phone,
    office_address,
    avatar_url
)
SELECT
    u.id AS user_id,
    u.raw_user_meta_data->>'full_name' AS full_name,
    'Advocate' AS designation,
    u.raw_user_meta_data->>'bar_number' AS bar_number,
    u.raw_user_meta_data->>'enrollment_state' AS enrollment_state,
    u.raw_user_meta_data->>'primary_court' AS primary_court,
    u.raw_user_meta_data->>'phone' AS phone,
    u.raw_user_meta_data->>'office_address' AS office_address,
    u.raw_user_meta_data->>'avatar_url' AS avatar_url
FROM auth.users u
WHERE u.raw_user_meta_data->>'full_name' IS NOT NULL 
  AND u.raw_user_meta_data->>'full_name' <> ''
ON CONFLICT (user_id) DO NOTHING;
