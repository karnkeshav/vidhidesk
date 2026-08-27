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

// Free-trial paywall (app/auth.py::_check_account_not_locked): the backend
// marks this specific 401 with the literal string "TRIAL_EXPIRED" in its
// detail so the frontend can tell "5-day trial lapsed, payment not yet
// received" apart from every other 401 cause (expired token, malformed
// header, ...). This deliberately does NOT sign the user out -- their
// Supabase session is still perfectly valid, and the whole point of the
// payment_received toggle is that access resumes the moment Nitesh flips
// it, with no re-login required. authed-shell.tsx's own onAuthStateChange /
// getSession() still separately owns real session-death handling.
function isTrialExpiredFailure(status: number, bodyText: string): boolean {
  return status === 401 && bodyText.includes("TRIAL_EXPIRED");
}

// Organization-level access gate (app/auth.py::_check_organization_access,
// added 27 Aug 2026 alongside — never replacing — the per-user trial check
// above). Deliberately a DISTINCT status/marker (403, not 401) and a
// separate destination page: TRIAL_EXPIRED means "your own account's free
// trial lapsed"; ORG_ACCESS_DISABLED means "the platform owner disabled or
// suspended your organization" — conflating the two into one redirect would
// misattribute the cause to the wrong actor. Same no-sign-out reasoning as
// isTrialExpiredFailure: the Supabase session stays valid, and access
// resumes the moment the owner re-enables the organization, no re-login
// required.
function isOrgAccessDisabledFailure(status: number, bodyText: string): boolean {
  return status === 403 && bodyText.includes("ORG_ACCESS_DISABLED");
}

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
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

