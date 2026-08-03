import { IntakeField } from "./api";

/**
 * Renders a group's collapsed-state summary line from its
 * `summary_template` and the form's current values.
 *
 * Design rule (Sprint 2 Phase 1 Session 1, confirmed before build):
 * `summary_template` is a sequence of short clauses joined by " · ",
 * each containing one or more `{{field_key}}` placeholders (e.g.
 * "{{fee_structure}} {{fee_amount}} · {{payment_frequency}}"). A clause
 * is dropped ENTIRELY if every placeholder inside it is empty — not
 * substituted with "" in place, which is what produces the exact
 * artifacts this rule exists to avoid: a trailing space ("Fixed Fee "),
 * or a dangling separator when an empty field sits between two filled
 * ones ("A ·  · C" instead of "A · C"). Surviving clauses are trimmed
 * and rejoined with " · ". If every clause in the whole template is
 * empty, the caller should show EMPTY_GROUP_SUMMARY instead of a blank
 * line — see groupSummaryOrEmpty.
 */

const CLAUSE_SEPARATOR = " · ";
const PLACEHOLDER_RE = /\{\{(\w+)\}\}/g;
const MAX_TEXT_VALUE_LENGTH = 40;

export const EMPTY_GROUP_SUMMARY = "Not started";

function formatDate(value: string): string {
  // ISO "2026-08-03" -> "3 August 2026" — Indian date convention, per
  // docs/UI_UX_Design_Notes.md ("never 08/03/2026 or Aug 3, 2026").
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

function optionLabelFor(field: IntakeField, rawValue: string): string {
  const opt = (field.options ?? []).find((o) => (typeof o === "string" ? o === rawValue : o.value === rawValue));
  if (!opt) return rawValue;
  return typeof opt === "string" ? opt : opt.label;
}

/** Empty-string return means "this field contributes nothing to the
 * summary" — the caller (renderGroupSummary) uses that to decide
 * whether a clause survives. */
function displayValue(field: IntakeField | undefined, raw: unknown): string {
  if (raw === undefined || raw === null) return "";

  if (field?.type === "list") {
    const items = Array.isArray(raw) ? raw : [];
    return items.length > 0 ? `${items.length} item${items.length === 1 ? "" : "s"}` : "";
  }

  if (field?.type === "boolean") {
    // A false/unset boolean contributes nothing — most groups reference
    // a boolean's *conditional* fields (e.g. SLA response-time-hours)
    // rather than the flag itself, so this mainly matters if a template
    // author deliberately wants to show "Yes" once something is turned on.
    return raw ? "Yes" : "";
  }

  if (field?.type === "date") {
    return typeof raw === "string" && raw ? formatDate(raw) : "";
  }

  if (field?.type === "select") {
    return typeof raw === "string" && raw ? optionLabelFor(field, raw) : "";
  }

  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (!trimmed) return "";
    return trimmed.length > MAX_TEXT_VALUE_LENGTH
      ? `${trimmed.slice(0, MAX_TEXT_VALUE_LENGTH - 1)}…`
      : trimmed;
  }

  return String(raw);
}

export function renderGroupSummary(
  template: string,
  values: Record<string, unknown>,
  fieldsByKey: Record<string, IntakeField>
): string {
  const clauses = template.split(CLAUSE_SEPARATOR);

  const survivors = clauses
    .map((clause) => {
      let hasContent = false;
      const substituted = clause.replace(PLACEHOLDER_RE, (_match, key: string) => {
        const display = displayValue(fieldsByKey[key], values[key]);
        if (display) hasContent = true;
        return display;
      });
      if (!hasContent) return null;
      // Collapse any incidental double-space left by an empty placeholder
      // elsewhere in a multi-placeholder clause (e.g. "{{a}} {{b}}" with
      // only `a` filled).
      return substituted.replace(/\s+/g, " ").trim();
    })
    .filter((c): c is string => c !== null && c.length > 0);

  return survivors.join(CLAUSE_SEPARATOR);
}

export function groupSummaryOrEmpty(
  template: string,
  values: Record<string, unknown>,
  fieldsByKey: Record<string, IntakeField>
): string {
  return renderGroupSummary(template, values, fieldsByKey) || EMPTY_GROUP_SUMMARY;
}
