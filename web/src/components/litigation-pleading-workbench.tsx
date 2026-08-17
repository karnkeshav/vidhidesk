"use client";

import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  PleadingOutline,
  PleadingClause,
  PleadingDraft,
  CaseAnalysis,
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
  CheckCircle,
  Eye,
  Download,
  AlertCircle,
  Sparkles
} from "lucide-react";
import { cn } from "@/lib/utils";

interface PleadingWorkbenchProps {
  matterId: string;
  latestCaseAnalysis: CaseAnalysis | null;
}

const CLAUSE_TYPES = [
  "TITLE_AND_JURISDICTION",
  "PARTIES_DESCRIPTION",
  "FACTS_CHRONOLOGY",
  "CAUSE_OF_ACTION",
  "LIMITATION_AND_DELAY",
  "JURISDICTION_AND_FORUM",
  "EVIDENCE_SUMMARY",
  "LEGAL_GROUNDS",
  "PRAYER_FOR_RELIEF",
  "VERIFICATION",
  "AFFIDAVIT"
];

export function LitigationPleadingWorkbench({ matterId, latestCaseAnalysis }: PleadingWorkbenchProps) {
  const [outline, setOutline] = useState<PleadingOutline | null>(null);
  const [clauses, setClauses] = useState<PleadingClause[]>([]);
  const [drafts, setDrafts] = useState<PleadingDraft[]>([]);
  const [isGeneratingOutline, setIsGeneratingOutline] = useState(false);
  const [isGeneratingClause, setIsGeneratingClause] = useState<string | null>(null);
  const [isComposing, setIsComposing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState(false);
  
  // Export states
  const [isExporting, setIsExporting] = useState<"docx" | "pdf" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportSuccess, setExportSuccess] = useState<string | null>(null);

  // 1: Outline, 2: Clauses/Review, 3: Preview/Export
  const [workflowStage, setWorkflowStage] = useState(1);

  async function loadData() {
    try {
      const outlines = await listPleadingOutlines(matterId);
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
      console.error(err);
    }
  }

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId]);

  async function handleGenerateOutline() {
    if (!latestCaseAnalysis) {
      setError("A Case Analysis is required before generating a pleading outline.");
      return;
    }
    setIsGeneratingOutline(true);
    setError(null);
    try {
      const out = await generatePleadingOutline(matterId, { case_analysis_id: latestCaseAnalysis.id });
      setOutline(out);
      setWorkflowStage(2);
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

  async function handleReviewClause(clauseId: string, status: "Approved" | "Rejected") {
    try {
      const cl = await reviewPleadingClause(matterId, clauseId, status);
      setClauses(prev => prev.map(c => c.id === clauseId ? cl : c));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
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
      setExportError(err instanceof Error ? err.message : "Failed to export document");
    } finally {
      setIsExporting(null);
    }
  }

  const latestDraft = drafts[0];
  const allApproved = clauses.length > 0 && clauses.every(c => c.review_status === "Approved") && CLAUSE_TYPES.every(ct => clauses.some(c => c.clause_type === ct && c.review_status === "Approved"));

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]">
          {error}
        </div>
      )}

      {/* Workflow Progress Tracker */}
      <div className="flex items-center gap-2 mb-6 border-b border-[#E4E2DD] pb-4">
        <div className={cn("flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase", workflowStage >= 1 ? "text-[#081534]" : "text-[#76777F]")}>
          <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-white", workflowStage >= 1 ? "bg-[#081534]" : "bg-[#C6C6CF]")}>1</div>
          Outline
        </div>
        <div className="flex-1 h-px bg-[#E4E2DD]"></div>
        <div className={cn("flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase", workflowStage >= 2 ? "text-[#081534]" : "text-[#76777F]")}>
          <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-white", workflowStage >= 2 ? "bg-[#081534]" : "bg-[#C6C6CF]")}>2</div>
          Clause Generation & Review
        </div>
        <div className="flex-1 h-px bg-[#E4E2DD]"></div>
        <div className={cn("flex items-center gap-1.5 font-sans text-[11px] font-bold uppercase", workflowStage >= 3 ? "text-[#081534]" : "text-[#76777F]")}>
          <div className={cn("h-5 w-5 rounded-full flex items-center justify-center text-white", workflowStage >= 3 ? "bg-[#081534]" : "bg-[#C6C6CF]")}>3</div>
          Compose & Export
        </div>
      </div>

      {workflowStage === 1 && (
        <div className="rounded-sm border border-[#E4E2DD] bg-white p-6 flex flex-col items-center justify-center text-center space-y-4 min-h-[300px]">
          <div className="h-12 w-12 rounded-full bg-[#F0EEE9] flex items-center justify-center text-[#081534]">
            <Layers className="h-6 w-6" />
          </div>
          <div>
            <h3 className="font-sans text-lg font-semibold text-[#081534]">Generate Pleading Outline</h3>
            <p className="font-serif text-sm text-[#45464E] max-w-md mx-auto mt-2">
              Transform the AI Case Analysis into a structured pleading plan. This establishes the logical flow before any drafting begins.
            </p>
          </div>
          <Button
            onClick={handleGenerateOutline}
            disabled={isGeneratingOutline || !latestCaseAnalysis}
            className="bg-[#081534] text-white font-sans text-xs font-semibold hover:bg-[#1E2A4A] h-9 px-6"
          >
            {isGeneratingOutline ? "Structuring Plan..." : "Generate Outline"}
          </Button>
          {!latestCaseAnalysis && (
            <p className="text-[#7A2A2A] font-sans text-xs">Run an AI Case Analysis first.</p>
          )}
        </div>
      )}

      {workflowStage >= 2 && !previewMode && (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
          <div className="md:col-span-8 space-y-4">
            {/* Document Action Bar */}
            <div className="flex items-center justify-between rounded-sm border border-[#E4E2DD] bg-white p-3 shadow-sm">
              <div className="flex gap-2">
                <Button onClick={handleCompose} disabled={isComposing || !allApproved} variant="outline" className="h-8 text-xs font-semibold font-sans border-[#E4E2DD] text-[#081534] hover:bg-[#F0EEE9]">
                  <FileText className="h-3.5 w-3.5 mr-1.5" />
                  {isComposing ? "Composing..." : "Compose Document"}
                </Button>
                {drafts.length > 0 && (
                  <Button onClick={() => setPreviewMode(true)} variant="outline" className="h-8 text-xs font-semibold font-sans border-[#E4E2DD] text-[#081534] hover:bg-[#F0EEE9]">
                    <Eye className="h-3.5 w-3.5 mr-1.5" />
                    Preview Document
                  </Button>
                )}
              </div>
              <div className="flex items-center gap-3">
                {exportError && <span className="text-[#7A2A2A] font-sans text-[11px] font-bold uppercase">{exportError}</span>}
                {exportSuccess && <span className="text-[#155724] font-sans text-[11px] font-bold uppercase">{exportSuccess}</span>}
                {!exportError && !exportSuccess && (
                  latestDraft ? (
                    <span className="flex items-center gap-1 text-[#155724] font-sans text-[11px] font-bold uppercase">
                      <CheckCircle className="h-3.5 w-3.5"/> Ready for Export
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[#76777F] font-sans text-[11px] font-bold uppercase">
                      Drafting in Progress
                    </span>
                  )
                )}
                <Button 
                  onClick={() => handleExport("docx")} 
                  disabled={!latestDraft || isExporting !== null} 
                  className="h-8 bg-[#081534] text-white text-xs font-semibold font-sans hover:bg-[#1E2A4A]"
                >
                  <Download className="h-3.5 w-3.5 mr-1.5" />
                  {isExporting === "docx" ? "Exporting..." : "Export"}
                </Button>
              </div>
            </div>

            {/* Clauses List */}
            <div className="space-y-3">
              {CLAUSE_TYPES.map(type => {
                const clause = clauses.find(c => c.clause_type === type);
                const isGenerating = isGeneratingClause === type;
                
                return (
                  <div key={type} className="rounded-sm border border-[#E4E2DD] bg-white overflow-hidden">
                    <div className="bg-[#FBF9F4] border-b border-[#E4E2DD] p-3 flex items-center justify-between">
                      <h4 className="font-sans text-xs font-semibold uppercase text-[#081534] tracking-wide">{type.replace(/_/g, ' ')}</h4>
                      {!clause && (
                        <Button
                          onClick={() => handleGenerateClause(type)}
                          disabled={isGenerating}
                          variant="outline"
                          className="h-7 text-[10px] font-sans bg-white"
                        >
                          {isGenerating ? <Sparkles className="h-3 w-3 mr-1 animate-pulse" /> : <Sparkles className="h-3 w-3 mr-1" />}
                          {isGenerating ? "Drafting..." : "Generate AI Draft"}
                        </Button>
                      )}
                    </div>
                    {clause && (
                      <div className="p-4 space-y-4">
                        <div className="font-serif text-sm leading-relaxed text-[#1A1A1A] whitespace-pre-wrap">
                          {clause.content}
                        </div>
                        <div className="flex items-center justify-between pt-3 border-t border-[#E4E2DD]">
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              "px-2 py-0.5 rounded-xs font-sans text-[10px] font-bold uppercase border",
                              clause.review_status === "Needs Review" ? "bg-[#FFF3CD] text-[#856404] border-[#FFEEBA]" :
                              clause.review_status === "Approved" ? "bg-[#D4EDDA] text-[#155724] border-[#C3E6CB]" :
                              "bg-[#FFF5F5] text-[#7A2A2A] border-[#F8D7DA]"
                            )}>
                              {clause.review_status}
                            </span>
                            <span className="text-[#76777F] font-sans text-[10px]">v{clause.version_no}</span>
                          </div>
                          {clause.review_status === "Needs Review" && (
                            <div className="flex gap-2">
                              <Button onClick={() => handleReviewClause(clause.id, "Rejected")} variant="outline" className="h-7 text-xs text-[#7A2A2A] hover:bg-[#FFF5F5]">Reject</Button>
                              <Button onClick={() => handleReviewClause(clause.id, "Approved")} className="h-7 text-xs bg-[#081534] text-white hover:bg-[#1E2A4A]">Approve</Button>
                            </div>
                          )}
                          {clause.review_status === "Approved" && (
                            <Button onClick={() => handleReviewClause(clause.id, "Rejected")} variant="outline" className="h-7 text-xs">Revoke Approval</Button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
          
          <div className="md:col-span-4 space-y-4">
            <div className="rounded-sm border border-[#E4E2DD] bg-white p-4">
              <h4 className="font-sans text-xs font-semibold uppercase text-[#081534] tracking-wide mb-3 flex items-center gap-1.5 border-b border-[#E4E2DD] pb-2">
                <AlertCircle className="h-4 w-4" />
                AI Review Panel
              </h4>
              <p className="font-serif text-xs text-[#45464E] leading-relaxed mb-4">
                The Advocate remains the final authority. All generated clauses must be reviewed and approved before document composition.
              </p>
              
              <div className="space-y-2 font-sans text-xs">
                <div className="flex justify-between items-center py-1">
                  <span className="text-[#45464E]">Total Sections</span>
                  <span className="font-semibold text-[#081534]">{CLAUSE_TYPES.length}</span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <span className="text-[#45464E]">Drafted</span>
                  <span className="font-semibold text-[#081534]">{clauses.length}</span>
                </div>
                <div className="flex justify-between items-center py-1 text-[#155724]">
                  <span>Approved</span>
                  <span className="font-semibold">{clauses.filter(c => c.review_status === "Approved").length}</span>
                </div>
                <div className="flex justify-between items-center py-1 text-[#856404]">
                  <span>Needs Review</span>
                  <span className="font-semibold">{clauses.filter(c => c.review_status === "Needs Review").length}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {previewMode && latestDraft && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-sm border border-[#E4E2DD] bg-white p-3 shadow-sm">
            <Button onClick={() => setPreviewMode(false)} variant="outline" className="h-8 text-xs font-semibold font-sans">
              &larr; Back to Workbench
            </Button>
            <div className="flex items-center gap-3">
              {exportError && <span className="text-[#7A2A2A] font-sans text-[11px] font-bold uppercase">{exportError}</span>}
              {exportSuccess && <span className="text-[#155724] font-sans text-[11px] font-bold uppercase">{exportSuccess}</span>}
              {!exportError && !exportSuccess && (
                <span className="flex items-center gap-1 text-[#155724] font-sans text-[11px] font-bold uppercase">
                  <CheckCircle className="h-3.5 w-3.5"/> Ready for Export
                </span>
              )}
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

          <div className="bg-white border border-[#E4E2DD] shadow-sm max-w-[850px] mx-auto min-h-[1100px] p-12 md:p-20">
            <div className="font-serif text-sm leading-[1.7] text-black max-w-[650px] mx-auto text-justify space-y-6">
              {latestDraft.composed_sections.map((section, idx) => (
                <div key={idx}>
                  <h5 className="font-bold mb-2 uppercase text-center">{section.heading}</h5>
                  <p className="whitespace-pre-wrap">{section.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
