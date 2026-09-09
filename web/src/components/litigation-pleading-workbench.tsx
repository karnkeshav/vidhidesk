"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  PleadingOutline,
  PleadingClause,
  PleadingDraft,
  CaseAnalysis,
  listCaseAnalyses,
  ClauseGround,
  generatePleadingOutline,
  listPleadingOutlines,
  generateClause,
  listClauses,
  reviewPleadingClause,
  composePleading,
  listPleadingDrafts,
  downloadPleadingDocx,
  downloadPleadingPdf
} from "@/lib/api";
import {
  FileText,
  Layers,
  Eye,
  Download,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Check,
  X,
  FileCheck2
} from "lucide-react";
import { cn } from "@/lib/utils";

interface PleadingWorkbenchProps {
  matterId: string;
  latestCaseAnalysis: CaseAnalysis | null;
}

const CLAUSE_TYPES = [
  "cause_title",
  "court_details",
  "parties",
  "jurisdiction",
  "facts",
  "chronology",
  "cause_of_action",
  "legal_grounds",
  "applicable_statutes",
  "applicable_precedents",
  "reliefs",
  "prayer",
  "verification",
  "annexures",
] as const;

const CLAUSE_HEADINGS: Record<string, string> = {
  cause_title: "Cause Title",
  court_details: "Court Details",
  parties: "Parties",
  jurisdiction: "Jurisdiction",
  facts: "Facts",
  chronology: "Chronology",
  cause_of_action: "Cause of Action",
  legal_grounds: "Legal Grounds",
  applicable_statutes: "Applicable Statutes",
  applicable_precedents: "Applicable Precedents",
  reliefs: "Reliefs",
  prayer: "Prayer",
  verification: "Verification",
  annexures: "List of Annexures",
};

const DETERMINISTIC_CLAUSES = new Set([
  "cause_title",
  "court_details",
  "parties",
  "jurisdiction",
  "chronology",
  "applicable_statutes",
  "applicable_precedents",
  "verification",
  "annexures",
]);

function getClauseText(content: PleadingClause["content"]): string {
  if (!content) return "";
  if (typeof content === "string") return content;
  return content.text || "";
}

function getClauseGrounds(content: PleadingClause["content"]): ClauseGround[] {
  if (!content || typeof content === "string") return [];
  return content.grounds || [];
}

