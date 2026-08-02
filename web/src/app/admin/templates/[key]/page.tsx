"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  Template,
  TemplateClause,
  bulkKeepBoilerplate,
  getTemplate,
  listTemplateClauses,
  listTemplates,
  reviewClause,
} from "@/lib/api";

// Sprint 3 note (not yet built — see docs/sprint_3_backlog.md "Lever 3"):
// clauses currently render in a template's own display_order. A review-
// sequencing recommendation (shared fixed_boilerplate first, bespoke
// llm_fillable last, cross-template "N clauses need one review each"
// framing on the admin index) would help once Lever 2's cross-template
// shared-clause detection exists to make "shared" a computable claim.

const STATUS_LABEL: Record<TemplateClause["review_status"], string> = {
  unreviewed: "Unreviewed",
  kept: "Kept",
  redrafted: "Redrafted",
  deleted: "Deleted",
};

const STATUS_VARIANT: Record<TemplateClause["review_status"], "secondary" | "default" | "destructive"> = {
  unreviewed: "secondary",
  kept: "default",
  redrafted: "default",
  deleted: "destructive",
};

export default function TemplateReviewPage() {
  const params = useParams<{ key: string }>();
  const [template, setTemplate] = useState<Template | null>(null);
  const [clauses, setClauses] = useState<TemplateClause[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [redraftText, setRedraftText] = useState("");
  const [reviewerNotes, setReviewerNotes] = useState("");
  const [actionMode, setActionMode] = useState<"none" | "redraft" | "delete">("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const templates = await listTemplates();
        const tpl = templates.find((t) => t.template_key === params.key);
        if (!tpl) {
          setError(`No template with key "${params.key}".`);
          return;
        }
        setTemplate(tpl);
        const rows = await listTemplateClauses(tpl.id);
        setClauses(rows);
        setSelectedId(rows[0]?.id ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }
    void init();
  }, [params.key]);

  const selected = clauses.find((c) => c.id === selectedId) ?? null;
  const reviewedCount = clauses.filter((c) => c.review_status !== "unreviewed").length;
  const unreviewedBoilerplateCount = clauses.filter(
    (c) => c.clause_type === "fixed_boilerplate" && c.review_status === "unreviewed"
  ).length;

  async function handleBulkKeepBoilerplate() {
    if (!template) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await bulkKeepBoilerplate(template.id);
      const updatedById = new Map(updated.map((c) => [c.id, c]));
      setClauses((prev) => prev.map((c) => updatedById.get(c.id) ?? c));
      // Same staleness fix as submitDecision — bulk-keep can also flip
      // the template beta -> reviewed if these were the last unreviewed
      // clauses.
      const refreshedTemplate = await getTemplate(template.id);
      setTemplate(refreshedTemplate);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  function resetActionState() {
    setActionMode("none");
    setRedraftText("");
    setReviewerNotes("");
  }

  async function submitDecision(decision: "keep" | "redraft" | "delete") {
    if (!template || !selected) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await reviewClause(template.id, selected.id, {
        decision,
        redraft_text: decision === "redraft" ? redraftText : undefined,
        reviewer_notes: reviewerNotes || undefined,
      });
      setClauses((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      // The backend may have just flipped beta -> reviewed (the last
      // clause clearing review) — refetch so the badge doesn't go stale.
      // Found via E2E testing: without this, templates.review_status was
      // correctly 'reviewed' in the DB but the UI kept showing "Beta"
      // until a manual page reload.
      const refreshedTemplate = await getTemplate(template.id);
      setTemplate(refreshedTemplate);
      resetActionState();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <AuthedShell wide>
        <p className="text-sm text-destructive">{error}</p>
      </AuthedShell>
    );
  }
  if (!template) {
    return (
      <AuthedShell wide>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </AuthedShell>
    );
  }

  return (
    <AuthedShell wide>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">{template.name} — clause review</h1>
            <p className="text-sm text-muted-foreground">
              {reviewedCount}/{clauses.length} clauses reviewed
            </p>
          </div>
          <div className="flex items-center gap-2">
            {unreviewedBoilerplateCount > 0 && (
              <Button size="sm" variant="outline" disabled={busy} onClick={handleBulkKeepBoilerplate}>
                Keep all boilerplate ({unreviewedBoilerplateCount})
              </Button>
            )}
            <Badge variant={template.review_status === "reviewed" ? "default" : "secondary"}>
              {template.review_status === "reviewed" ? "Reviewed" : "Beta — pending clause review"}
            </Badge>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-[16rem_1fr]">
          <div className="space-y-1">
            {clauses.map((c) => (
              <button
                key={c.id}
                onClick={() => {
                  setSelectedId(c.id);
                  resetActionState();
                }}
                className={cn(
                  "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm",
                  c.id === selectedId ? "border-primary bg-accent" : "hover:bg-accent"
                )}
              >
                <span className="truncate">{c.clause_key}</span>
                <Badge variant={STATUS_VARIANT[c.review_status]} className="ml-2 shrink-0">
                  {STATUS_LABEL[c.review_status]}
                </Badge>
              </button>
            ))}
          </div>

          {selected && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-base">
                  <span>{selected.clause_key}</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {selected.clause_type === "llm_fillable"
                      ? "LLM-fillable — reviewing the prompt/instructions"
                      : "Fixed boilerplate"}
                    {selected.applicable_condition &&
                      ` · shown when ${selected.applicable_condition.field} = ${JSON.stringify(
                        selected.applicable_condition.equals ?? selected.applicable_condition.not_equals
                      )}`}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {error && <p className="text-sm text-destructive">{error}</p>}
                <pre className="max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded-md border bg-muted/30 p-4 font-mono text-xs">
                  {selected.current_text}
                </pre>

                {actionMode === "none" && (
                  <div className="flex gap-2">
                    <Button size="sm" disabled={busy} onClick={() => submitDecision("keep")}>
                      Keep
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => setActionMode("redraft")}>
                      Redraft
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => setActionMode("delete")}
                    >
                      Delete
                    </Button>
                  </div>
                )}

                {actionMode === "redraft" && (
                  <div className="space-y-2">
                    <Textarea
                      value={redraftText}
                      onChange={(e) => setRedraftText(e.target.value)}
                      placeholder="Revised clause text…"
                      rows={6}
                    />
                    <Textarea
                      value={reviewerNotes}
                      onChange={(e) => setReviewerNotes(e.target.value)}
                      placeholder="Reviewer note (optional) — why this changed"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        disabled={busy || !redraftText.trim()}
                        onClick={() => submitDecision("redraft")}
                      >
                        Save redraft
                      </Button>
                      <Button size="sm" variant="ghost" onClick={resetActionState}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {actionMode === "delete" && (
                  <div className="space-y-2">
                    <p className="text-sm text-destructive">
                      Deleting removes this clause from future drafts of this template. This
                      requires a note explaining why.
                    </p>
                    <Textarea
                      value={reviewerNotes}
                      onChange={(e) => setReviewerNotes(e.target.value)}
                      placeholder="Why is this clause being deleted? (required)"
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={busy || !reviewerNotes.trim()}
                        onClick={() => submitDecision("delete")}
                      >
                        Confirm delete
                      </Button>
                      <Button size="sm" variant="ghost" onClick={resetActionState}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </AuthedShell>
  );
}
