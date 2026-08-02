import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

export type Matter = {
  id: string;
  title: string;
  client_name: string | null;
  module: "litigation" | "contracts" | "rera" | "consulting";
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

export function createMatter(input: {
  title: string;
  client_name?: string;
  module: Matter["module"];
}): Promise<Matter> {
  return authedFetch("/api/matters", {
    method: "POST",
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

export type IntakeSchema = {
  template_key: string;
  title: string;
  variant_field?: string;
  fields: IntakeField[];
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
