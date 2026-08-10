import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

export type Matter = {
  id: string;
  title: string;
  client_name: string | null;
  module: "litigation" | "contracts" | "rera" | "consulting";
  template_id?: string | null;
  court_category?: string | null;
  jurisdiction_state?: string | null;
  cnr_number?: string | null;
  case_number_formatted?: string | null;
  litigation_stage?: string | null;
  court_name?: string | null;
  bench_name?: string | null;
  created_at: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model_used: string | null;
  created_at: string;
};

async function authedFetch(path: string, init?: RequestInit) {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not signed in");

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export function listMatters(): Promise<Matter[]> {
  return authedFetch("/api/matters");
}

export function getMatter(matterId: string): Promise<Matter> {
  return authedFetch(`/api/matters/${matterId}`);
}

export function createMatter(input: {
  title: string;
  client_name?: string;
  module: Matter["module"];
  template_id?: string;
  court_category?: string;
  jurisdiction_state?: string;
  cnr_number?: string;
  case_number_formatted?: string;
}): Promise<Matter> {
  return authedFetch("/api/matters", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listParties(matterId: string) {
  return authedFetch(`/api/matters/${matterId}/parties`);
}

export function addParty(matterId: string, partyData: Record<string, unknown>) {
  return authedFetch(`/api/matters/${matterId}/parties`, {
    method: "POST",
    body: JSON.stringify(partyData),
  });
}

export function deleteParty(matterId: string, partyId: string) {
  return authedFetch(`/api/matters/${matterId}/parties/${partyId}`, {
    method: "DELETE",
  });
}

export function listEvidence(matterId: string) {
  return authedFetch(`/api/matters/${matterId}/evidence`);
}

export function addEvidence(matterId: string, factData: Record<string, unknown>) {
  return authedFetch(`/api/matters/${matterId}/evidence`, {
    method: "POST",
    body: JSON.stringify(factData),
  });
}

export function deleteEvidence(matterId: string, evidenceId: string) {
  return authedFetch(`/api/matters/${matterId}/evidence/${evidenceId}`, {
    method: "DELETE",
  });
}

/** Multipart upload — a real exhibit document, not just a text label.
 * Deliberately does NOT go through authedFetch: that helper always sets
 * Content-Type: application/json and JSON.stringifies the body, which
 * would corrupt a multipart/form-data request. The browser must set its
 * own Content-Type header (with the multipart boundary) for FormData. */
export async function uploadEvidenceFile(
  matterId: string,
  file: File,
  fields: { event_date?: string; exhibit_number?: string; document_title?: string; relevance_notes?: string }
) {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not signed in");

  const formData = new FormData();
  formData.append("file", file);
  for (const [key, value] of Object.entries(fields)) {
    if (value) formData.append(key, value);
  }

  const res = await fetch(`${API_URL}/api/matters/${matterId}/evidence/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${session.access_token}` },
    body: formData,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export function listHearings(matterId: string) {
  return authedFetch(`/api/matters/${matterId}/hearings`);
}

export function addHearing(matterId: string, hearingData: Record<string, unknown>) {
  return authedFetch(`/api/matters/${matterId}/hearings`, {
    method: "POST",
    body: JSON.stringify(hearingData),
  });
}

export function calculateLimitation(payload: {
  cause_of_action_date: string;
  suit_category: string;
  exclusion_days?: number;
  selected_article?: string;
}) {
  return authedFetch("/api/litigation/limitation-calculator", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// --- AI Case Analysis (Sprint 3.5.3) ----------------------------------------

export type ChronologicalFact = {
  event_date: string | null;
  fact_summary: string;
  exhibit_number: string | null;
  has_evidence_file: boolean;
};

export type ApplicableStatute = {
  act: string;
  section_no: string;
  year: number | null;
  chunk_excerpt: string;
  score: number;
};

export type CauseOfActionStatuteRef = { act: string; section_no: string; grounded: boolean };

export type CauseOfAction = {
  title: string;
  description: string;
  supporting_facts: string[];
  statutes_relied_upon: CauseOfActionStatuteRef[];
};

export type PotentialRisk = { risk: string; severity: "High" | "Medium" | "Low"; mitigation: string | null };

export type PrecedentMention = {
  case_name: string;
  note: string;
  status: "verified" | "unverified";
  ik_url: string | null;
  court: string | null;
};

export type CaseAnalysis = {
  id: string;
  matter_id: string;
  version_no: number;
  matter_summary: string;
  chronological_facts: ChronologicalFact[];
  missing_information: string[];
  applicable_statutes: ApplicableStatute[];
  possible_causes_of_action: CauseOfAction[];
  jurisdiction_summary: { recommended_forum: ForumResultOption; is_unambiguous: boolean } | null;
  limitation_summary: {
    limitation_expiry_date: string;
    is_barred: boolean;
    days_remaining: number;
    primary_article: { article_number: string; description: string; statutory_period_years: number; trigger_event: string; notes?: string | null };
    condonation_required: boolean;
    condonation_notes: string;
  } | null;
  potential_risks: PotentialRisk[];
  evidence_gaps: string[];
  recommended_next_steps: string[];
  possible_precedents: PrecedentMention[];
  model_used: string | null;
  generation_warning: string | null;
  created_at: string;
  notice: string;
};

type ForumResultOption = {
  forum_name: string;
  court_category: string;
  territorial_basis: string;
  pecuniary_basis: string;
  governing_provisions: string[];
  confidence: string;
  assumptions: string[];
};

export function generateCaseAnalysis(
  matterId: string,
  payload: {
    limitation?: CaseAnalysis["limitation_summary"];
    forum?: { recommended_forum: ForumResultOption; is_unambiguous: boolean };
  }
): Promise<CaseAnalysis> {
  return authedFetch(`/api/matters/${matterId}/case-analysis`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listCaseAnalyses(matterId: string): Promise<CaseAnalysis[]> {
  return authedFetch(`/api/matters/${matterId}/case-analysis`);
}

export function determineForum(payload: {
  suit_type: string;
  claim_value_inr: number;
  jurisdiction_state: string;
  defendant_residence_state?: string;
  cause_of_action_location?: string;
  property_location_state?: string;
}) {
  return authedFetch("/api/litigation/forum-advisor", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Title-only update — backs the auto-generating-title UX (debounced
 * saves as party names fill in, and manual click-to-edit overrides). */
export function updateMatter(matterId: string, input: { title: string }): Promise<Matter> {
  return authedFetch(`/api/matters/${matterId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function listMessages(matterId: string): Promise<Message[]> {
  return authedFetch(`/api/matters/${matterId}/messages`);
}

export function sendMessage(
  matterId: string,
  content: string
): Promise<[Message, Message]> {
  return authedFetch(`/api/matters/${matterId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

// --- Contracts (Sprint 2) ----------------------------------------------------

export type IntakeFieldOption = string | { value: string; label: string };

export type IntakeField = {
  key: string;
  label: string;
  type: "text" | "textarea" | "select" | "boolean" | "date" | "list";
  options?: IntakeFieldOption[];
  required?: boolean;
  default?: unknown;
  help?: string;
  condition?: { field: string; equals?: unknown; not_equals?: unknown };
  // type: "list" only — a repeatable list of sub-objects (deliverables,
  // benefits, fixtures, ...). item_schema reuses this same IntakeField
  // shape so each item renders with the exact same primitives as a
  // top-level field, just recursively.
  item_schema?: IntakeField[];
  item_singular_label?: string;
  min_items?: number;
  max_items?: number | null;
};

/** Sprint 2 Phase 1 Session 1: schema-declared field groups, rendered as
 * collapsible accordion sections on the intake form. `summary_template`
 * is a string of short clauses joined by " · ", each containing one or
 * more `{{field_key}}` placeholders — see
 * web/src/lib/group-summary.ts for the exact rendering rule (a clause
 * drops entirely if every placeholder inside it is empty, rather than
 * leaving a trailing space or a dangling separator). `state` is never
 * assigned to a group — it renders in the persistent sidebar instead,
 * see IntakeForm. */
export type IntakeFieldGroup = {
  id: string;
  label: string;
  field_keys: string[];
  summary_template: string;
};

export type IntakeSchema = {
  template_key: string;
  title: string;
  variant_field?: string;
  fields: IntakeField[];
  // Optional for backward compatibility with a template that hasn't
  // been migrated to the groups pattern yet — IntakeForm falls back to
  // one flat ungrouped section (its pre-Session-1 behavior) when absent.
  groups?: IntakeFieldGroup[];
};

export type Template = {
  id: string;
  name: string;
  category: string;
  review_status: "beta" | "reviewed";
  states_supported: string[];
  template_key: string | null;
};

export type TemplateDetail = Template & { intake_schema: IntakeSchema };

export function listTemplates(): Promise<Template[]> {
  return authedFetch("/api/templates");
}

export function getTemplate(templateId: string): Promise<TemplateDetail> {
  return authedFetch(`/api/templates/${templateId}`);
}

export type ClauseFill = {
  clause_key: string;
  generated_text: string;
  model_used: string;
};

export type Draft = {
  draft_version_id: string;
  version_no: number;
  docx_path: string;
  clause_fills: ClauseFill[];
  full_text: string;
};

export type DraftVersion = {
  id: string;
  template_id: string;
  version_no: number;
  docx_path: string;
  change_summary: string | null;
  created_at: string;
};

export function generateDraft(
  matterId: string,
  input: { template_id: string; form_data: Record<string, unknown>; amendment_note?: string }
): Promise<Draft> {
  return authedFetch(`/api/matters/${matterId}/drafts`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listDrafts(matterId: string): Promise<DraftVersion[]> {
  return authedFetch(`/api/matters/${matterId}/drafts`);
}

/** File downloads need the auth header but aren't JSON — fetch as a blob
 * and trigger the browser's normal download flow via a temporary link. */
async function downloadFile(path: string, filename: string) {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not signed in");

  const res = await fetch(`${API_URL}${path}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadDraftDocx(draftVersionId: string, filename: string) {
  return downloadFile(`/api/drafts/${draftVersionId}/download`, filename);
}

export function downloadDraftPdf(draftVersionId: string, filename: string) {
  return downloadFile(`/api/drafts/${draftVersionId}/download.pdf`, filename);
}

export type StateRule = {
  state: string;
  instrument: string;
  stamp_duty: string | null;
  registration_req: string | null;
  notes: string | null;
  source_url: string | null;
  last_verified: string | null;
};

export function getStateRules(state: string, instrument: string): Promise<StateRule[]> {
  const params = new URLSearchParams({ state, instrument });
  return authedFetch(`/api/state-rules?${params.toString()}`);
}

export type TemplateClause = {
  id: string;
  clause_key: string;
  display_order: number;
  clause_type: "fixed_boilerplate" | "llm_fillable";
  applicable_condition: { field: string; equals?: unknown; not_equals?: unknown } | null;
  heading: string | null;
  current_text: string;
  review_status: "unreviewed" | "kept" | "redrafted" | "deleted";
};

export function listTemplateClauses(templateId: string): Promise<TemplateClause[]> {
  return authedFetch(`/api/templates/${templateId}/clauses`);
}

export function reviewClause(
  templateId: string,
  clauseId: string,
  input: { decision: "keep" | "redraft" | "delete"; redraft_text?: string; reviewer_notes?: string }
): Promise<TemplateClause> {
  return authedFetch(`/api/templates/${templateId}/clauses/${clauseId}/review`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Keeps every currently-unreviewed fixed_boilerplate clause on a
 * template in one action — never touches llm_fillable clauses or a
 * clause that's already been reviewed. Returns the updated rows. */
export function bulkKeepBoilerplate(templateId: string): Promise<TemplateClause[]> {
  return authedFetch(`/api/templates/${templateId}/clauses/bulk-keep-boilerplate`, {
    method: "POST",
  });
}
