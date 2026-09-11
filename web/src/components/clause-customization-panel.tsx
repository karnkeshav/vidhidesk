"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  MatterClauseCustomization,
  TemplateClause,
  addMatterCustomClause,
  deleteMatterClauseCustomization,
  listMatterClauseCustomizations,
  listTemplateClauses,
  setMatterClauseDecision,
} from "@/lib/api";
import { Plus, Trash2, Pencil, Check, X } from "lucide-react";

// Per-matter clause customization (2026-09-11): every lawyer's own
// keep/modify/delete decision on this matter's clauses, plus any
// wholly custom clause they add -- distinct from, and never written
// back to, the shared template's own review status (the "Reviewed" /
// "Beta" badge on the Contracts Workspace picker). Nothing here is
// gated on that shared review status; a template stuck on "Beta" can
// still be fully customized here, per matter.
export function ClauseCustomizationPanel({ matterId, templateId }: { matterId: string; templateId: string }) {
  const [templateClauses, setTemplateClauses] = useState<TemplateClause[]>([]);
  const [customizations, setCustomizations] = useState<MatterClauseCustomization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingClauseId, setEditingClauseId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [addingCustom, setAddingCustom] = useState(false);
  const [customHeading, setCustomHeading] = useState("");
  const [customText, setCustomText] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [clauses, overrides] = await Promise.all([
          listTemplateClauses(templateId),
          listMatterClauseCustomizations(matterId),
        ]);
        if (cancelled) return;
        setTemplateClauses(clauses);
        setCustomizations(overrides);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [matterId, templateId]);

  const overrideByClauseId = new Map(
    customizations.filter((c) => c.template_clause_id).map((c) => [c.template_clause_id as string, c])
  );
  const customClauses = customizations
    .filter((c) => c.decision === "custom")
    .sort((a, b) => a.display_order - b.display_order);

  async function decide(clause: TemplateClause, decision: "kept" | "modified" | "deleted", text?: string) {
    setBusyId(clause.id);
    setError(null);
    try {
      const updated = await setMatterClauseDecision(matterId, clause.id, {
        decision,
        custom_text: decision === "modified" ? text : undefined,
      });
      setCustomizations((prev) => [...prev.filter((c) => c.template_clause_id !== clause.id), updated]);
      setEditingClauseId(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function revert(clause: TemplateClause) {
    const existing = overrideByClauseId.get(clause.id);
    if (!existing) return;
    setBusyId(clause.id);
    setError(null);
    try {
      await deleteMatterClauseCustomization(matterId, existing.id);
      setCustomizations((prev) => prev.filter((c) => c.id !== existing.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function submitCustomClause() {
    if (!customHeading.trim() || !customText.trim()) return;
    setBusyId("custom-new");
    setError(null);
    try {
      const created = await addMatterCustomClause(matterId, {
        heading: customHeading.trim(),
        custom_text: customText.trim(),
      });
      setCustomizations((prev) => [...prev, created]);
      setCustomHeading("");
      setCustomText("");
      setAddingCustom(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function removeCustomClause(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await deleteMatterClauseCustomization(matterId, id);
      setCustomizations((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return <p className="font-serif text-xs text-[#76777F]">Loading clauses…</p>;
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
          Customize Clauses for This Matter
        </h3>
        <p className="mt-1 font-serif text-xs text-[#45464E]">
          Keep, modify, or remove any clause for this matter only — nothing here changes the shared
          template or any other matter. You can also add a clause the template is missing.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-sm border border-[#FFDAD6] bg-[#FFF5F5] p-2 font-serif text-xs text-[#7A2A2A]">
          {error}
        </p>
      )}

      <div className="space-y-2">
        {templateClauses.map((clause) => {
          const override = overrideByClauseId.get(clause.id);
          const decision = override?.decision ?? "kept";
          const displayText = decision === "modified" && override?.custom_text ? override.custom_text : clause.current_text;
          const isEditing = editingClauseId === clause.id;
          const isBusy = busyId === clause.id;

          return (
            <div key={clause.id} className="rounded-sm border border-[#E4E2DD] bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-sans text-xs font-semibold text-[#081534]">
                  {clause.heading || clause.clause_key}
                </span>
                <Badge variant={decision === "deleted" ? "destructive" : decision === "modified" ? "default" : "secondary"}>
                  {decision === "kept" ? "Kept (template text)" : decision === "modified" ? "Modified" : "Removed"}
                </Badge>
              </div>

              {decision !== "deleted" && !isEditing && (
                <p className="mt-1 whitespace-pre-wrap font-serif text-xs text-[#45464E]">{displayText}</p>
              )}

              {isEditing && (
                <div className="mt-2 space-y-2">
                  <Textarea
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    rows={4}
                    className="font-serif text-xs"
                  />
                  <div className="flex gap-2">
                    <Button size="sm" disabled={isBusy || !editText.trim()} onClick={() => decide(clause, "modified", editText)}>
                      <Check className="mr-1 h-3 w-3" /> Save
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setEditingClauseId(null)}>
                      <X className="mr-1 h-3 w-3" /> Cancel
                    </Button>
                  </div>
                </div>
              )}

              {!isEditing && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {decision !== "kept" && (
                    <Button size="sm" variant="outline" disabled={isBusy} onClick={() => revert(clause)}>
                      Keep template text
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={isBusy}
                    onClick={() => {
                      setEditingClauseId(clause.id);
                      setEditText(decision === "modified" && override?.custom_text ? override.custom_text : clause.current_text);
                    }}
                  >
                    <Pencil className="mr-1 h-3 w-3" /> Modify
                  </Button>
                  {decision !== "deleted" && (
                    <Button size="sm" variant="outline" disabled={isBusy} onClick={() => decide(clause, "deleted")}>
                      <Trash2 className="mr-1 h-3 w-3" /> Remove
                    </Button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {customClauses.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
            Custom Clauses Added for This Matter
          </h4>
          {customClauses.map((c) => (
            <div key={c.id} className="rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-sans text-xs font-semibold text-[#081534]">{c.heading}</span>
                <Button size="sm" variant="outline" disabled={busyId === c.id} onClick={() => removeCustomClause(c.id)}>
                  <Trash2 className="mr-1 h-3 w-3" /> Remove
                </Button>
              </div>
              <p className="mt-1 whitespace-pre-wrap font-serif text-xs text-[#45464E]">{c.custom_text}</p>
            </div>
          ))}
        </div>
      )}

      {addingCustom ? (
        <div className="space-y-2 rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] p-3">
          <Input
            placeholder="Clause heading (e.g. Non-Compete)"
            value={customHeading}
            onChange={(e) => setCustomHeading(e.target.value)}
            className="text-xs"
          />
          <Textarea
            placeholder="Clause text"
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            rows={4}
            className="font-serif text-xs"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={busyId === "custom-new" || !customHeading.trim() || !customText.trim()}
              onClick={submitCustomClause}
            >
              <Check className="mr-1 h-3 w-3" /> Add Clause
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setAddingCustom(false);
                setCustomHeading("");
                setCustomText("");
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button size="sm" variant="outline" onClick={() => setAddingCustom(true)}>
          <Plus className="mr-1 h-3 w-3" /> Add a Missing Clause
        </Button>
      )}
    </div>
  );
}
