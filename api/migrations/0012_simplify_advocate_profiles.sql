-- Migration: 0012_simplify_advocate_profiles.sql
-- Description: Simplify advocate_profiles schema by removing deprecated fields to match active production database state

-- 1. Drop redundant indexes & constraints depending on removed columns
DROP INDEX IF EXISTS public.idx_advocate_profiles_bar_state;
DROP INDEX IF EXISTS public.idx_advocate_profiles_enrollment_state;
ALTER TABLE public.advocate_profiles DROP CONSTRAINT IF EXISTS uq_advocate_profiles_bar_state;

-- 2. Drop deprecated columns safely
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS enrollment_state;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS enrollment_year;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS high_court_roll_no;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS aor_code;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS firm_name;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS practice_areas;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS states_of_practice;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS languages_spoken;
ALTER TABLE public.advocate_profiles DROP COLUMN IF EXISTS rera_advocate_reg_no;
