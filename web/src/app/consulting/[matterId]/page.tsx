"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { createConsultingAnalysis, listConsultingAnalyses, ConsultingAnalysisOut } from "@/lib/api";
import { Loader2, AlertTriangle, Scale, HelpCircle, AlertCircle, FileText, ChevronRight, Clock } from "lucide-react";

export default function ConsultingMatterPage() {
  const params = useParams();
  const matterId = params.matterId as string;

  const [analyses, setAnalyses] = useState<ConsultingAnalysisOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [followUpQuestion, setFollowUpQuestion] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const fetchAnalyses = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await listConsultingAnalyses(matterId);
      // Sort ascending by version_no
      const sorted = data.sort((a, b) => a.version_no - b.version_no);
      setAnalyses(sorted);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load consulting analyses.");
    } finally {
      setIsLoading(false);
    }
  }, [matterId]);

  useEffect(() => {
    if (matterId) {
      fetchAnalyses();
    }
  }, [matterId, fetchAnalyses]);

  const handleFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!followUpQuestion.trim()) return;

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await createConsultingAnalysis({
        matter_id: matterId,
        question: followUpQuestion,
      });
      setFollowUpQuestion("");
      await fetchAnalyses();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to submit follow-up question.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthedShell wide>
      <div className="flex flex-col h-[calc(100vh-64px)]">
        {/* Scrollable Content Area */}
        <div className="flex-1 overflow-y-auto bg-[#FBF9F4] p-4 sm:p-6 lg:p-8 pb-32">
          <div className="max-w-4xl mx-auto space-y-10">
            <div>
              <h1 className="font-sans text-2xl font-semibold text-[#081534]">Consulting Analysis</h1>
              <p className="font-serif text-sm text-[#45464E] mt-1">Matter ID: {matterId}</p>
            </div>

            {isLoading ? (
              <div className="flex justify-center p-12">
                <Loader2 className="h-8 w-8 animate-spin text-[#081534]" />
              </div>
            ) : error ? (
              <div className="p-4 bg-[#FCE8E8] border border-[#7A2A2A] rounded-sm text-[#7A2A2A] font-sans text-sm flex items-start">
                <AlertCircle className="h-5 w-5 mr-2 shrink-0" />
                <span>{error}</span>
              </div>
            ) : analyses.length === 0 ? (
              <div className="text-center p-12 bg-white border border-[#E4E2DD] rounded-sm">
                <p className="font-sans text-sm text-[#45464E]">No analysis versions found for this matter.</p>
              </div>
            ) : (
              <div className="space-y-8 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-[#E4E2DD] before:to-transparent">
                {analyses.map((analysis, index) => (
                  <div key={analysis.id} className="relative flex items-start flex-col md:flex-row gap-6 md:gap-8 group">
                    <div className="flex items-center justify-center w-10 h-10 rounded-full border-4 border-[#FBF9F4] bg-[#081534] text-white font-sans text-sm font-bold shadow-sm z-10 md:mx-auto shrink-0 transition-transform group-hover:scale-110">
                      v{analysis.version_no}
                    </div>

                    <div className={`w-full md:w-[calc(50%-2.5rem)] bg-white border border-[#E4E2DD] rounded-sm shadow-sm p-6 ${index % 2 === 0 ? 'md:ml-auto md:text-left' : 'md:mr-auto md:text-left'}`}>
                      <div className="mb-4 pb-4 border-b border-[#E4E2DD]">
                        <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-2 flex items-center">
                          <HelpCircle className="h-4 w-4 mr-1.5" />
                          Question
                        </h3>
                        <p className="font-serif text-sm text-[#081534] leading-relaxed">
                          {analysis.question}
                        </p>
                      </div>

                      <div className="space-y-6">
                        {/* Applicable Law */}
                        {analysis.applicable_law && analysis.applicable_law.length > 0 && (
                          <div>
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-3 flex items-center">
                              <Scale className="h-4 w-4 mr-1.5" />
                              Applicable Law
                            </h3>
                            <ul className="space-y-3">
                              {analysis.applicable_law.map((law, i) => (
                                <li key={i} className="bg-[#FBF9F4] p-3 border border-[#E4E2DD] rounded-sm text-sm">
                                  <div className="flex items-start justify-between gap-2 mb-1">
                                    <span className="font-sans font-semibold text-[#081534]">
                                      {law.act}, {law.section_no}
                                    </span>
                                    {!law.grounded && (
                                      <span className="inline-flex items-center px-1.5 py-0.5 rounded-xs text-[10px] font-bold bg-[#FCE8E8] text-[#7A2A2A] whitespace-nowrap">
                                        <AlertTriangle className="h-3 w-3 mr-1" />
                                        Not Grounded
                                      </span>
                                    )}
                                  </div>
                                  <p className="font-serif text-xs text-[#45464E]">{law.relevance}</p>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Correct Forum */}
                        {analysis.correct_forum && (
                          <div>
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-3 flex items-center">
                              <Scale className="h-4 w-4 mr-1.5" />
                              Correct Forum
                            </h3>
                            <div className="bg-[#FBF9F4] p-3 border border-[#E4E2DD] rounded-sm text-sm">
                              <div className="flex items-center justify-between mb-1">
                                <span className="font-sans font-semibold text-[#081534]">{analysis.correct_forum.forum_name}</span>
                                {!analysis.correct_forum.deterministic && (
                                  <span className="inline-flex items-center text-[#7A2A2A] text-xs" title="Determination is not definitive.">
                                    <AlertTriangle className="h-3.5 w-3.5 mr-1" />
                                    Warning
                                  </span>
                                )}
                              </div>
                              <p className="font-serif text-xs text-[#45464E] mb-1">{analysis.correct_forum.reasoning}</p>
                              {analysis.correct_forum.source && (
                                <p className="font-sans text-[10px] text-[#73737C]">Source: {analysis.correct_forum.source}</p>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Remedies Available */}
                        {analysis.remedies_available && analysis.remedies_available.length > 0 && (
                          <div>
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-3 flex items-center">
                              <FileText className="h-4 w-4 mr-1.5" />
                              Remedies Available
                            </h3>
                            <ul className="list-disc pl-5 space-y-2">
                              {analysis.remedies_available.map((rem, i) => (
                                <li key={i} className="font-serif text-sm text-[#45464E] marker:text-[#081534]">
                                  <strong className="font-sans text-[#081534] block mb-0.5">{rem.remedy}</strong>
                                  <span className="text-xs">{rem.description}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Limitation Period */}
                        {analysis.limitation_period && (
                          <div>
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-3 flex items-center">
                              <Clock className="h-4 w-4 mr-1.5" />
                              Limitation Period
                            </h3>
                            <div className="bg-[#FBF9F4] p-3 border border-[#E4E2DD] rounded-sm text-sm">
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <p className="font-serif text-xs text-[#45464E]">{analysis.limitation_period.summary}</p>
                                {!analysis.limitation_period.deterministic && (
                                  <span className="inline-flex items-center px-1.5 py-0.5 rounded-xs text-[10px] font-bold bg-[#FFF4E5] text-[#9A6A00] whitespace-nowrap">
                                    <AlertTriangle className="h-3 w-3 mr-1" />
                                    Estimate
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap gap-2 font-sans text-[10px]">
                                {analysis.limitation_period.expiry_date && (
                                  <span className="bg-white border border-[#E4E2DD] px-2 py-1 rounded-sm text-[#081534]">
                                    Expiry: {analysis.limitation_period.expiry_date}
                                  </span>
                                )}
                                {analysis.limitation_period.is_barred !== null && (
                                  <span className={`border px-2 py-1 rounded-sm ${analysis.limitation_period.is_barred ? 'bg-[#FCE8E8] border-[#7A2A2A] text-[#7A2A2A]' : 'bg-[#E8F5E9] border-[#155724] text-[#155724]'}`}>
                                    {analysis.limitation_period.is_barred ? 'Time-Barred' : 'Within Time'}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Missing Information */}
                        {analysis.missing_information && analysis.missing_information.length > 0 && (
                          <div>
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-3 flex items-center">
                              <AlertCircle className="h-4 w-4 mr-1.5" />
                              Missing Information
                            </h3>
                            <ul className="list-disc pl-5 space-y-1">
                              {analysis.missing_information.map((info, i) => (
                                <li key={i} className="font-serif text-xs text-[#7A2A2A] marker:text-[#7A2A2A]">
                                  {info}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Case Law References */}
                        {analysis.case_law_references && analysis.case_law_references.length > 0 && (
                          <div className="pt-4 border-t border-[#E4E2DD]">
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E] mb-3 flex items-center">
                              <FileText className="h-4 w-4 mr-1.5" />
                              Case Law References
                            </h3>
                            <ul className="space-y-3">
                              {analysis.case_law_references.map((caseLaw, i) => {
                                const isVerified = caseLaw.status === "verified";
                                
                                return (
                                  <li key={i} className={`p-3 border rounded-sm text-sm ${isVerified ? 'bg-[#F0F4F8] border-[#B8CDE0]' : 'bg-[#F9F9F9] border-[#E4E2DD]'}`}>
                                    <div className="flex items-start justify-between gap-2 mb-1">
                                      {isVerified && caseLaw.ik_url ? (
                                        <a href={caseLaw.ik_url} target="_blank" rel="noopener noreferrer" className="font-sans font-semibold text-[#0056B3] hover:underline flex items-center gap-1">
                                          {caseLaw.case_name}
                                          <ChevronRight className="h-3 w-3" />
                                        </a>
                                      ) : (
                                        <span className="font-sans font-semibold text-[#73737C] flex items-center gap-1 cursor-help" title="Unverified — confirm manually (may exist only on SCC/Manupatra)">
                                          {caseLaw.case_name}
                                          <AlertTriangle className="h-3.5 w-3.5 text-[#7A2A2A]" />
                                        </span>
                                      )}
                                    </div>
                                    {caseLaw.court && (
                                      <p className="font-sans text-[10px] text-[#45464E] mb-1">{caseLaw.court}</p>
                                    )}
                                    <p className="font-serif text-xs text-[#45464E]">{caseLaw.note}</p>
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        )}

                        <div className="pt-4 border-t border-[#E4E2DD] flex justify-between items-center">
                          <span className="font-sans text-[10px] text-[#73737C]">Model: {analysis.model_used}</span>
                          <span className="font-sans text-[10px] text-[#73737C]">{new Date(analysis.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sticky Follow-up Section */}
        <div className="border-t border-[#E4E2DD] bg-white p-4 sm:p-6 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] shrink-0 z-20">
          <div className="max-w-4xl mx-auto">
            <form onSubmit={handleFollowUp} className="flex gap-4">
              <div className="flex-1 relative">
                <textarea
                  rows={2}
                  value={followUpQuestion}
                  onChange={(e) => setFollowUpQuestion(e.target.value)}
                  placeholder="Ask a follow-up question to refine the analysis..."
                  className="w-full bg-[#FBF9F4] border border-[#E4E2DD] rounded-sm py-2 px-3 font-serif text-sm focus:outline-none focus:border-[#081534] resize-none"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleFollowUp(e);
                    }
                  }}
                />
                {submitError && (
                  <p className="absolute -top-6 left-0 text-[10px] text-[#7A2A2A] bg-[#FCE8E8] px-2 py-0.5 rounded-sm border border-[#7A2A2A]">
                    {submitError}
                  </p>
                )}
              </div>
              <Button 
                type="submit" 
                disabled={isSubmitting || !followUpQuestion.trim()} 
                className="bg-[#081534] text-white font-sans text-sm font-semibold hover:bg-[#1E2A4A] px-6 h-auto self-stretch"
              >
                {isSubmitting ? (
                  <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                  "Ask Follow-up"
                )}
              </Button>
            </form>
          </div>
        </div>
      </div>
    </AuthedShell>
  );
}
