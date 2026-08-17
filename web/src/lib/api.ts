import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

// TEMP DEBUG (Auth Request Forensics Sprint, 2026-08-11): traces the exact
// lifecycle of an authedFetch call so a live repro can show where a
// request dies before FastAPI ever sees it. Deliberately never logs the
// JWT, the Authorization header value, or any request/response body --
// only structural facts (url, attempt number, status, abort reason).
// Remove once the forensic sprint concludes.
const DEBUG_AUTH_FETCH = true;
function debugLog(event: string, data?: Record<string, unknown>) {
  if (DEBUG_AUTH_FETCH) console.debug(`[authedFetch] ${event}`, data ?? "");
}

// Frontend resilience for transient upstream failures (2026-08-10): a real,
// live incident showed the backend's own auth check occasionally getting a
// 520 from Supabase's Cloudflare edge (Render <-> Supabase connectivity, not
// our code, not fixable here) — surfaced to the client as a 401 wrapping
// "Invalid session: Server error '520' ...". Retrying the exact same
// request a moment later succeeds, since the failure is transient at the
// network/edge layer, not a genuinely dead session. This never changes what
// counts as authenticated — a real invalid/expired session (no 5xx in the
// wrapped message) is still rejected immediately, not retried.
const TRANSIENT_RETRY_DELAYS_MS = [600, 1500, 3000];

// 2026-08-10, same day as the retry logic above: a real report of "stuck on
// 'Loading...' for 3 minutes, then the error" showed the actual gap -- the
// retry delays above only bound the wait *between* attempts, never the
// attempt itself. A hung request (connection opens, server/edge never
// responds at all -- not even an error) has no built-in browser fetch
// timeout, so it sits until the OS/network stack's own timeout, which can
// genuinely be minutes. Aborting a stuck attempt after FETCH_TIMEOUT_MS
// turns that into a fast, retryable failure through the exact same path a
// network error already takes below, bounding the worst case to roughly
// (FETCH_TIMEOUT_MS + backoff) x 4 attempts, not an open-ended hang.
const FETCH_TIMEOUT_MS = 12000;

function isTransientFailure(status: number, bodyText: string): boolean {
  if (status >= 500) return true;
  if (status === 401) return /server error '?5\d\d/i.test(bodyText);
  return false;
}

