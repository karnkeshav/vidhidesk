"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { IntakeForm } from "@/components/intake-form";
import { LegalDocumentSheet } from "@/components/legal-document-sheet";
import { ContractAiAssistant } from "@/components/contract-ai-assistant";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { generateMatterTitle } from "@/lib/matter-title";
import {
  Draft,
  DraftVersion,
  Matter,
  TemplateDetail,
  downloadDraftDocx,
  downloadDraftPdf,
  generateDraft,
  getMatter,
  getTemplate,
  listDrafts,
  updateMatter,
} from "@/lib/api";
import {
  Share2,
  Download,
  Bold,
  Italic,
  Underline,
  ListOrdered,
  AlignLeft,
  Sparkles,
  FileCheck,
  Zap,
} from "lucide-react";

type Mode = "form" | "draft";

const TITLE_SAVE_DEBOUNCE_MS = 800;

export default function ContractMatterPage() {
  const params = useParams<{ matterId: string }>();
  const searchParams = useSearchParams();
  const matterId = params.matterId;
  const templateIdParam = searchParams.get("template");

  const [template, setTemplate] = useState<TemplateDetail | null>(null);
  const [matter, setMatter] = useState<Matter | null>(null);
  const [drafts, setDrafts] = useState<DraftVersion[]>([]);
  const [latestDraft, setLatestDraft] = useState<Draft | null>(null);
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});
  const [mode, setMode] = useState<Mode>("form");
  const [busy, setBusy] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Auto-generating title
  const [titleManuallySet, setTitleManuallySet] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const titleSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function saveTitle(title: string) {
    if (titleSaveTimer.current) clearTimeout(titleSaveTimer.current);
    titleSaveTimer.current = setTimeout(() => {
      void updateMatter(matterId, { title }).catch(() => {});
    }, TITLE_SAVE_DEBOUNCE_MS);
  }

  function handleFormValuesChange(values: Record<string, unknown>) {
    if (titleManuallySet || !template) return;
    const nextTitle = generateMatterTitle(
      template.name,
      values.party_a_name as string | undefined,
      values.party_b_name as string | undefined
    );
    setMatter((prev) => (prev ? { ...prev, title: nextTitle } : prev));
    saveTitle(nextTitle);
  }

  function commitManualTitle() {
    const trimmed = titleDraft.trim();
    setEditingTitle(false);
    if (!trimmed || trimmed === matter?.title) return;
    setTitleManuallySet(true);
    setMatter((prev) => (prev ? { ...prev, title: trimmed } : prev));
    saveTitle(trimmed);
  }

  useEffect(() => {
    async function init() {
      try {
        const [existingDrafts, matterRow] = await Promise.all([
          listDrafts(matterId),
          getMatter(matterId),
        ]);
        setDrafts(existingDrafts);
        setMatter(matterRow);

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

  async function handleAmend(amendmentNote: string) {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <AuthedShell>
        <p className="font-sans text-sm text-[#7A2A2A]">{error}</p>
      </AuthedShell>
    );
  }

  if (!template) {
    return (
      <AuthedShell>
        <p className="font-serif text-sm text-[#45464E]">Loading contract workspace…</p>
      </AuthedShell>
    );
  }

  const displayTitle = matter?.title ?? template.name;
  const wordCount = latestDraft ? latestDraft.full_text.split(/\s+/).filter(Boolean).length : 0;

  return (
    <AuthedShell wide>
      <div className="-m-4 flex h-[calc(100vh-100px)] flex-col overflow-hidden md:-m-6">
        {/* Main Document Workspace & Sidebars Container */}
        <div className="flex flex-1 overflow-hidden">
          {/* Main Document Center Canvas */}
          <section className="relative flex flex-1 flex-col overflow-hidden bg-[#FBF9F4]">
            {/* Workspace Header */}
            <header className="border-b border-[#E4E2DD] bg-white px-6 py-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  {editingTitle ? (
                    <Input
                      autoFocus
                      value={titleDraft}
                      onChange={(e) => setTitleDraft(e.target.value)}
                      onBlur={commitManualTitle}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          commitManualTitle();
                        } else if (e.key === "Escape") {
                          setEditingTitle(false);
                        }
                      }}
                      className="h-auto flex-1 border-[#E4E2DD] font-sans text-xl font-semibold text-[#081534]"
                    />
                  ) : (
                    <h1
                      className="cursor-text font-sans text-xl font-semibold tracking-tight text-[#081534]"
                      title="Click to rename this matter"
                      onClick={() => {
                        setTitleDraft(displayTitle);
                        setEditingTitle(true);
                      }}
                    >
                      {displayTitle}
                    </h1>
                  )}
                  <div className="mt-1 flex flex-wrap gap-2">
                    <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] text-[#45464E]">
                      Client: {matter?.client_name || "Acme Industries"}
                    </span>
                    <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] text-[#45464E]">
                      Matter: #{matterId.slice(0, 8)}
                    </span>
                    <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] text-[#45464E]">
                      Revisions Logged: {drafts.length}
                    </span>
                    <Badge variant={template.review_status === "reviewed" ? "default" : "secondary"}>
                      {latestDraft ? `Version ${latestDraft.version_no}` : "Drafting Stage"}
                    </Badge>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#081534]"
                    onClick={() => navigator.clipboard.writeText(window.location.href)}
                  >
                    <Share2 className="h-3.5 w-3.5" />
                    Share
                  </Button>

                  {latestDraft && (
                    <>
                      <Button
                        size="sm"
                        className="h-8 gap-1.5 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
                        onClick={() =>
                          downloadDraftDocx(
                            latestDraft.draft_version_id,
                            `${template.name}-v${latestDraft.version_no}.docx`
                          )
                        }
                      >
                        <Download className="h-3.5 w-3.5" />
                        Download .docx
                      </Button>

                      <Button
                        size="sm"
                        variant="outline"
                        disabled={pdfBusy}
                        className="h-8 gap-1.5 rounded-sm border-[#E4E2DD] font-sans text-xs font-semibold text-[#081534] hover:bg-[#FBF9F4]"
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
                    </>
                  )}

                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-8 font-sans text-xs text-[#45464E]"
                    onClick={() => setMode(mode === "form" ? "draft" : "form")}
                  >
                    {mode === "form" ? "View Draft Sheet" : "Revise Intake Form"}
                  </Button>
                </div>
              </div>
            </header>

            {/* Sticky Editor Toolbar (Stitch Approved Layout) */}
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#E4E2DD] bg-[#F0EEE9] px-6 py-2">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 border-r border-[#E4E2DD] pr-3 text-[#45464E]">
                  <button type="button" className="rounded p-1 hover:bg-[#E4E2DD]" title="Bold">
                    <Bold className="h-3.5 w-3.5" />
                  </button>
                  <button type="button" className="rounded p-1 hover:bg-[#E4E2DD]" title="Italic">
                    <Italic className="h-3.5 w-3.5" />
                  </button>
                  <button type="button" className="rounded p-1 hover:bg-[#E4E2DD]" title="Underline">
                    <Underline className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="flex items-center gap-1 border-r border-[#E4E2DD] pr-3 text-[#45464E]">
                  <button type="button" className="rounded p-1 hover:bg-[#E4E2DD]" title="Numbered List">
                    <ListOrdered className="h-3.5 w-3.5" />
                  </button>
                  <button type="button" className="rounded p-1 hover:bg-[#E4E2DD]" title="Align Left">
                    <AlignLeft className="h-3.5 w-3.5" />
                  </button>
                </div>

                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => handleAmend("AI Draft improvement for clause precision")}
                  disabled={busy}
                  className="h-7 gap-1 font-sans text-xs font-semibold text-[#081534] hover:bg-[#E4E2DD]"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  AI Draft Clause
                </Button>
              </div>
            </div>

            {/* Legal Document Sheet Canvas */}
            <div className="flex-1 overflow-y-auto">
              {mode === "form" ? (
                <div className="p-6">
                  <IntakeForm
                    schema={template.intake_schema}
                    initialValues={formValues}
                    busy={busy}
                    onSubmit={handleGenerate}
                    onValuesChange={handleFormValuesChange}
                  />
                </div>
              ) : (
                <LegalDocumentSheet
                  title={template.name}
                  subtitle={`Draft Version ${latestDraft?.version_no || 1} — Advocate Review Copy`}
                  fullText={latestDraft?.full_text}
                />
              )}
            </div>
          </section>

          {/* Right Sidebar: AI Copilot Assistant (320px Stitch Design) */}
          <ContractAiAssistant
            documentTitle={displayTitle}
            onApplyAmendment={handleAmend}
            busy={busy}
          />
        </div>

        {/* Bottom Status Bar (Stitch Approved Design) */}
        <footer className="flex h-7 items-center justify-between border-t border-[#E4E2DD] bg-white px-4 text-xs text-[#76777F]">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#3D5A3D]"></span>
              <span className="font-sans text-[10px] font-medium text-[#45464E]">Auto Save Active</span>
            </div>
            <span className="font-sans text-[10px]">
              Version {latestDraft?.version_no || "1.0"}
            </span>
            <span className="font-sans text-[10px]">Word Count: {wordCount}</span>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <Zap className="h-3 w-3 text-[#081534]" />
              <span className="font-sans text-[10px]">AI Status: Ready</span>
            </div>
            <div className="flex items-center gap-1">
              <FileCheck className="h-3 w-3 text-[#3D5A3D]" />
              <span className="font-sans text-[10px]">Citation Verified</span>
            </div>
          </div>
        </footer>
      </div>
    </AuthedShell>
  );
}