export function LitigationPleadingWorkbench({ matterId, latestCaseAnalysis }: PleadingWorkbenchProps) {
  const [outline, setOutline] = useState<PleadingOutline | null>(null);
  const [clauses, setClauses] = useState<PleadingClause[]>([]);
  const [drafts, setDrafts] = useState<PleadingDraft[]>([]);
  const [fetchedAnalysis, setFetchedAnalysis] = useState<CaseAnalysis | null>(null);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [isGeneratingClause, setIsGeneratingClause] = useState<string | null>(null);
  const [isBatchGenerating, setIsBatchGenerating] = useState(false);
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; currentType: string } | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState(false);

  // Export states
  const [isExporting, setIsExporting] = useState<"docx" | "pdf" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  // 1: Outline, 2: Clauses/Review, 3: Preview/Export
  const [workflowStage, setWorkflowStage] = useState(1);

  const activeAnalysis = latestCaseAnalysis || fetchedAnalysis;

  async function loadData() {
    try {
      const [outlines, analysesList] = await Promise.all([
        listPleadingOutlines(matterId).catch(() => []),
        listCaseAnalyses(matterId).catch(() => []),
      ]);
      if (analysesList.length > 0) {
        setFetchedAnalysis(analysesList[0]);
      }
      if (outlines.length > 0) {
        setOutline(outlines[0]);
        setWorkflowStage(2);
        const [cls, drfs] = await Promise.all([
          listClauses(matterId, outlines[0].id),
          listPleadingDrafts(matterId, outlines[0].id)
        ]);
        setClauses(cls);
        setDrafts(drfs);
        if (drfs.length > 0) {
          setWorkflowStage(3);
        }
      }
    } catch (err) {
      console.error("Failed to load pleading workbench data:", err);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId, latestCaseAnalysis?.id]);

  async function handleGenerateOutline() {
    if (!activeAnalysis) {
      setError("A Case Analysis is required before generating a pleading outline.");
      return;
    }
    setIsGeneratingOutline(true);
    setError(null);
    try {
      const out = await generatePleadingOutline(matterId, { case_analysis_id: activeAnalysis.id });
      setOutline(out);
      setWorkflowStage(2);
      const cls = await listClauses(matterId, out.id);
      setClauses(cls);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsGeneratingOutline(false);
    }
  }

  async function handleGenerateClause(clauseType: string) {
    if (!outline) return;
    setIsGeneratingClause(clauseType);
    setError(null);
    try {
      const cl = await generateClause(matterId, clauseType, { pleading_outline_id: outline.id });
      setClauses(prev => {
        const filtered = prev.filter(c => c.clause_type !== clauseType);
        return [cl, ...filtered];
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsGeneratingClause(null);
    }
  }

  async function handleGenerateAllClauses() {
    if (!outline || isBatchGenerating) return;
    setIsBatchGenerating(true);
    setError(null);

    const total = CLAUSE_TYPES.length;
    let completed = 0;

    for (const clauseType of CLAUSE_TYPES) {
      setBatchProgress({ current: completed + 1, total, currentType: CLAUSE_HEADINGS[clauseType] || clauseType });
      try {
        const cl = await generateClause(matterId, clauseType, { pleading_outline_id: outline.id });
        setClauses(prev => {
          const filtered = prev.filter(c => c.clause_type !== clauseType);
          return [cl, ...filtered];
        });
      } catch (err) {
        console.error(`Failed generating clause ${clauseType}:`, err);
        setError(`Failed drafting ${CLAUSE_HEADINGS[clauseType] || clauseType}: ${err instanceof Error ? err.message : String(err)}`);
      }
      completed++;
    }

    setIsBatchGenerating(false);
    setBatchProgress(null);
  }

  async function handleReviewClause(clauseId: string, status: "approved" | "rejected") {
    try {
      const cl = await reviewPleadingClause(matterId, clauseId, status);
      setClauses(prev => prev.map(c => c.id === clauseId ? cl : c));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleApproveAllClauses() {
    setError(null);
    const unapproved = clauses.filter(c => c.review_status !== "approved");
    for (const cl of unapproved) {
      try {
        const updated = await reviewPleadingClause(matterId, cl.id, "approved");
        setClauses(prev => prev.map(c => c.id === cl.id ? updated : c));
      } catch (err) {
        console.error(`Failed approving clause ${cl.clause_type}:`, err);
      }
    }
  }

  async function handleCompose() {
    if (!outline) return;
    setIsComposing(true);
    setError(null);
    try {
      const d = await composePleading(matterId, { pleading_outline_id: outline.id });
      setDrafts([d, ...drafts]);
      setWorkflowStage(3);
      setPreviewMode(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsComposing(false);
    }
  }

  async function handleExport(format: "docx" | "pdf") {
    if (drafts.length === 0 || isExporting) return;
    const currentDraft = drafts[0];

    setIsExporting(format);
    setExportError(null);
    setExportSuccess(null);

    try {
      if (format === "docx") {
        await downloadPleadingDocx(matterId, currentDraft.id, `Pleading_${matterId}.docx`);
      } else {
        await downloadPleadingPdf(matterId, currentDraft.id, `Pleading_${matterId}.pdf`);
      }
      setExportSuccess(`Successfully downloaded ${format.toUpperCase()}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to export document";
      if (msg.includes("501") || msg.includes("LibreOffice") || msg.includes("soffice")) {
        setExportError("PDF export requires LibreOffice on the server. Please export as DOCX.");
      } else {
        setExportError(msg);
      }
    } finally {
      setIsExporting(null);
    }
  }

  const latestDraft = drafts[0];
  const approvedCount = clauses.filter(c => c.review_status === "approved").length;
  const canCompose = approvedCount > 0;

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A] flex items-start justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-[#7A2A2A] hover:opacity-75 text-sm font-bold ml-2">&times;</button>
        </div>
      )}

      {/* Workflow Progress Tracker */}
      <div className="flex items-center gap-2 mb-6 border-b border-[#E4E2DD] pb-4">
        <div
          onClick={() => setWorkflowStage(1)}
          className={cn(
            "flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase cursor-pointer transition-colors",
            workflowStage >= 1 ? "text-[#081534]" : "text-[#76777F]"
          )}
        >
          <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-white", workflowStage >= 1 ? "bg-[#081534]" : "bg-[#C6C6CF]")}>1</div>
          1. Plan Outline
        </div>
        <div className="flex-1 h-px bg-[#E4E2DD]"></div>
        <div
          onClick={() => outline && setWorkflowStage(2)}
          className={cn(
            "flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase transition-colors",
            outline ? "cursor-pointer" : "cursor-not-allowed",
            workflowStage >= 2 ? "text-[#081534]" : "text-[#76777F]"
          )}
        >
          <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-white", workflowStage >= 2 ? "bg-[#081534]" : "bg-[#C6C6CF]")}>2</div>
          2. Clause Workbench ({clauses.length}/14 Drafted)
        </div>
        <div className="flex-1 h-px bg-[#E4E2DD]"></div>
        <div
          onClick={() => drafts.length > 0 && (setWorkflowStage(3), setPreviewMode(true))}
          className={cn(
            "flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase transition-colors",
            drafts.length > 0 ? "cursor-pointer" : "cursor-not-allowed",
            workflowStage >= 3 ? "text-[#081534]" : "text-[#76777F]"
          )}
        >
          <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-white", workflowStage >= 3 ? "bg-[#081534]" : "bg-[#C6C6CF]")}>3</div>
          3. Final Pleading Draft
        </div>
      </div>

      {workflowStage === 1 && (
        <div className="rounded-sm border border-[#E4E2DD] bg-white p-8 flex flex-col items-center justify-center text-center space-y-4 min-h-[340px]">
          <div className="h-14 w-14 rounded-full bg-[#F0EEE9] flex items-center justify-center text-[#081534]">
            <Layers className="h-7 w-7" />
          </div>
          <div>
            <h3 className="font-sans text-lg font-bold text-[#081534]">Pleading Planning & Architecture</h3>
            <p className="font-serif text-sm text-[#45464E] max-w-lg mx-auto mt-2 leading-relaxed">
              Transform the AI Case Analysis into a structured 14-clause pleading framework (Cause Title, Jurisdiction, Grounds, Reliefs, Prayer, Annexures).
            </p>
          </div>
          <Button
            onClick={handleGenerateOutline}
            disabled={isGeneratingOutline || !activeAnalysis}
            className="bg-[#081534] text-white font-sans text-xs font-semibold hover:bg-[#1E2A4A] h-10 px-8 mt-2"
          >
            {isGeneratingOutline ? (
              <>
                <Sparkles className="h-4 w-4 mr-2 animate-spin" /> Structuring Plan...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" /> Generate Pleading Outline
              </>
            )}
          </Button>
          {!activeAnalysis && (
            <p className="text-[#7A2A2A] font-sans text-xs mt-2">
              Generate an AI Case Analysis first before creating a pleading outline.
            </p>
          )}
          {outline && (
            <div className="pt-4 border-t border-[#E4E2DD] w-full max-w-md">
              <span className="text-xs text-[#76777F] font-sans">Existing Outline v{outline.version_no} is ready. </span>
              <button onClick={() => setWorkflowStage(2)} className="text-xs font-semibold text-[#081534] underline font-sans ml-1">
                Go to Clause Workbench &rarr;
              </button>
            </div>
          )}
        </div>
      )}

      {workflowStage >= 2 && !previewMode && (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-8 space-y-4">
            {/* Document Action Bar */}
            <div className="flex flex-wrap items-center justify-between rounded-sm border border-[#E4E2DD] bg-white p-3.5 shadow-sm gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  onClick={handleGenerateAllClauses}
                  disabled={isBatchGenerating || !!isGeneratingClause}
                  className="h-8 bg-[#081534] text-white text-xs font-semibold font-sans hover:bg-[#1E2A4A]"
                >
                  <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                  {isBatchGenerating ? `Drafting (${batchProgress?.current}/${batchProgress?.total})...` : "Generate All 14 Clauses"}
                </Button>

                {clauses.some(c => c.review_status !== "approved") && (
                  <Button
                    onClick={handleApproveAllClauses}
                    variant="outline"
                    className="h-8 text-xs font-semibold font-sans border-[#C3E6CB] text-[#155724] bg-[#F4FBF6] hover:bg-[#D4EDDA]"
                  >
                    <Check className="h-3.5 w-3.5 mr-1" /> Approve All Drafted
                  </Button>
                )}

                <Button
                  onClick={handleCompose}
                  disabled={isComposing || !canCompose}
                  variant="outline"
                  className={cn(
                    "h-8 text-xs font-semibold font-sans border-[#E4E2DD]",
                    canCompose ? "text-[#081534] hover:bg-[#F0EEE9]" : "text-[#76777F] opacity-60"
                  )}
                >
                  <FileText className="h-3.5 w-3.5 mr-1.5" />
                  {isComposing ? "Composing..." : `Compose Document (${approvedCount}/14 Approved)`}
                </Button>

                {drafts.length > 0 && (
                  <Button
                    onClick={() => setPreviewMode(true)}
                    variant="outline"
                    className="h-8 text-xs font-semibold font-sans border-[#E4E2DD] text-[#081534] hover:bg-[#F0EEE9]"
                  >
                    <Eye className="h-3.5 w-3.5 mr-1.5" />
                    Preview Draft v{drafts[0].version_no}
                  </Button>
                )}
              </div>

              <div className="flex items-center gap-2">
                {exportError && <span className="text-[#7A2A2A] font-sans text-[11px] font-bold uppercase">{exportError}</span>}
                {exportSuccess && <span className="text-[#155724] font-sans text-[11px] font-bold uppercase">{exportSuccess}</span>}
                {latestDraft && !exportError && !exportSuccess && (
                  <Button
                    onClick={() => handleExport("docx")}
                    disabled={isExporting !== null}
                    variant="outline"
                    className="h-8 border-[#E4E2DD] text-[#081534] text-xs font-semibold font-sans hover:bg-[#F0EEE9]"
                  >
                    <Download className="h-3.5 w-3.5 mr-1.5" />
                    {isExporting === "docx" ? "Exporting..." : "DOCX"}
                  </Button>
                )}
              </div>
            </div>

            {/* Batch generation progress banner */}
            {isBatchGenerating && batchProgress && (
              <div className="rounded-sm border border-[#B8DAFF] bg-[#EBF5FF] p-3 font-sans text-xs text-[#004085] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 animate-spin text-[#004085]" />
                  <span>Drafting clause {batchProgress.current} of {batchProgress.total}: <strong>{batchProgress.currentType}</strong>...</span>
                </div>
                <span className="font-mono font-bold">{Math.round((batchProgress.current / batchProgress.total) * 100)}%</span>
              </div>
            )}

            {/* Clauses List */}
            <div className="space-y-3">
              {CLAUSE_TYPES.map((type, index) => {
                const clause = clauses.find(c => c.clause_type === type);
                const isGenerating = isGeneratingClause === type;
                const isDeterministic = DETERMINISTIC_CLAUSES.has(type);
                const heading = CLAUSE_HEADINGS[type] || type;
                const textContent = clause ? getClauseText(clause.content) : "";
                const grounds = clause ? getClauseGrounds(clause.content) : [];

                return (
                  <div key={type} className="rounded-sm border border-[#E4E2DD] bg-white overflow-hidden shadow-2xs">
                    <div className="bg-[#FBF9F4] border-b border-[#E4E2DD] px-4 py-2.5 flex items-center justify-between">
                      <div className="flex items-center gap-2.5">
                        <span className="text-[11px] font-mono font-bold text-[#76777F] w-5">{index + 1}.</span>
                        <h4 className="font-sans text-xs font-bold uppercase text-[#081534] tracking-wide">{heading}</h4>
                        <span className={cn(
                          "px-2 py-0.5 rounded-full text-[9px] font-sans font-bold uppercase tracking-wider",
                          isDeterministic ? "bg-[#EAE8E3] text-[#45464E]" : "bg-[#EDE9FE] text-[#5B21B6]"
                        )}>
                          {isDeterministic ? "Deterministic / Grounded" : "AI Synthesized"}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {clause ? (
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              "px-2 py-0.5 rounded-xs font-sans text-[10px] font-bold uppercase border",
                              clause.review_status === "pending" ? "bg-[#FFF3CD] text-[#856404] border-[#FFEEBA]" :
                              clause.review_status === "approved" ? "bg-[#D4EDDA] text-[#155724] border-[#C3E6CB]" :
                              "bg-[#FFF5F5] text-[#7A2A2A] border-[#F8D7DA]"
                            )}>
                              {clause.review_status === "pending" ? "Pending Review" : clause.review_status}
                            </span>
                            <span className="text-[#76777F] font-sans text-[10px]">v{clause.version_no}</span>
                            <Button
                              onClick={() => handleGenerateClause(type)}
                              disabled={isGenerating || isBatchGenerating}
                              variant="ghost"
                              className="h-6 w-6 p-0 text-[#76777F] hover:text-[#081534]"
                              title="Regenerate clause"
                            >
                              <RefreshCw className={cn("h-3 w-3", isGenerating && "animate-spin")} />
                            </Button>
                          </div>
                        ) : (
                          <Button
                            onClick={() => handleGenerateClause(type)}
                            disabled={isGenerating || isBatchGenerating}
                            variant="outline"
                            className="h-7 text-[11px] font-sans bg-white border-[#E4E2DD] text-[#081534] hover:bg-[#F0EEE9]"
                          >
                            <Sparkles className={cn("h-3 w-3 mr-1 text-[#081534]", isGenerating && "animate-spin")} />
                            {isGenerating ? "Drafting..." : "Generate Clause"}
                          </Button>
                        )}
                      </div>
                    </div>

                    {clause && (
                      <div className="p-4 space-y-3">
                        {/* Render clause text safely */}
                        <div className="font-serif text-sm leading-relaxed text-[#1A1A1A] whitespace-pre-wrap bg-[#FCFCFA] p-3 rounded-xs border border-[#F0EEE9]">
                          {textContent || <span className="text-[#76777F] italic">No text generated. Click regenerate to retry.</span>}
                        </div>

                        {/* If legal grounds has structured issues */}
                        {grounds.length > 0 && (
                          <div className="space-y-2 pt-2 border-t border-[#F0EEE9]">
                            <span className="text-[11px] font-sans font-bold uppercase text-[#45464E]">Structured Ground Breakdown:</span>
                            <div className="grid grid-cols-1 gap-2">
                              {grounds.map((g, gi) => (
                                <div key={gi} className="rounded-xs border border-[#E4E2DD] p-2.5 bg-white text-xs space-y-1.5">
                                  <div className="font-bold text-[#081534] font-sans">{g.issue}</div>
                                  <div className="font-serif text-[#45464E]">{g.argument_note}</div>
                                  <div className="flex flex-wrap gap-1.5 pt-1">
                                    {g.statute_refs?.map((s, si) => (
                                      <span key={si} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs bg-[#F0EEE9] text-[10px] font-mono text-[#081534]">
                                        <ShieldCheck className="h-3 w-3 text-[#155724]" />
                                        {s.act} § {s.section_no}
                                      </span>
                                    ))}
                                    {g.case_law_refs?.map((c, ci) => (
                                      <a
                                        key={ci}
                                        href={c.ik_url || `https://indiankanoon.org/search/?formInput=${encodeURIComponent(c.case_name)}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs bg-[#EBF5FF] text-[10px] text-[#004085] hover:underline"
                                      >
                                        <ExternalLink className="h-2.5 w-2.5" />
                                        {c.case_name} ({c.status})
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Citations bar */}
                        {(clause.statute_refs?.length > 0 || clause.case_law_refs?.length > 0) && grounds.length === 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {clause.statute_refs?.map((s, si) => (
                              <span key={si} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs bg-[#F0EEE9] text-[10px] font-mono text-[#081534]">
                                <ShieldCheck className="h-3 w-3 text-[#155724]" />
                                {s.act} § {s.section_no}
                              </span>
                            ))}
                            {clause.case_law_refs?.map((c, ci) => (
                              <a
                                key={ci}
                                href={c.ik_url || `https://indiankanoon.org/search/?formInput=${encodeURIComponent(c.case_name)}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs bg-[#EBF5FF] text-[10px] text-[#004085] hover:underline"
                              >
                                <ExternalLink className="h-2.5 w-2.5" />
                                {c.case_name}
                              </a>
                            ))}
                          </div>
                        )}

                        {/* Actions bar */}
                        <div className="flex items-center justify-between pt-2 border-t border-[#E4E2DD]">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-sans text-[#76777F]">
                              Confidence: <strong>{Math.round((clause.confidence || 1) * 100)}%</strong>
                            </span>
                            {clause.model_used && (
                              <span className="text-[10px] font-mono text-[#76777F]">({clause.model_used})</span>
                            )}
                          </div>

                          <div className="flex items-center gap-2">
                            {clause.review_status === "pending" && (
                              <>
                                <Button
                                  onClick={() => handleReviewClause(clause.id, "rejected")}
                                  variant="outline"
                                  className="h-7 text-xs text-[#7A2A2A] border-[#F8D7DA] hover:bg-[#FFF5F5]"
                                >
                                  <X className="h-3 w-3 mr-1" /> Reject
                                </Button>
                                <Button
                                  onClick={() => handleReviewClause(clause.id, "approved")}
                                  className="h-7 text-xs bg-[#155724] text-white hover:bg-[#0E3D19]"
                                >
                                  <Check className="h-3 w-3 mr-1" /> Approve
                                </Button>
                              </>
                            )}
                            {clause.review_status === "approved" && (
                              <Button
                                onClick={() => handleReviewClause(clause.id, "rejected")}
                                variant="outline"
                                className="h-7 text-xs text-[#76777F] border-[#E4E2DD] hover:bg-[#F0EEE9]"
                              >
                                Revoke Approval
                              </Button>
                            )}
                            {clause.review_status === "rejected" && (
                              <Button
                                onClick={() => handleReviewClause(clause.id, "approved")}
                                className="h-7 text-xs bg-[#155724] text-white hover:bg-[#0E3D19]"
                              >
                                <Check className="h-3 w-3 mr-1" /> Approve
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="md:col-span-4 space-y-4">
            <div className="rounded-sm border border-[#E4E2DD] bg-white p-4 sticky top-4 shadow-2xs">
              <h4 className="font-sans text-xs font-bold uppercase text-[#081534] tracking-wide mb-3 flex items-center gap-1.5 border-b border-[#E4E2DD] pb-2">
                <FileCheck2 className="h-4 w-4 text-[#081534]" />
                Pleading Assembly Status
              </h4>
              <p className="font-serif text-xs text-[#45464E] leading-relaxed mb-4">
                The Advocate remains the final authority. Approved clauses are compiled directly into the legal court filing format.
              </p>

              <div className="space-y-2.5 font-sans text-xs border-t border-[#E4E2DD] pt-3">
                <div className="flex justify-between items-center py-0.5">
                  <span className="text-[#45464E]">Total Pleading Clauses</span>
                  <span className="font-bold text-[#081534]">{CLAUSE_TYPES.length}</span>
                </div>
                <div className="flex justify-between items-center py-0.5">
                  <span className="text-[#45464E]">Drafted Clauses</span>
                  <span className="font-bold text-[#081534]">{clauses.length} / 14</span>
                </div>
                <div className="flex justify-between items-center py-0.5 text-[#155724]">
                  <span>Approved Clauses</span>
                  <span className="font-bold">{approvedCount} / 14</span>
                </div>
                <div className="flex justify-between items-center py-0.5 text-[#856404]">
                  <span>Pending Review</span>
                  <span className="font-bold">{clauses.filter(c => c.review_status === "pending").length}</span>
                </div>
                <div className="flex justify-between items-center py-0.5 text-[#7A2A2A]">
                  <span>Rejected Clauses</span>
                  <span className="font-bold">{clauses.filter(c => c.review_status === "rejected").length}</span>
                </div>
              </div>

              <div className="pt-4 mt-3 border-t border-[#E4E2DD] space-y-2">
                <Button
                  onClick={handleCompose}
                  disabled={isComposing || !canCompose}
                  className="w-full bg-[#081534] text-white text-xs font-semibold font-sans hover:bg-[#1E2A4A] h-9"
                >
                  <FileText className="h-3.5 w-3.5 mr-1.5" />
                  {isComposing ? "Composing Document..." : `Compose Pleading (${approvedCount}/14)`}
                </Button>
                {!canCompose && (
                  <p className="text-[11px] text-[#76777F] font-sans text-center">
                    Approve at least one clause to generate a composed draft.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {previewMode && latestDraft && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-sm border border-[#E4E2DD] bg-white p-3.5 shadow-sm">
            <Button onClick={() => setPreviewMode(false)} variant="outline" className="h-8 text-xs font-semibold font-sans border-[#E4E2DD]">
              &larr; Back to Clause Workbench
            </Button>
            <div className="flex items-center gap-3">
              {exportError && <span className="text-[#7A2A2A] font-sans text-[11px] font-bold uppercase">{exportError}</span>}
              {exportSuccess && <span className="text-[#155724] font-sans text-[11px] font-bold uppercase">{exportSuccess}</span>}
              <Button
                onClick={() => handleExport("docx")}
                disabled={isExporting !== null}
                className="h-8 bg-[#081534] text-white text-xs font-semibold font-sans hover:bg-[#1E2A4A]"
              >
                <Download className="h-3.5 w-3.5 mr-1.5" />
                {isExporting === "docx" ? "Exporting..." : "Export DOCX"}
              </Button>
              <Button
                onClick={() => handleExport("pdf")}
                disabled={isExporting !== null}
                className="h-8 bg-[#081534] text-white text-xs font-semibold font-sans hover:bg-[#1E2A4A]"
              >
                <Download className="h-3.5 w-3.5 mr-1.5" />
                {isExporting === "pdf" ? "Exporting..." : "Export PDF"}
              </Button>
            </div>
          </div>

          <div className="bg-white border border-[#E4E2DD] shadow-sm max-w-[850px] mx-auto min-h-[1100px] p-12 md:p-16">
            <div className="font-serif text-sm leading-[1.8] text-black max-w-[650px] mx-auto space-y-6">
              <div className="text-center font-bold text-xs uppercase tracking-widest text-[#76777F] border-b border-[#E4E2DD] pb-2">
                Draft Pleading &bull; Version {latestDraft.version_no}
              </div>

              {latestDraft.composed_sections.map((section, idx) => (
                <div key={idx} className="space-y-2">
                  <h5 className="font-bold text-xs uppercase tracking-wider text-[#081534] text-center pt-2">
                    {section.heading}
                  </h5>
                  <div className="whitespace-pre-wrap text-justify">
                    {section.text}
                  </div>
                  {section.bullet_items && section.bullet_items.length > 0 && (
                    <ul className="list-disc pl-6 space-y-1">
                      {section.bullet_items.map((b, bi) => (
                        <li key={bi}>{b}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
