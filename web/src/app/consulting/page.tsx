"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell, useMatters } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { createConsultingAnalysis } from "@/lib/api";
import { MessageSquare, Loader2, Calendar, User } from "lucide-react";

export default function ConsultingPage() {
  const router = useRouter();
  const { matters, error: mattersError } = useMatters();

  const [question, setQuestion] = useState("");
  const [partyNames, setPartyNames] = useState("");
  const [addresses, setAddresses] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const consultingMatters = useMemo(() => {
    return (matters || []).filter((m) => m.module === "consulting").sort((a, b) => 
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
  }, [matters]);

  const handleCreateAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const party_names = partyNames.split(",").map(s => s.trim()).filter(Boolean);
      const addressesList = addresses.split(",").map(s => s.trim()).filter(Boolean);

      const result = await createConsultingAnalysis({
        question,
        party_names: party_names.length > 0 ? party_names : undefined,
        addresses: addressesList.length > 0 ? addressesList : undefined,
      });

      router.push(`/consulting/${result.matter_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create consulting analysis.");
      setIsSubmitting(false);
    }
  };

  return (
    <AuthedShell wide>
      <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-12">
        <section>
          <div className="mb-6">
            <h1 className="font-sans text-2xl font-semibold text-[#081534]">Consulting Hub</h1>
            <p className="font-serif text-sm text-[#45464E] mt-1">
              Ask a new legal question and instantly receive an initial legal analysis, relevant sections, and case law references.
            </p>
          </div>

          <form onSubmit={handleCreateAnalysis} className="bg-white border border-[#E4E2DD] rounded-sm p-6 shadow-sm space-y-6">
            <div>
              <label className="block font-sans text-sm font-semibold text-[#081534] mb-2">
                Ask a new legal question *
              </label>
              <textarea
                required
                rows={5}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Describe the legal scenario or question in detail..."
                className="w-full bg-[#FBF9F4] border border-[#E4E2DD] rounded-sm p-3 font-serif text-sm focus:outline-none focus:border-[#081534]"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block font-sans text-xs font-semibold text-[#081534] mb-1">
                  Party Names to Mask (Optional)
                </label>
                <input
                  type="text"
                  value={partyNames}
                  onChange={(e) => setPartyNames(e.target.value)}
                  placeholder="e.g. John Doe, Acme Corp"
                  className="w-full bg-[#FBF9F4] border border-[#E4E2DD] rounded-sm px-3 py-2 font-sans text-xs focus:outline-none focus:border-[#081534]"
                />
                <p className="text-[10px] text-[#45464E] mt-1">Comma separated</p>
              </div>
              <div>
                <label className="block font-sans text-xs font-semibold text-[#081534] mb-1">
                  Addresses to Mask (Optional)
                </label>
                <input
                  type="text"
                  value={addresses}
                  onChange={(e) => setAddresses(e.target.value)}
                  placeholder="e.g. 123 Main St, Mumbai"
                  className="w-full bg-[#FBF9F4] border border-[#E4E2DD] rounded-sm px-3 py-2 font-sans text-xs focus:outline-none focus:border-[#081534]"
                />
                <p className="text-[10px] text-[#45464E] mt-1">Comma separated</p>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-[#FCE8E8] border border-[#7A2A2A] rounded-sm text-[#7A2A2A] font-sans text-xs">
                {error}
              </div>
            )}

            <div className="flex justify-end pt-2 border-t border-[#E4E2DD]">
              <Button 
                type="submit" 
                disabled={isSubmitting || !question.trim()} 
                className="bg-[#081534] text-white font-sans text-sm font-semibold hover:bg-[#1E2A4A] h-10 px-6"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  "Analyze & Create Matter"
                )}
              </Button>
            </div>
          </form>
        </section>

        <section>
          <h2 className="font-sans text-lg font-semibold text-[#081534] mb-4 border-b border-[#E4E2DD] pb-2">
            Recent Consultations
          </h2>

          {mattersError ? (
            <div className="p-4 bg-white border border-[#E4E2DD] rounded-sm text-[#7A2A2A] font-sans text-sm">
              Failed to load recent matters.
            </div>
          ) : !matters ? (
            <div className="flex justify-center p-8">
              <Loader2 className="h-6 w-6 animate-spin text-[#081534]" />
            </div>
          ) : consultingMatters.length === 0 ? (
            <div className="p-8 bg-white border border-[#E4E2DD] rounded-sm text-center">
              <MessageSquare className="h-8 w-8 text-[#C6C6CF] mx-auto mb-3" />
              <p className="font-sans text-sm text-[#45464E]">No consulting matters found.</p>
              <p className="font-serif text-xs text-[#73737C] mt-1">Ask a new legal question above to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {consultingMatters.map((m) => (
                <a 
                  key={m.id} 
                  href={`/consulting/${m.id}`} 
                  className="block bg-white rounded-sm border border-[#E4E2DD] p-5 hover:border-[#081534] transition-colors shadow-sm group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-sans text-sm font-semibold text-[#081534] line-clamp-2 group-hover:underline">
                      {m.title}
                    </h3>
                  </div>
                  <div className="space-y-2 mt-4 pt-4 border-t border-[#E4E2DD]">
                    {m.client_name && (
                      <div className="flex items-center text-[#45464E]">
                        <User className="h-3.5 w-3.5 mr-2 shrink-0" />
                        <span className="font-serif text-xs truncate">{m.client_name}</span>
                      </div>
                    )}
                    <div className="flex items-center text-[#45464E]">
                      <Calendar className="h-3.5 w-3.5 mr-2 shrink-0" />
                      <span className="font-serif text-xs">
                        {new Date(m.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </a>
              ))}
            </div>
          )}
        </section>
      </div>
    </AuthedShell>
  );
}