// Cross-module practice calendar entry (Calendar page). Distinct from the
// per-litigation-matter docket log below (listHearings(matterId) /
// addHearing / LitigationHearingOut) -- that tracks outcomes/next-dates
// for one case's hearing history; CalendarHearing is a lighter, optional
// matter-linked reminder spanning every module, scheduled from /calendar.
export type CalendarHearing = {
  id: string;
  matter_id: string | null;
  case_no: string | null;
  title: string;
  court: string | null;
  bench: string | null;
  item_no: string | null;
  stage: string | null;
  hearing_at: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
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
async function authedFetch(path: string, init?: RequestInit, options?: { retry?: boolean; timeoutMs?: number }) {
  const retryEligible = options?.retry ?? true;
  const timeoutMs = options?.timeoutMs ?? FETCH_TIMEOUT_MS;
  const {
    data: { session },
  } = await supabase.auth.getSession();
  debugLog("request started", { url: `${API_URL}${path}`, authPresent: !!session });
  if (!session) throw new Error("Not signed in");

  for (let attempt = 0; ; attempt++) {
    debugLog("attempt", { url: `${API_URL}${path}`, attempt });
    let res: Response;
    try {
      res = await fetchWithTimeout(
        `${API_URL}${path}`,
        {
          ...init,
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.access_token}`,
            ...(init?.headers ?? {}),
          },
        },
        timeoutMs
      );
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
    if (isTrialExpiredFailure(res.status, body)) {
      // Deliberately no sign-out here -- the Supabase session stays valid,
      // and payment_received flipping to true should resume access with no
      // re-login required. Hard navigation (not router.push) since this
      // file has no router instance and every caller is in a different
      // component tree.
      if (typeof window !== "undefined") window.location.href = "/trial-expired";
    } else if (isOrgAccessDisabledFailure(res.status, body)) {
      // Same no-sign-out, hard-navigation reasoning as TRIAL_EXPIRED above
      // -- but a distinct destination, since the cause and the actor who
      // can fix it are different (platform owner, not "arrange payment").
      if (typeof window !== "undefined") window.location.href = "/org-access-disabled";
    }
    throw new ApiError(res.status, `${res.status} ${res.statusText}: ${body}`);
  }
}

// Records this user's free-trial start (app/routers/auth.py) -- a no-op
// after the first successful call ever, by design (insert-once on the
// backend). Called by login/page.tsx right after a real sign-in completes
// -- never on a page load/session restore, though it would be harmless
// either way now.
export function startSession(): Promise<{ status: string }> {
  return authedFetch("/api/auth/session-start", { method: "POST" }, { retry: false });
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

export type CalendarHearingInput = {
  matter_id?: string | null;
  case_no?: string | null;
  title: string;
  court?: string | null;
  bench?: string | null;
  item_no?: string | null;
  stage?: string | null;
  hearing_at: string;
  notes?: string | null;
};

export function listCalendarHearings(): Promise<CalendarHearing[]> {
  return authedFetch("/api/hearings");
}

export function createCalendarHearing(input: CalendarHearingInput): Promise<CalendarHearing> {
  return authedFetch(
    "/api/hearings",
    {
      method: "POST",
      body: JSON.stringify(input),
    },
    { retry: false }
  );
}

export function updateCalendarHearing(
  hearingId: string,
  input: Partial<CalendarHearingInput>
): Promise<CalendarHearing> {
  return authedFetch(`/api/hearings/${hearingId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteCalendarHearing(hearingId: string): Promise<{ status: string; id: string }> {
  return authedFetch(`/api/hearings/${hearingId}`, {
    method: "DELETE",
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

/** RERA Phase 2G — restores a historical draft's preview text by reading
 * the actual persisted .docx server-side (see api/app/routers/contracts.py's
 * get_draft_text), not by reconstructing from clause data client-side. */
export type DraftText = {
  draft_version_id: string;
  version_no: number;
  full_text: string;
};

export function getDraftText(draftVersionId: string): Promise<DraftText> {
  return authedFetch(`/api/drafts/${draftVersionId}/text`);
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
  return authedFetch(
    `/api/matters/${matterId}/pleading-outline`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    { retry: false }
  );
}

export function listPleadingOutlines(matterId: string): Promise<PleadingOutline[]> {
  return authedFetch(`/api/matters/${matterId}/pleading-outline`);
}

export function generateClause(matterId: string, clauseType: string, payload: { pleading_outline_id: string }): Promise<PleadingClause> {
  return authedFetch(
    `/api/matters/${matterId}/clauses/${clauseType}/generate`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    { retry: false }
  );
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
  return authedFetch(
    `/api/matters/${matterId}/pleading-draft/compose`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    { retry: false }
  );
}

export function listPleadingDrafts(matterId: string, pleadingOutlineId: string): Promise<PleadingDraft[]> {
  return authedFetch(`/api/matters/${matterId}/pleading-draft?pleading_outline_id=${pleadingOutlineId}`);
}

// ==========================================
// RERA
// ==========================================

export type RERAWalkthroughProcedureOut = {
  state: string;
  procedure: string;
  step_count: number;
};

export type RERAWalkthroughStepOut = {
  id: string;
  state: string;
  procedure: string;
  step_no: number;
  heading: string | null;
  instruction: string;
  required_documents: string[];
  portal_url: string | null;
  warnings: string | null;
  source_url: string | null;
  last_verified: string | null;
  verification_status: string;
};

export type RERAWalkthroughProgressOut = {
  id: string;
  user_id: string;
  matter_id: string | null;
  state: string;
  procedure: string;
  current_step_no: number;
  completed_step_ids: string[];
  is_complete: boolean;
  started_at: string;
  updated_at: string;
};

export function getReraStates(): Promise<string[]> {
  return authedFetch("/api/rera/states");
}

export function getReraProcedures(state: string): Promise<RERAWalkthroughProcedureOut[]> {
  return authedFetch(`/api/rera/procedures?state=${encodeURIComponent(state)}`);
}

export function getReraWalkthrough(state: string, procedure: string): Promise<RERAWalkthroughStepOut[]> {
  return authedFetch(`/api/rera/walkthrough/${encodeURIComponent(state)}/${encodeURIComponent(procedure)}`);
}

export function getReraProgress(state: string, procedure: string, matterId?: string): Promise<RERAWalkthroughProgressOut | null> {
  const query = matterId ? `?matter_id=${encodeURIComponent(matterId)}` : "";
  return authedFetch(`/api/rera/walkthrough/${encodeURIComponent(state)}/${encodeURIComponent(procedure)}/progress${query}`);
}

export function updateReraProgress(
  state: string, 
  procedure: string, 
  update: { current_step_no?: number, mark_step_complete_id?: string, mark_step_incomplete_id?: string, matter_id?: string }
): Promise<RERAWalkthroughProgressOut> {
  return authedFetch(`/api/rera/walkthrough/${encodeURIComponent(state)}/${encodeURIComponent(procedure)}/progress`, {
    method: "PUT",
    body: JSON.stringify(update),
  });
}

// ==========================================
// CONSULTING
// ==========================================

export type ConsultingAnalyzeRequest = {
  question: string;
  matter_id?: string | null;
  party_names?: string[];
  addresses?: string[];
  limitation?: unknown;
  forum?: unknown;
};

export type ConsultingAnalysisOut = {
  id: string;
  matter_id: string;
  version_no: number;
  question: string;
  applicable_law: Array<{
    act: string;
    section_no: string;
    relevance: string;
    grounded: boolean;
  }>;
  correct_forum: {
    forum_name: string;
    reasoning: string;
    deterministic: boolean;
    source: string;
  } | null;
  remedies_available: Array<{
    remedy: string;
    description: string;
  }>;
  limitation_period: {
    summary: string;
    deterministic: boolean;
    source: string;
    expiry_date: string | null;
    is_barred: boolean | null;
    days_remaining: number | null;
  } | null;
  case_law_references: Array<{
    case_name: string;
    note: string;
    status: "verified" | "unverified" | "pending";
    ik_url: string | null;
    court: string | null;
  }>;
  missing_information: string[];
  model_used: string;
  generation_warning: string | null;
  created_at: string;
  notice: string;
};

// Well past FETCH_TIMEOUT_MS's default 12s: this endpoint does PII masking
// + RAG retrieval + an LLM call (with up to 3 Gemini + 5 Groq failover
// attempts on error/rate-limit, CLAUDE.md Decision 3), then a live Indian
// Kanoon verification call for every case name the model proposes. A real
// local run measured 134.5s end to end while the Gemini key was being
// rejected as leaked (403) on every attempt, forcing the full Groq
// fallback cascade -- 180s leaves margin above that worst case even before
// the key is rotated.
const CONSULTING_ANALYZE_TIMEOUT_MS = 300000;

export function createConsultingAnalysis(payload: ConsultingAnalyzeRequest): Promise<ConsultingAnalysisOut> {
  return authedFetch("/api/consulting/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  }, { retry: false, timeoutMs: CONSULTING_ANALYZE_TIMEOUT_MS });
}

export function listConsultingAnalyses(matterId: string): Promise<ConsultingAnalysisOut[]> {
  return authedFetch(`/api/consulting/matters/${matterId}/analyses`);
}

// ==========================================
// PLATFORM OWNER DASHBOARD (Enhancement_Roadmap.md §4)
// Every call below hits a /api/platform/* route gated server-side by
// app/auth.py::require_platform_owner -- a non-owner gets a 403 from
// authedFetch itself (surfaces as ApiError, status 403), not a redirect.
// ==========================================

export type OrganizationOut = {
  id: string;
  name: string;
  organization_type: "individual" | "firm";
  subscription_status: "trial" | "active" | "suspended" | "expired";
  trial_started_at: string;
  trial_ends_at: string;
  access_enabled: boolean;
  payment_marked_at: string | null;
  created_at: string;
  updated_at: string;
};

export type OrganizationListItem = OrganizationOut & {
  member_count: number;
  matter_count: number;
};

export type MembershipOut = {
  id: string;
  organization_id: string;
  user_id: string;
  role: "org_admin" | "member";
  email: string | null;
  // Dashboard clarity (27 Aug 2026): this member's own account_security
  // state, entirely separate from organization-level access below —
  // "trial_active" | "trial_expired" | "payment_received" | "not_started".
  // Never the raw login_started_at timestamp.
  account_status: "trial_active" | "trial_expired" | "payment_received" | "not_started" | null;
  created_at: string;
};

export type OrganizationDetail = OrganizationOut & {
  members: MembershipOut[];
  matter_count: number;
  modules_used: string[];
  last_activity_at: string | null;
};

export type PlatformOverview = {
  total_organizations: number;
  individual_organizations: number;
  firm_organizations: number;
  trial_organizations: number;
  active_organizations: number;
  expired_organizations: number;
  suspended_organizations: number;
  users_with_a_matter: number;
  users_with_a_draft: number;
  onboarding_funnel: Record<string, number>;
};

export function getPlatformOverview(): Promise<PlatformOverview> {
  return authedFetch("/api/platform/overview");
}

export function listOrganizations(filters?: {
  status?: OrganizationOut["subscription_status"];
  org_type?: OrganizationOut["organization_type"];
}): Promise<OrganizationListItem[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.org_type) params.set("org_type", filters.org_type);
  const query = params.toString();
  return authedFetch(`/api/platform/organizations${query ? `?${query}` : ""}`);
}

export function getOrganization(orgId: string): Promise<OrganizationDetail> {
  return authedFetch(`/api/platform/organizations/${orgId}`);
}

export function updateOrganizationAccess(
  orgId: string,
  input: {
    action: "mark_payment" | "enable" | "suspend" | "reactivate" | "extend_trial";
    reason?: string;
    extend_days?: number;
  }
): Promise<OrganizationOut> {
  return authedFetch(
    `/api/platform/organizations/${orgId}/access`,
    {
      method: "PATCH",
      body: JSON.stringify(input),
    },
    { retry: false }
  );
}
