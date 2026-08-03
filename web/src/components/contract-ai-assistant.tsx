"use client";

import { useState } from "react";
import { Sparkles, AlertTriangle, ExternalLink, Send, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ContractAiAssistant({
  documentTitle = "Master Service Agreement v2.1",
  onApplyAmendment,
  busy = false,
}: {
  documentTitle?: string;
  onApplyAmendment?: (note: string) => void;
  busy?: boolean;
}) {
  const [prompt, setPrompt] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim() || busy) return;
    onApplyAmendment?.(prompt);
    setPrompt("");
  };

  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-64px)] w-[320px] shrink-0 flex-col border-l border-[#E4E2DD] bg-white lg:flex">
      {/* Header */}
      <div className="border-b border-[#E4E2DD] p-4">
        <div className="flex items-center gap-2 text-[#081534]">
          <Sparkles className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
          <h2 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
            AI Legal Assistant
          </h2>
        </div>
        <p className="font-serif text-[11px] text-[#76777F] truncate">
          Analyzing &quot;{documentTitle}&quot;
        </p>
      </div>

      {/* Main Analysis Content Scroll */}
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {/* Risk Analysis Card */}
        <div className="rounded-sm border border-[#FFDAD6] bg-[#FFF5F5] p-3">
          <div className="mb-1.5 flex items-center justify-between">
            <span className="flex items-center gap-1 font-sans text-[10px] font-bold uppercase tracking-wider text-[#7A2A2A]">
              <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.5} />
              Risk Analysis
            </span>
            <span className="rounded bg-[#BA1A1A] px-1.5 py-0.5 font-sans text-[9px] font-bold text-white">
              Critical
            </span>
          </div>
          <p className="font-serif text-xs leading-relaxed text-[#1A1A1A]">
            Section 2.1 (IP Assignment) lacks a &apos;Back-License&apos; for Background IP. This could result in loss of proprietary methodologies.
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onApplyAmendment?.("Add back-license for Background IP in Section 2.1")}
            className="mt-2.5 w-full rounded-sm border-[#7A2A2A] font-sans text-xs font-semibold text-[#7A2A2A] hover:bg-[#FFDAD6]/30"
          >
            Generate Clause
          </Button>
        </div>

        {/* Clause Suggestions Card */}
        <div className="rounded-sm border border-[#E4E2DD] p-3">
          <span className="mb-2 block font-sans text-[10px] font-bold uppercase tracking-wider text-[#081534]">
            Clause Suggestions
          </span>
          <div className="space-y-3">
            <div>
              <p className="font-sans text-xs font-semibold text-[#1A1A1A]">
                Force Majeure Enhancement
              </p>
              <p className="font-serif text-[11px] leading-relaxed text-[#45464E]">
                Add &quot;Epidemics and Pandemics&quot; to Section 5.4 for post-2020 standard compliance.
              </p>
              <button
                type="button"
                onClick={() => onApplyAmendment?.("Add epidemics and pandemics to Force Majeure clause")}
                className="mt-1 font-sans text-xs font-medium text-[#081534] hover:underline"
              >
                Insert Clause
              </button>
            </div>
            <div className="border-t border-[#E4E2DD] pt-2">
              <p className="font-sans text-xs font-semibold text-[#1A1A1A]">
                Arbitration Venue
              </p>
              <p className="font-serif text-[11px] leading-relaxed text-[#45464E]">
                Change seat to New Delhi under MCIA / High Court rules.
              </p>
              <button
                type="button"
                onClick={() => onApplyAmendment?.("Set arbitration seat to New Delhi")}
                className="mt-1 font-sans text-xs font-medium text-[#081534] hover:underline"
              >
                Modify Section 8.2
              </button>
            </div>
          </div>
        </div>

        {/* Citations & Acts Card */}
        <div className="space-y-2">
          <span className="block font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
            Citations & Statutory Grounding
          </span>
          <div className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
            <div className="flex items-center justify-between">
              <span className="font-sans text-xs font-semibold text-[#1A1A1A]">
                Indian Contract Act, 1872
              </span>
              <ExternalLink className="h-3 w-3 text-[#76777F]" />
            </div>
            <p className="font-serif text-[11px] text-[#45464E]">
              Section 27 (Agreement in restraint of trade).
            </p>
          </div>
          <div className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
            <div className="flex items-center justify-between">
              <span className="font-sans text-xs font-semibold text-[#1A1A1A]">
                Kanoon Doc Citation
              </span>
              <CheckCircle2 className="h-3 w-3 text-[#3D5A3D]" />
            </div>
            <p className="font-serif text-[11px] italic text-[#45464E]">
              ONGC v. Saw Pipes Ltd. (2003)
            </p>
            <p className="mt-0.5 font-serif text-[10px] text-[#76777F]">
              Governs liquidated damages clauses under Indian law.
            </p>
          </div>
        </div>
      </div>

      {/* Bottom Amendment Chat Input */}
      <form onSubmit={handleSubmit} className="border-t border-[#E4E2DD] p-3">
        <div className="relative">
          <Input
            type="text"
            placeholder="Ask AI or request amendment..."
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={busy}
            className="h-9 rounded-full border-[#E4E2DD] bg-[#F0EEE9] pr-9 font-sans text-xs text-[#1A1A1A] placeholder:text-[#9A9B9E] focus-visible:ring-1 focus-visible:ring-[#081534]"
          />
          <button
            type="submit"
            disabled={busy || !prompt.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-[#081534] disabled:opacity-40"
          >
            <Send className="h-4 w-4" strokeWidth={1.5} />
          </button>
        </div>
      </form>
    </aside>
  );
}
