"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { getReraWalkthrough, getReraProgress, updateReraProgress, RERAWalkthroughStepOut, RERAWalkthroughProgressOut } from "@/lib/api";
import { CheckCircle, AlertCircle, ArrowLeft, ArrowRight, RefreshCcw } from "lucide-react";
import Link from "next/link";

export default function ReraWalkthroughProcedurePage() {
  const params = useParams<{ state: string; procedure: string }>();
  const searchParams = useSearchParams();
  const matterId = searchParams.get("matter_id");
  
  const stateDecoded = decodeURIComponent(params.state);
  const procedureDecoded = decodeURIComponent(params.procedure);

  const [steps, setSteps] = useState<RERAWalkthroughStepOut[]>([]);
  const [progress, setProgress] = useState<RERAWalkthroughProgressOut | null>(null);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  // We derive current step index either from progress or local state (when transitioning)
  const [currentStepIndex, setCurrentStepIndex] = useState(0);

  useEffect(() => {
    async function init() {
      try {
        setLoading(true);
        const [stepsData, progressData] = await Promise.all([
          getReraWalkthrough(stateDecoded, procedureDecoded),
          getReraProgress(stateDecoded, procedureDecoded, matterId || undefined)
        ]);
        
        setSteps(stepsData.sort((a, b) => a.step_no - b.step_no));
        setProgress(progressData);
        if (progressData && progressData.current_step_no > 0) {
          const idx = stepsData.findIndex(s => s.step_no === progressData.current_step_no);
          setCurrentStepIndex(idx >= 0 ? idx : 0);
        }
      } catch (err: unknown) {
        setError((err instanceof Error ? err.message : 'Unknown error') || "Failed to load walkthrough");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, [stateDecoded, procedureDecoded, matterId]);

  async function handleCompleteStep(stepId: string, currentStepNo: number, isLast: boolean) {
    if (updating) return;
    try {
      setUpdating(true);
      const nextStepNo = isLast ? currentStepNo : steps[currentStepIndex + 1].step_no;
      
      const updated = await updateReraProgress(stateDecoded, procedureDecoded, {
        mark_step_complete_id: stepId,
        current_step_no: nextStepNo,
        matter_id: matterId || undefined
      });
      setProgress(updated);
      
      if (!isLast) {
        setCurrentStepIndex(currentStepIndex + 1);
      }
    } catch (err: unknown) {
      alert("Failed to save progress: " + (err instanceof Error ? err.message : 'Unknown error'));
    } finally {
      setUpdating(false);
    }
  }

  async function handlePrev() {
    if (currentStepIndex > 0) {
      try {
        setUpdating(true);
        const prevStepNo = steps[currentStepIndex - 1].step_no;
        const updated = await updateReraProgress(stateDecoded, procedureDecoded, {
          current_step_no: prevStepNo,
          matter_id: matterId || undefined
        });
        setProgress(updated);
        setCurrentStepIndex(currentStepIndex - 1);
      } catch (err: unknown) {
        alert("Failed to save progress: " + (err instanceof Error ? err.message : 'Unknown error'));
      } finally {
        setUpdating(false);
      }
    }
  }

  async function handleNext() {
    if (currentStepIndex < steps.length - 1) {
      try {
        setUpdating(true);
        const nextStepNo = steps[currentStepIndex + 1].step_no;
        const updated = await updateReraProgress(stateDecoded, procedureDecoded, {
          current_step_no: nextStepNo,
          matter_id: matterId || undefined
        });
        setProgress(updated);
        setCurrentStepIndex(currentStepIndex + 1);
      } catch (err: unknown) {
        alert("Failed to save progress: " + (err instanceof Error ? err.message : 'Unknown error'));
      } finally {
        setUpdating(false);
      }
    }
  }

  if (loading) {
    return (
      <AuthedShell wide>
        <div className="flex h-[80vh] items-center justify-center text-[#081534] font-sans">
          Loading Walkthrough...
        </div>
      </AuthedShell>
    );
  }

  if (error) {
    return (
      <AuthedShell wide>
        <div className="p-8 max-w-4xl mx-auto flex flex-col gap-4 text-[#081534] font-sans">
          <Link href="/rera/walkthrough" className="text-sm underline">← Back to states</Link>
          <div className="p-6 bg-[#ffdad6] text-[#93000a] rounded-sm border border-[#93000a]">
            <h2 className="font-bold mb-2">Error loading procedure</h2>
            <p>{error}</p>
          </div>
        </div>
      </AuthedShell>
    );
  }

  if (steps.length === 0) {
    return (
      <AuthedShell wide>
        <div className="p-8 max-w-4xl mx-auto flex flex-col gap-4 text-[#081534] font-sans">
          <Link href="/rera/walkthrough" className="text-sm underline flex items-center gap-2">
            <ArrowLeft className="h-4 w-4" /> Back to states
          </Link>
          <div className="flex flex-col items-center justify-center p-12 bg-white border border-[#E5E3DE] rounded-sm mt-8">
            <AlertCircle className="h-12 w-12 text-[#6B6B6B] mb-4" />
            <h2 className="text-lg font-semibold text-[#081534]">No steps available</h2>
            <p className="text-sm text-[#45464E] mt-2">There are no curated steps for {stateDecoded} - {procedureDecoded} yet.</p>
          </div>
        </div>
      </AuthedShell>
    );
  }

  const currentStep = steps[currentStepIndex];
  const isComplete = progress?.completed_step_ids?.includes(currentStep.id) || false;
  const isLast = currentStepIndex === steps.length - 1;

  return (
    <AuthedShell wide>
      <div className="max-w-4xl mx-auto pt-8 pb-24 px-4 font-sans text-[#1A1A1A]">
        
        <Link href="/rera/walkthrough" className="inline-flex items-center gap-2 text-sm text-[#45464E] hover:text-[#081534] mb-6 font-sans">
          <ArrowLeft className="h-4 w-4" /> Back to states
        </Link>
        
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-[#081534] mb-2 font-sans tracking-tight">
            {stateDecoded} RERA: {procedureDecoded.replace(/-/g, " ")}
          </h1>
          <p className="text-sm text-[#45464E] font-serif">
            Step {currentStepIndex + 1} of {steps.length}
          </p>
          
          <div className="flex w-full h-1 bg-[#E4E2DD] rounded-sm mt-4 overflow-hidden">
            <div 
              className="h-full bg-[#081534] transition-all duration-300"
              style={{ width: `${((currentStepIndex) / Math.max(1, steps.length - 1)) * 100}%` }}
            />
          </div>
        </div>

        <div className="bg-white border border-[#E5E3DE] rounded-sm p-6 md:p-10 shadow-sm relative">
          
          {progress?.is_complete && (
            <div className="absolute top-0 left-0 right-0 p-3 bg-[#E4E2DE] text-[#3D5A3D] text-sm font-semibold flex items-center justify-center gap-2 rounded-t-sm">
              <CheckCircle className="h-4 w-4" /> This walkthrough is fully completed.
            </div>
          )}
          
          <div className={progress?.is_complete ? "mt-8" : ""}>
            <div className="flex items-center justify-between mb-6 border-b border-[#E5E3DE] pb-4">
              <h2 className="text-xl font-semibold text-[#081534] font-sans">
                {currentStep.step_no}. {currentStep.heading}
              </h2>
              {isComplete && (
                <span className="flex items-center gap-1.5 text-xs font-semibold text-[#3D5A3D] bg-[#F6F3EE] px-2.5 py-1 rounded-sm">
                  <CheckCircle className="h-3.5 w-3.5" /> Completed
                </span>
              )}
            </div>

            <div className="space-y-6 font-serif">
              {currentStep.warnings && currentStep.warnings.length > 0 && (
                <div className="p-4 bg-[#F0EEE9] border-l-2 border-[#7A2A2A] rounded-r-sm text-sm text-[#45464E]">
                  <h4 className="font-semibold text-[#1A1A1A] font-sans text-xs uppercase tracking-wider mb-2">Important Warnings</h4>
                  <ul className="list-disc pl-5 space-y-1">
                    {currentStep.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {currentStep.required_documents && currentStep.required_documents.length > 0 && (
                <div>
                  <h4 className="font-semibold text-[#1A1A1A] font-sans text-xs uppercase tracking-wider mb-2">Required Documents</h4>
                  <ul className="list-disc pl-5 space-y-1 text-[#45464E]">
                    {currentStep.required_documents.map((doc, i) => (
                      <li key={i}>{doc}</li>
                    ))}
                  </ul>
                </div>
              )}

              {currentStep.portal_url && (
                <div>
                  <h4 className="font-semibold text-[#1A1A1A] font-sans text-xs uppercase tracking-wider mb-2">Portal Link</h4>
                  <a href={currentStep.portal_url} target="_blank" rel="noreferrer" className="text-[#081534] underline font-sans text-sm">
                    {currentStep.portal_url}
                  </a>
                </div>
              )}
              
              <div className="pt-4 mt-8 border-t border-[#E5E3DE] flex items-center justify-between">
                <Button 
                  variant="outline" 
                  onClick={handlePrev} 
                  disabled={currentStepIndex === 0 || updating}
                  className="font-sans text-[#081534] border-[#E5E3DE]"
                >
                  <ArrowLeft className="mr-2 h-4 w-4" /> Previous
                </Button>
                
                <div className="flex items-center gap-3">
                  {!isComplete && (
                    <Button 
                      onClick={() => handleCompleteStep(currentStep.id, currentStep.step_no, isLast)} 
                      disabled={updating}
                      className="bg-[#081534] text-white hover:bg-[#1E2A4A] font-sans"
                    >
                      {updating ? <RefreshCcw className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle className="mr-2 h-4 w-4" />}
                      {isLast ? "Complete Final Step" : "Mark Complete & Continue"}
                    </Button>
                  )}
                  {isComplete && !isLast && (
                    <Button 
                      onClick={handleNext} 
                      disabled={updating}
                      className="bg-[#081534] text-white hover:bg-[#1E2A4A] font-sans"
                    >
                      Next Step <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AuthedShell>
  );
}