async function fetchWithTimeout(url: string, init: RequestInit): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, FETCH_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (err) {
    debugLog("request cancelled", {
      url,
      reason: timedOut ? "internal-timeout" : (err instanceof Error ? err.name : String(err)),
    });
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

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

// Retry eligibility (Auth Request Forensics Sprint follow-up, 2026-08-14):
// TRANSIENT_RETRY_DELAYS_MS above assumes replaying the exact same request
// is harmless -- true for a GET, and true in practice for our PATCH/DELETE
// endpoints (they converge on the same end state no matter how many times
// they're applied). It is NOT true for a persistent POST that creates a new
// row per call (new matter, new draft_version, new message, new audit
// entry, ...): a request that actually reached the server and succeeded,
// but whose response was lost to a timeout/network blip, would silently
// create a duplicate on "retry". That's exactly how one Generate Draft
// click produced three draft_versions in a prior E2E run. `retry: false`
// opts a call out of the retry loop below -- it still gets exactly one
// attempt (still subject to FETCH_TIMEOUT_MS), it just never replays.
// Defaults to true so every pre-existing call site keeps its current
// behavior unchanged; any *new* persistent/non-idempotent write should be
// added with `{ retry: false }` explicitly rather than relying on the
// default.
async function authedFetch(path: string, init?: RequestInit, options?: { retry?: boolean }) {
  const retryEligible = options?.retry ?? true;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  debugLog("request started", { url: `${API_URL}${path}`, authPresent: !!session });
  if (!session) throw new Error("Not signed in");

  for (let attempt = 0; ; attempt++) {
    debugLog("attempt", { url: `${API_URL}${path}`, attempt });
    let res: Response;
    try {
      res = await fetchWithTimeout(`${API_URL}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          ...(init?.headers ?? {}),
        },
      });
    } catch (err) {
      // A network-level failure (including a request a CORS-blocked
      // response shows up as, and now an aborted-for-hanging-too-long
      // request too) never gives us a status code at all -- always
      // eligible for the same retry treatment as a 5xx, unless this call
      // opted out via `retry: false` (see note above authedFetch).
      if (retryEligible && attempt < TRANSIENT_RETRY_DELAYS_MS.length) {
        debugLog("retrying after network-level failure", { url: `${API_URL}${path}`, attempt });
        await new Promise((r) => setTimeout(r, TRANSIENT_RETRY_DELAYS_MS[attempt]));
        continue;
      }
      debugLog("request failed permanently", { url: `${API_URL}${path}`, attempt });
      throw err instanceof Error ? err : new Error(String(err));
    }

    debugLog("request completed", { url: `${API_URL}${path}`, status: res.status, attempt });
    if (res.ok) return res.json();

    const body = await res.text();
    if (retryEligible && isTransientFailure(res.status, body) && attempt < TRANSIENT_RETRY_DELAYS_MS.length) {
      debugLog("retrying after transient status", { url: `${API_URL}${path}`, status: res.status, attempt });
      await new Promise((r) => setTimeout(r, TRANSIENT_RETRY_DELAYS_MS[attempt]));
      continue;
    }

    // Reverted (2026-08-10): this used to also hard-redirect to /login on
    // any exhausted 401, on the theory that a dead session should bounce
    // the user back to sign in. That was wrong and caused a real reload
    // loop in production: /login's own useEffect redirects straight back
    // to /dashboard whenever a local session is still present (see
    // app/login/page.tsx), which it is here -- this redirect fires when
    // Supabase itself is degraded for longer than the retry window, not
    // when the local session is actually gone, so login would have hit
    // the exact same failing Supabase call and bounced back immediately.
    // Two pages full-page-reloading into each other, forever, is worse
    // than the raw error this was meant to improve on. Session-death
    // detection stays where it already correctly lives: authed-shell.tsx's
    // onAuthStateChange/getSession() checks, driven by the Supabase SDK's
    // own authoritative state, not by one failed backend call.
    throw new ApiError(res.status, `${res.status} ${res.statusText}: ${body}`);
  }
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
  return authedFetch(
    "/api/matters",
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    { retry: false }
  );
}

export function listParties(matterId: string) {
  return authedFetch(`/api/matters/${matterId}/parties`);
}

export function addParty(matterId: string, partyData: Record<string, unknown>) {
  return authedFetch(
    `/api/matters/${matterId}/parties`,
    {
      method: "POST",
      body: JSON.stringify(partyData),
    },
    { retry: false }
  );
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
  return authedFetch(
    `/api/matters/${matterId}/evidence`,
    {
      method: "POST",
      body: JSON.stringify(factData),
    },
    { retry: false }
  );
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
  return authedFetch(
    `/api/matters/${matterId}/hearings`,
    {
      method: "POST",
      body: JSON.stringify(hearingData),
    },
    { retry: false }
  );
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
  return authedFetch(
    `/api/matters/${matterId}/case-analysis`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    { retry: false }
  );
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
  return authedFetch(
    `/api/matters/${matterId}/messages`,
    {
      method: "POST",
      body: JSON.stringify({ content }),
    },
    { retry: false }
  );
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
  return authedFetch(
    `/api/matters/${matterId}/drafts`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    { retry: false }
  );
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

export function downloadPleadingDocx(matterId: string, draftId: string, filename: string) {
  return downloadFile(`/api/matters/${matterId}/pleading-draft/${draftId}/download`, filename);
}

export function downloadPleadingPdf(matterId: string, draftId: string, filename: string) {
  return downloadFile(`/api/matters/${matterId}/pleading-draft/${draftId}/download.pdf`, filename);
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
  return authedFetch(
    `/api/templates/${templateId}/clauses/${clauseId}/review`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    { retry: false }
  );
}

/** Keeps every currently-unreviewed fixed_boilerplate clause on a
 * template in one action — never touches llm_fillable clauses or a
 * clause that's already been reviewed. Returns the updated rows. */
export function bulkKeepBoilerplate(templateId: string): Promise<TemplateClause[]> {
  return authedFetch(
    `/api/templates/${templateId}/clauses/bulk-keep-boilerplate`,
    {
      method: "POST",
    },
    { retry: false }
  );
}

// --- Litigation Pleading Workbench (Sprint 4) ---

export type PleadingOutline = {
  id: string;
  version_no: number;
  sections: Array<{
    title: string;
    section_type: string;
    required_clauses: string[];
    suggested_arguments: string[];
  }>;
  status: string;
  created_at: string;
};

export type PleadingClause = {
  id: string;
  clause_type: string;
  version_no: number;
  content: string;
  review_status: "Needs Review" | "Approved" | "Rejected";
  citations: unknown[];
  created_at: string;
};

export type PleadingDraft = {
  id: string;
  version_no: number;
  composed_sections: Array<{
    paragraph_no: number;
    clause_type: string;
    heading: string;
    text: string;
  }>;
  created_at: string;
};

export function generatePleadingOutline(matterId: string, payload: { case_analysis_id: string }): Promise<PleadingOutline> {
  return authedFetch(`/api/matters/${matterId}/pleading-outline`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPleadingOutlines(matterId: string): Promise<PleadingOutline[]> {
  return authedFetch(`/api/matters/${matterId}/pleading-outline`);
}

export function generateClause(matterId: string, clauseType: string, payload: { pleading_outline_id: string }): Promise<PleadingClause> {
  return authedFetch(`/api/matters/${matterId}/clauses/${clauseType}/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listClauses(matterId: string, pleadingOutlineId: string): Promise<PleadingClause[]> {
  return authedFetch(`/api/matters/${matterId}/clauses?pleading_outline_id=${pleadingOutlineId}`);
}

export function reviewPleadingClause(matterId: string, clauseId: string, status: "Approved" | "Rejected"): Promise<PleadingClause> {
  return authedFetch(`/api/matters/${matterId}/clauses/${clauseId}/review`, {
    method: "POST",
    body: JSON.stringify({ review_status: status }),
  });
}

export function composePleading(matterId: string, payload: { pleading_outline_id: string }): Promise<PleadingDraft> {
  return authedFetch(`/api/matters/${matterId}/pleading-draft/compose`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listPleadingDrafts(matterId: string, pleadingOutlineId: string): Promise<PleadingDraft[]> {
  return authedFetch(`/api/matters/${matterId}/pleading-draft?pleading_outline_id=${pleadingOutlineId}`);
}
