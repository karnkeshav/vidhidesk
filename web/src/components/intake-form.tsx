"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { getStateRules, IntakeField, IntakeFieldGroup, IntakeSchema, StateRule } from "@/lib/api";
import { groupSummaryOrEmpty } from "@/lib/group-summary";

function optionValue(opt: IntakeField["options"] extends (infer T)[] | undefined ? T : never) {
  return typeof opt === "string" ? opt : opt.value;
}
function optionLabel(opt: IntakeField["options"] extends (infer T)[] | undefined ? T : never) {
  return typeof opt === "string" ? opt : opt.label;
}

function fieldVisible(field: IntakeField, values: Record<string, unknown>): boolean {
  if (!field.condition) return true;
  const actual = values[field.condition.field];
  if ("equals" in field.condition) return actual === field.condition.equals;
  if ("not_equals" in field.condition) return actual !== field.condition.not_equals;
  return true;
}

function defaultsForFields(fields: IntakeField[]): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  for (const f of fields) {
    if (f.type === "list") defaults[f.key] = [];
    else if (f.default !== undefined) defaults[f.key] = f.default;
  }
  return defaults;
}

/** True if a required (or, for lists, min_items-bound) field currently
 * fails that requirement — used for the accordion's own pre-submit
 * check, since a field inside a collapsed section is unmounted and
 * native HTML5 `required` validation cannot see it (a submit would
 * either silently go through with missing data, or the browser blocks
 * it with no visible reason — neither acceptable once fields can be
 * hidden by our own UI, not just by a `condition`). Only checks
 * top-level fields; a `list` field's own item_schema fields stay
 * covered by native validation as before, since an expanded list's
 * items are never collapsed away themselves. */
function isFieldMissing(field: IntakeField, value: unknown): boolean {
  if (field.type === "list") {
    const items = Array.isArray(value) ? value : [];
    return items.length < (field.min_items ?? 0);
  }
  if (field.type === "boolean") return false;
  if (!field.required) return false;
  return value === undefined || value === null || value === "";
}

/** The single control for one field's value — text/textarea/select/
 * boolean/date/list. Used both for top-level schema fields and,
 * recursively, for each field inside a "list" field's item_schema — a
 * repeater item is rendered with exactly the same primitives as the
 * top-level form, per Sprint 2 Deliverable 2's generic-repeater design. */
