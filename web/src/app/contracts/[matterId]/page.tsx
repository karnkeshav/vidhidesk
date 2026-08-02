"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { IntakeForm } from "@/components/intake-form";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Draft,
  DraftVersion,
  TemplateDetail,
  downloadDraftDocx,
  downloadDraftPdf,
  generateDraft,
  getTemplate,
  listDrafts,
} from "@/lib/api";

type Mode = "form" | "draft";

export default function ContractMatterPage() {
  const params = useParams<{ matterId: string }>();
  const searchParams = useSearchParams();
  const matterId = params.matterId;
  const templateIdParam = searchParams.get("template");

  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [drafts, setDrafts] = useState<DraftVersion[]>([]);
  const [latestDraft, setLatestDraft] = useState<Draft | null>(null);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [mode, setMode] = useState<Mode>("form");
  const [amendmentNote, setAmendmentNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const existingDrafts = await listDrafts(matterId);
        setDrafts(existingDrafts);

        const templateId = templateIdParam ?? existingDrafts[0]?.template_id;
        if (!templateId) {
          setError("No template specified and no existing drafts for this matter.");
          return;
        }
        const tpl = await getTemplate(templateId);
        setTemplate(tpl);
        if (existingDrafts.length > 0) setMode("draft");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }
    void init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId, templateIdParam]);

  // The plain-text preview (per Sprint 2's own sanctioned fallback: "docx
  // preview OR plain-text-in-a-monospace-block if preview is complex") is
  // the server's own fully-rendered assembly (generateDraft's
  // `full_text`) — not reconstructed client-side. A client-side rebuild
  // was tried first and dropped: fixed_boilerplate clauses are now
  // Jinja-rendered server-side (loops, substitutions), which the browser
  // has no way to reproduce from raw clause text alone.

  async function handleGenerate(values: Record<string, unknown>) {
    if (!template) return;
    setBusy(true);
    setError(null);
    try {
      const draft = await generateDraft(matterId, { template_id: template.id, form_data: values });
      setFormValues(values);
      setLatestDraft(draft);
      setDrafts(await listDrafts(matterId));
      setMode("draft");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAmend() {
    if (!template || !amendmentNote.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const draft = await generateDraft(matterId, {
        template_id: template.id,
        form_data: formValues,
        amendment_note: amendmentNote,
      });
      setLatestDraft(draft);
      setDrafts(await listDrafts(matterId));
      setAmendmentNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <AuthedShell>
        <p className="text-sm text-destructive">{error}</p>
      </AuthedShell>
    );
  }

  if (!template) {
    return (
      <AuthedShell>
        <p className="text-sm text-muted-foreground">Loading…</p>
      </AuthedShell>
    );
  }

  return (
    <AuthedShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">{template.name}</h1>
          <Badge variant={template.review_status === "reviewed" ? "default" : "secondary"}>
            {template.review_status === "reviewed" ? "Reviewed" : "Beta — pending clause review"}
          </Badge>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {mode === "form" && (
          <IntakeForm
            schema={template.intake_schema}
            initialValues={formValues}
            busy={busy}
            onSubmit={handleGenerate}
          />
        )}

        {mode === "draft" && latestDraft && (
          <div className="space-y-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-base">Draft — version {latestDraft.version_no}</CardTitle>
                <div className="flex items-center gap-2">
                  {/* .docx is the working artifact and the default action —
                      solid/primary. .pdf is a final artifact generated
                      lazily on click (headless LibreOffice conversion adds
                      3-8s) and is visually secondary on purpose, not
                      offered with equal weight next to .docx. */}
                  <Button
                    size="sm"
                    onClick={() => downloadDraftDocx(latestDraft.draft_version_id, `${template.name}-v${latestDraft.version_no}.docx`)}
                  >
                    Download .docx
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={pdfBusy}
                    title="Generates a PDF on click (a few seconds) — the .docx is the editable working copy"
                    onClick={async () => {
                      setPdfBusy(true);
                      setError(null);
                      try {
                        await downloadDraftPdf(
                          latestDraft.draft_version_id,
                          `${template.name}-v${latestDraft.version_no}.pdf`
                        );
                      } catch (err) {
                        setError(err instanceof Error ? err.message : String(err));
                      } finally {
                        setPdfBusy(false);
                      }
                    }}
                  >
                    {pdfBusy ? "Generating PDF…" : "Download .pdf"}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setMode("form")}>
                    Revise intake form
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="max-h-[50vh] overflow-y-auto whitespace-pre-wrap rounded-md border bg-muted/30 p-4 font-mono text-xs">
                  {latestDraft.full_text}
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Amend this draft</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  value={amendmentNote}
                  onChange={(e) => setAmendmentNote(e.target.value)}
                  placeholder='e.g. "reduce lock-in to 12 months", "add arbitration seat Delhi"'
                  rows={2}
                />
                <Button onClick={handleAmend} disabled={busy || !amendmentNote.trim()}>
                  {busy ? "Regenerating…" : "Apply amendment (new version)"}
                </Button>
              </CardContent>
            </Card>

            {drafts.length > 1 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Version history</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {drafts.map((d) => (
                    <div key={d.id} className="flex items-center justify-between text-sm">
                      <div>
                        <span className="font-medium">v{d.version_no}</span>{" "}
                        <span className="text-muted-foreground">{d.change_summary}</span>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => downloadDraftDocx(d.id, `${template.name}-v${d.version_no}.docx`)}
                      >
                        Download
                      </Button>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </AuthedShell>
  );
}
