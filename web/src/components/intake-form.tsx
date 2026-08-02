"use client";

import { useEffect, useState } from "react";
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
import { getStateRules, IntakeField, IntakeSchema, StateRule } from "@/lib/api";

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
        className="h-4 w-4 rounded border-input"
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
  // terms?"), not stacked above it like every other field type — and
  // stacking them was actually broken, not just unconventional: <Label>
  // and <input type=checkbox> are both inline-level, so the space-y-2
  // margin-top between them collapsed (inline elements don't respect
  // vertical margin), leaving the checkbox squished against the label
  // text with no visible gap. Explicit flex + gap fixes both the layout
  // and the visual bug at once.
  if (field.type === "boolean") {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <FieldInput id={id} field={field} value={value} onChange={onChange} />
          <Label htmlFor={id}>
            {field.label}
            {field.required && <span className="text-destructive"> *</span>}
          </Label>
        </div>
        {field.help && <p className="text-xs text-muted-foreground">{field.help}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={id}>
        {field.label}
        {field.required && <span className="text-destructive"> *</span>}
      </Label>
      {field.help && <p className="text-xs text-muted-foreground">{field.help}</p>}
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
        <div key={index} className="space-y-3 rounded-md border p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">
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

export function IntakeForm({
  schema,
  initialValues,
  onSubmit,
  busy,
  submitLabel = "Generate draft",
}: {
  schema: IntakeSchema;
  initialValues?: Record<string, unknown>;
  onSubmit: (values: Record<string, unknown>) => void;
  busy?: boolean;
  submitLabel?: string;
}) {
  const [values, setValues] = useState<Record<string, unknown>>(() => ({
    ...defaultsForFields(schema.fields),
    ...(initialValues ?? {}),
  }));
  const [stateRules, setStateRules] = useState<StateRule[]>([]);

  const stateField = schema.fields.find((f) => f.key === "state");
  const currentState = stateField ? (values.state as string | undefined) : undefined;

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
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }

  return (
    <div className="grid gap-6 md:grid-cols-[1fr_18rem]">
      <form onSubmit={handleSubmit} className="space-y-4">
        {schema.fields
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

        <Button type="submit" disabled={busy}>
          {busy ? "Generating…" : submitLabel}
        </Button>
      </form>

      <div className="space-y-2">
        <h3 className="text-sm font-medium text-muted-foreground">State law notes</h3>
        {!currentState && (
          <p className="text-xs text-muted-foreground">Pick a governing state to see notes.</p>
        )}
        {currentState && stateRules.length === 0 && (
          <p className="text-xs text-muted-foreground">
            No notes on file yet for {currentState}.
          </p>
        )}
        {stateRules.map((rule, i) => (
          <div key={i} className="rounded-md border bg-muted/40 p-3 text-xs">
            <div className="font-medium">{rule.state}</div>
            {rule.stamp_duty && <p className="mt-1">Stamp duty: {rule.stamp_duty}</p>}
            {rule.registration_req && <p className="mt-1">Registration: {rule.registration_req}</p>}
            {rule.notes && <p className="mt-1 font-medium text-amber-700">{rule.notes}</p>}
            {rule.source_url && (
              <a
                href={rule.source_url}
                target="_blank"
                rel="noreferrer"
                className="mt-1 block underline"
              >
                Source
              </a>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