function FieldInput({
  id,
  field,
  value,
  onChange,
}: {
  id: string;
  field: IntakeField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  if (field.type === "text") {
    return (
      <Input
        id={id}
        required={field.required}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (field.type === "date") {
    return (
      <Input
        id={id}
        type="date"
        required={field.required}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (field.type === "textarea") {
    return (
      <Textarea
        id={id}
        required={field.required}
        rows={3}
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  if (field.type === "boolean") {
    return (
      <input
        id={id}
        type="checkbox"
        className="h-4 w-4 rounded border-[#E4E2DD]"
        checked={Boolean(value)}
        onChange={(e) => onChange(e.target.checked)}
      />
    );
  }
  if (field.type === "select") {
    return (
      <Select value={(value as string) ?? ""} onValueChange={onChange}>
        <SelectTrigger id={id}>
          <SelectValue placeholder="Select…" />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map((opt) => (
            <SelectItem key={optionValue(opt)} value={optionValue(opt)}>
              {optionLabel(opt)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }
  if (field.type === "list") {
    return (
      <ListRepeaterField
        idPrefix={id}
        field={field}
        value={(value as Record<string, unknown>[]) ?? []}
        onChange={onChange}
      />
    );
  }
  return null;
}

/** Label + help text + the control, for one field. Reused for both
 * top-level fields and (with a namespaced `id`) each field inside a
 * repeater item. */
function FieldRow({
  id,
  field,
  value,
  onChange,
}: {
  id: string;
  field: IntakeField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  // Checkboxes read naturally beside their label ("[ ] Include SLA
  // terms?"), not stacked above it like every other field type — see
  // docs/lessons_learned.md: <Label> and <input type=checkbox> are both
  // inline-level, so a stacked space-y-2 layout's margin-top between
  // them silently collapses (inline elements don't respect vertical
  // margin). Explicit flex + gap fixes both the layout and that bug.
  if (field.type === "boolean") {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <FieldInput id={id} field={field} value={value} onChange={onChange} />
          <Label htmlFor={id} className="font-sans text-sm text-[#1A1A1A]">
            {field.label}
            {field.required && <span className="text-[#7A2A2A]"> *</span>}
          </Label>
        </div>
        {field.help && <p className="font-serif text-xs text-[#45464E]">{field.help}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="font-sans text-sm font-medium text-[#1A1A1A]">
        {field.label}
        {field.required && <span className="text-[#7A2A2A]"> *</span>}
      </Label>
      {field.help && <p className="font-serif text-xs text-[#45464E]">{field.help}</p>}
      <FieldInput id={id} field={field} value={value} onChange={onChange} />
    </div>
  );
}

/** Generic repeater for `type: "list"` fields (deliverables, benefits,
 * fixtures, encumbrances, ... — any template's enumerable content).
 * Deliberately generic: it knows nothing about what an item *means*, only
 * that it's a set of fields rendered via the same FieldRow/FieldInput
 * primitives as everything else. */
function ListRepeaterField({
  idPrefix,
  field,
  value,
  onChange,
}: {
  idPrefix: string;
  field: IntakeField;
  value: Record<string, unknown>[];
  onChange: (value: Record<string, unknown>[]) => void;
}) {
  const itemFields = field.item_schema ?? [];
  const minItems = field.min_items ?? 0;
  const maxItems = field.max_items ?? null;
  const singular = field.item_singular_label ?? "Item";

  function addItem() {
    onChange([...value, defaultsForFields(itemFields)]);
  }
  function removeItem(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }
  function updateItem(index: number, key: string, itemValue: unknown) {
    onChange(value.map((item, i) => (i === index ? { ...item, [key]: itemValue } : item)));
  }

  return (
    <div className="space-y-3">
      {value.map((item, index) => (
        <div key={index} className="space-y-3 rounded-sm border border-[#E4E2DD] p-3">
          <div className="flex items-center justify-between">
            <span className="font-sans text-xs font-medium text-[#45464E]">
              {singular} {index + 1}
            </span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => removeItem(index)}
              disabled={value.length <= minItems}
            >
              Remove
            </Button>
          </div>
          {itemFields.map((itemField) => (
            <FieldRow
              key={itemField.key}
              id={`${idPrefix}-${index}-${itemField.key}`}
              field={itemField}
              value={item[itemField.key]}
              onChange={(v) => updateItem(index, itemField.key, v)}
            />
          ))}
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={addItem}
        disabled={maxItems != null && value.length >= maxItems}
      >
        + Add {singular}
      </Button>
    </div>
  );
}

/** One collapsible accordion section — a group's header shows its label
 * and, when collapsed, the rendered summary line; expanded, it shows its
 * fields via the same FieldRow primitives as everything else. */
function GroupSection({
  group,
  fields,
  fieldsByKey,
  values,
  expanded,
  incomplete,
  onToggle,
  onFieldChange,
}: {
  group: IntakeFieldGroup;
  fields: IntakeField[];
  fieldsByKey: Record<string, IntakeField>;
  values: Record<string, unknown>;
  expanded: boolean;
  incomplete: boolean;
  onToggle: () => void;
  onFieldChange: (key: string, value: unknown) => void;
}) {
  const summary = groupSummaryOrEmpty(group.summary_template, values, fieldsByKey);
  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          {incomplete && (
            <span
              className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#7A2A2A]"
              title="This section has a required field still to fill"
            />
          )}
          <div>
            <div className="font-sans text-sm font-semibold text-[#081534]">{group.label}</div>
            {!expanded && <div className="mt-0.5 font-serif text-xs italic text-[#45464E]">{summary}</div>}
          </div>
        </div>
        <ChevronDown
          className={cn("h-4 w-4 shrink-0 text-[#45464E] transition-transform", expanded && "rotate-180")}
          strokeWidth={1.5}
        />
      </button>
      {expanded && (
        <div className="space-y-4 border-t border-[#E4E2DD] px-4 py-4">
          {fields
            .filter((f) => fieldVisible(f, values))
            .map((field) => (
              <FieldRow
                key={field.key}
                id={field.key}
                field={field}
                value={values[field.key]}
                onChange={(v) => onFieldChange(field.key, v)}
              />
            ))}
        </div>
      )}
    </div>
  );
}

export function IntakeForm({
  schema,
  initialValues,
  onSubmit,
  onValuesChange,
  busy,
  submitLabel = "Generate draft",
}: {
  schema: IntakeSchema;
  initialValues?: Record<string, unknown>;
  onSubmit: (values: Record<string, unknown>) => void;
  /** Fires on every field change, live — lets the parent page observe
   * values while the advocate is still typing (e.g. to drive the
   * auto-generating matter title from party names) without lifting the
   * whole form's state out of this component. */
  onValuesChange?: (values: Record<string, unknown>) => void;
  busy?: boolean;
  submitLabel?: string;
}) {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({
    ...defaultsForFields(schema.fields),
    ...(initialValues ?? {}),
  }));
  const [stateRules, setStateRules] = useState<StateRule[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

  const stateField = schema.fields.find((f) => f.key === "state");
  const currentState = stateField ? (values.state as string | undefined) : undefined;

  const groups = useMemo(() => schema.groups ?? [], [schema.groups]);
  const fieldsByKey = useMemo(() => {
    const map: Record<string, IntakeField> = {};
    for (const f of schema.fields) map[f.key] = f;
    return map;
  }, [schema.fields]);

  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(groups[0]?.id ?? null);

  useEffect(() => {
    // Dev-time defensive check only — a field silently missing from
    // every group would simply never render, with no error anywhere
    // else to catch it. "state" is deliberately excluded from every
    // group (it renders in the sidebar instead), so it's exempted here.
    if (groups.length === 0 || process.env.NODE_ENV === "production") return;
    const grouped = new Set(groups.flatMap((g) => g.field_keys));
    const orphans = schema.fields.filter((f) => f.key !== "state" && !grouped.has(f.key));
    if (orphans.length > 0) {
      console.warn(
        `IntakeForm: "${schema.template_key}" has fields not assigned to any group:`,
        orphans.map((f) => f.key)
      );
    }
  }, [schema, groups]);

  useEffect(() => {
    if (!currentState || currentState.startsWith("Other")) {
      setStateRules([]);
      return;
    }
    getStateRules(currentState, schema.title)
      .then(setStateRules)
      .catch(() => setStateRules([])); // notes panel is a convenience, not a blocker
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentState, schema.title]);

  function setValue(key: string, value: unknown) {
    setValues((prev) => {
      const next = { ...prev, [key]: value };
      onValuesChange?.(next);
      return next;
    });
  }

  /** Which group (by id) a top-level field key belongs to — used both to
   * flag an incomplete section's header dot and to auto-expand the
   * right section on a failed submit. Fields not in `schema.groups` at
   * all (the ungrouped fallback path) have no group id. */
  function groupIdFor(fieldKey: string): string | null {
    return groups.find((g) => g.field_keys.includes(fieldKey))?.id ?? null;
  }

  function firstMissingFieldKey(): string | null {
    for (const field of schema.fields) {
      if (field.key === "state") continue;
      if (!fieldVisible(field, values)) continue;
      if (isFieldMissing(field, values[field.key])) return field.key;
    }
    return null;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const missingKey = firstMissingFieldKey();
    if (missingKey) {
      const missingGroupId = groupIdFor(missingKey);
      if (missingGroupId) setExpandedGroupId(missingGroupId);
      setValidationError(
        `${fieldsByKey[missingKey]?.label ?? missingKey} is required before the draft can be generated.`
      );
      return;
    }
    setValidationError(null);
    onSubmit(values);
  }

  const ungroupedFields = schema.fields.filter((f) => f.key !== "state");

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
      <form onSubmit={handleSubmit} className="space-y-3">
        {validationError && (
          <div
            role="alert"
            className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] px-3 py-2 font-sans text-xs text-[#7A2A2A]"
          >
            {validationError}
          </div>
        )}

        {groups.length > 0
          ? groups.map((group) => {
              const groupFields = group.field_keys
                .map((k) => fieldsByKey[k])
                .filter((f): f is IntakeField => Boolean(f));
              const incomplete = groupFields.some(
                (f) => fieldVisible(f, values) && isFieldMissing(f, values[f.key])
              );
              return (
                <GroupSection
                  key={group.id}
                  group={group}
                  fields={groupFields}
                  fieldsByKey={fieldsByKey}
                  values={values}
                  expanded={expandedGroupId === group.id}
                  incomplete={incomplete}
                  onToggle={() => setExpandedGroupId((prev) => (prev === group.id ? null : group.id))}
                  onFieldChange={setValue}
                />
              );
            })
          : // Fallback for a schema that hasn't declared groups yet — the
            // original flat, ungrouped layout.
            ungroupedFields
              .filter((f) => fieldVisible(f, values))
              .map((field) => (
                <FieldRow
                  key={field.key}
                  id={field.key}
                  field={field}
                  value={values[field.key]}
                  onChange={(v) => setValue(field.key, v)}
                />
              ))}

        <Button
          type="submit"
          disabled={busy}
          className="w-full rounded-sm bg-[#081534] py-2.5 font-sans text-sm font-semibold text-white hover:bg-[#1E2A4A]"
        >
          {busy ? "Generating…" : submitLabel}
        </Button>
      </form>

      <div className="space-y-4">
        {stateField && (
          <div className="rounded-sm border border-[#E4E2DD] bg-white p-4">
            <Label
              htmlFor="state"
              className="font-sans text-xs font-semibold uppercase tracking-wider text-[#45464E]"
            >
              Governing State
            </Label>
            <div className="mt-2">
              <FieldInput
                id="state"
                field={stateField}
                value={values.state}
                onChange={(v) => setValue("state", v)}
              />
            </div>
          </div>
        )}

        <div className="space-y-2 rounded-sm border border-[#E4E2DD] bg-white p-4">
          <h3 className="font-sans text-xs font-semibold uppercase tracking-wider text-[#45464E]">
            State law notes
          </h3>
          {!currentState && (
            <p className="font-serif text-xs text-[#45464E]">Pick a governing state to see notes.</p>
          )}
          {currentState && stateRules.length === 0 && (
            <p className="font-serif text-xs text-[#45464E]">No notes on file yet for {currentState}.</p>
          )}
          {stateRules.map((rule, i) => (
            <div key={i} className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3 font-serif text-xs">
              <div className="font-sans font-medium text-[#081534]">{rule.state}</div>
              {rule.stamp_duty && <p className="mt-1">Stamp duty: {rule.stamp_duty}</p>}
              {rule.registration_req && <p className="mt-1">Registration: {rule.registration_req}</p>}
              {rule.notes && <p className="mt-1 font-sans font-medium text-[#7A2A2A]">{rule.notes}</p>}
              {rule.source_url && (
                <a
                  href={rule.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block font-sans text-[#081534] underline"
                >
                  Source
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
