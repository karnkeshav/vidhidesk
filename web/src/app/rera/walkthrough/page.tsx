"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { getReraStates, getReraProcedures, RERAWalkthroughProcedureOut } from "@/lib/api";
import { Loader2, ArrowRight, AlertTriangle, MapPin, FileText } from "lucide-react";

export default function ReraWalkthroughLanding() {
  const router = useRouter();

  const [states, setStates] = useState<string[]>([]);
  const [statesLoading, setStatesLoading] = useState(true);
  const [statesError, setStatesError] = useState<string | null>(null);

  const [selectedState, setSelectedState] = useState<string>("");

  const [procedures, setProcedures] = useState<RERAWalkthroughProcedureOut[]>([]);
  const [proceduresLoading, setProceduresLoading] = useState(false);
  const [proceduresError, setProceduresError] = useState<string | null>(null);

  const [selectedProcedure, setSelectedProcedure] = useState<string>("");

  useEffect(() => {
    let unmounted = false;
    const fetchStates = async () => {
      setStatesLoading(true);
      setStatesError(null);
      try {
        const data = await getReraStates();
        if (!unmounted) {
          setStates(data);
        }
      } catch (err: unknown) {
        if (!unmounted) {
          setStatesError((err instanceof Error ? err.message : 'Unknown error') || "Failed to load states.");
        }
      } finally {
        if (!unmounted) {
          setStatesLoading(false);
        }
      }
    };
    fetchStates();
    return () => {
      unmounted = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedState) {
      setProcedures([]);
      setSelectedProcedure("");
      return;
    }

    let unmounted = false;
    const fetchProcedures = async () => {
      setProceduresLoading(true);
      setProceduresError(null);
      try {
        const data = await getReraProcedures(selectedState);
        if (!unmounted) {
          setProcedures(data);
          setSelectedProcedure("");
        }
      } catch (err: unknown) {
        if (!unmounted) {
          setProceduresError((err instanceof Error ? err.message : 'Unknown error') || "Failed to load procedures.");
        }
      } finally {
        if (!unmounted) {
          setProceduresLoading(false);
        }
      }
    };
    fetchProcedures();
    return () => {
      unmounted = true;
    };
  }, [selectedState]);

  const handleStart = () => {
    if (selectedState && selectedProcedure) {
      router.push(`/rera/walkthrough/${selectedState}/${selectedProcedure}`);
    }
  };

  return (
    <AuthedShell>
      <div className="max-w-4xl mx-auto p-8 font-sans">
        <div className="mb-8 border-b border-[#E5E3DE] pb-6">
          <h1 className="text-3xl font-serif text-[#081534] mb-2">RERA Filing Walkthrough</h1>
          <p className="text-[#1A1A1A] max-w-2xl">
            Select a state and a corresponding procedure to begin the step-by-step walkthrough for RERA compliance.
          </p>
        </div>

        {statesLoading && (
          <div className="flex items-center justify-center p-12 text-[#081534]">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span className="ml-3 font-medium">Loading available states...</span>
          </div>
        )}

        {statesError && (
          <div className="p-4 bg-[#FBF9F5] border border-[#ba1a1a] rounded flex flex-col items-center justify-center mb-8">
            <AlertTriangle className="w-6 h-6 text-[#ba1a1a] mb-2" />
            <p className="text-[#ba1a1a] font-medium">{statesError}</p>
          </div>
        )}

        {!statesLoading && !statesError && states.length === 0 && (
          <div className="p-12 border border-[#E5E3DE] border-dashed rounded text-center text-[#1A1A1A] bg-[#FBF9F5]">
            <p>No RERA states found.</p>
          </div>
        )}

        {!statesLoading && !statesError && states.length > 0 && (
          <div className="space-y-8">
            <div className="bg-[#FBF9F5] border border-[#E5E3DE] rounded-lg p-6">
              <label className="block text-sm font-semibold text-[#081534] mb-3 flex items-center">
                <MapPin className="w-4 h-4 mr-2" />
                Select State
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {states.map((state) => (
                  <button
                    key={state}
                    onClick={() => setSelectedState(state)}
                    className={`px-4 py-3 border rounded text-left transition-colors flex items-center justify-between ${
                      selectedState === state
                        ? "bg-[#081534] border-[#081534] text-white"
                        : "bg-white border-[#E5E3DE] text-[#1A1A1A] hover:border-[#081534]"
                    }`}
                  >
                    <span className="font-medium truncate">{state}</span>
                  </button>
                ))}
              </div>
            </div>

            {selectedState && (
              <div className="bg-[#FBF9F5] border border-[#E5E3DE] rounded-lg p-6">
                <label className="block text-sm font-semibold text-[#081534] mb-3 flex items-center">
                  <FileText className="w-4 h-4 mr-2" />
                  Select Procedure
                </label>

                {proceduresLoading && (
                  <div className="flex items-center py-6 text-[#081534]">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="ml-3">Loading procedures for {selectedState}...</span>
                  </div>
                )}

                {proceduresError && (
                  <div className="p-4 border border-[#ba1a1a] rounded flex items-center text-[#ba1a1a] bg-white">
                    <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0" />
                    <p className="text-sm font-medium">{proceduresError}</p>
                  </div>
                )}

                {!proceduresLoading && !proceduresError && procedures.length === 0 && (
                  <div className="py-6 text-[#1A1A1A] italic">
                    No procedures available for this state.
                  </div>
                )}

                {!proceduresLoading && !proceduresError && procedures.length > 0 && (
                  <div className="grid gap-3">
                    {procedures.map((proc) => (
                      <button
                        key={proc.procedure}
                        onClick={() => setSelectedProcedure(proc.procedure)}
                        className={`p-4 border rounded text-left transition-colors flex flex-col sm:flex-row sm:items-center justify-between ${
                          selectedProcedure === proc.procedure
                            ? "bg-[#081534] border-[#081534] text-white"
                            : "bg-white border-[#E5E3DE] text-[#1A1A1A] hover:border-[#081534]"
                        }`}
                      >
                        <div className="flex flex-col">
                          <span className="font-medium">{proc.procedure}</span>
                          <span className={`text-sm mt-1 ${selectedProcedure === proc.procedure ? "text-gray-300" : "text-gray-500"}`}>
                            {proc.step_count} steps
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end pt-4">
              <button
                onClick={handleStart}
                disabled={!selectedState || !selectedProcedure}
                className={`flex items-center px-6 py-3 rounded font-medium transition-colors ${
                  selectedState && selectedProcedure
                    ? "bg-[#081534] text-white hover:bg-[#1A1A1A]"
                    : "bg-[#E5E3DE] text-gray-500 cursor-not-allowed"
                }`}
              >
                Start Walkthrough
                <ArrowRight className="w-4 h-4 ml-2" />
              </button>
            </div>
          </div>
        )}
      </div>
    </AuthedShell>
  );
}
