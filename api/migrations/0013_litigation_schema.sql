-- Migration: 0013_litigation_schema.sql
-- Description: Add additive litigation columns to matters and create litigation_parties, litigation_facts_evidence, and litigation_hearings tables with RLS owner policies.

-- 1. Add additive litigation columns to public.matters
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS court_category text;
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS jurisdiction_state text;
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS cnr_number text;
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS case_number_formatted text;
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS litigation_stage text;
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS court_name text;
ALTER TABLE public.matters ADD COLUMN IF NOT EXISTS bench_name text;

-- 2. Create public.litigation_parties
CREATE TABLE IF NOT EXISTS public.litigation_parties (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    party_type text NOT NULL, -- e.g. 'Petitioner', 'Respondent', 'Plaintiff', 'Defendant', 'Intervener'
    party_name text NOT NULL,
    party_number integer NOT NULL DEFAULT 1,
    address text,
    advocate_name text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_litigation_parties_matter ON public.litigation_parties(matter_id);

ALTER TABLE public.litigation_parties ENABLE ROW LEVEL SECURITY;

CREATE POLICY litigation_parties_select_owner ON public.litigation_parties
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_parties.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_parties_insert_owner ON public.litigation_parties
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_parties.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_parties_update_owner ON public.litigation_parties
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_parties.matter_id
              AND m.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_parties.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_parties_delete_owner ON public.litigation_parties
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_parties.matter_id
              AND m.user_id = auth.uid()
        )
    );

-- 3. Create public.litigation_facts_evidence
CREATE TABLE IF NOT EXISTS public.litigation_facts_evidence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    event_date date,
    fact_summary text NOT NULL,
    exhibit_number text, -- e.g. 'Exhibit P-1'
    document_title text,
    relevance_notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_litigation_facts_matter ON public.litigation_facts_evidence(matter_id, event_date);

ALTER TABLE public.litigation_facts_evidence ENABLE ROW LEVEL SECURITY;

CREATE POLICY litigation_facts_select_owner ON public.litigation_facts_evidence
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_facts_evidence.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_facts_insert_owner ON public.litigation_facts_evidence
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_facts_evidence.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_facts_update_owner ON public.litigation_facts_evidence
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_facts_evidence.matter_id
              AND m.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_facts_evidence.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_facts_delete_owner ON public.litigation_facts_evidence
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_facts_evidence.matter_id
              AND m.user_id = auth.uid()
        )
    );

-- 4. Create public.litigation_hearings
CREATE TABLE IF NOT EXISTS public.litigation_hearings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matter_id uuid NOT NULL REFERENCES public.matters(id) ON DELETE CASCADE,
    hearing_date date NOT NULL,
    cause_list_item_no integer,
    purpose_of_hearing text, -- e.g. 'Admission', 'Framing of Issues', 'Arguments on IA'
    ia_number text, -- ARB Recommendation: Interim Application tracking
    hearing_outcome text,
    next_hearing_date date,
    status text NOT NULL DEFAULT 'Scheduled', -- 'Scheduled', 'Heard', 'Adjourned', 'Passed Over'
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_litigation_hearings_matter ON public.litigation_hearings(matter_id, hearing_date);

ALTER TABLE public.litigation_hearings ENABLE ROW LEVEL SECURITY;

CREATE POLICY litigation_hearings_select_owner ON public.litigation_hearings
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_hearings.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_hearings_insert_owner ON public.litigation_hearings
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_hearings.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_hearings_update_owner ON public.litigation_hearings
    FOR UPDATE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_hearings.matter_id
              AND m.user_id = auth.uid()
        )
    ) WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_hearings.matter_id
              AND m.user_id = auth.uid()
        )
    );

CREATE POLICY litigation_hearings_delete_owner ON public.litigation_hearings
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM public.matters m
            WHERE m.id = litigation_hearings.matter_id
              AND m.user_id = auth.uid()
        )
    );
