"use client";

import { AuthedShell, useMatters } from "@/components/authed-shell";
import { Gavel } from "lucide-react";

export default function LitigationPage() {
  const { matters, error } = useMatters();
  const litigationMatters = matters.filter((m) => m.module === "litigation");

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        <div>
          <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534]">
            Litigation Workspace
          </h1>
          <p className="font-serif text-sm text-[#45464E]">
            Track court dates, evidentiary logs, and ongoing filings across your litigation matters.
          </p>
        </div>

        {error && (
          <div
            role="alert"
            className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]"
          >
            {error}
          </div>
        )}

        <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none">
          <p className="mb-3 font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
            Active Litigation Matters ({litigationMatters.length})
          </p>
          {litigationMatters.length === 0 ? (
            <p className="font-serif text-xs text-[#76777F]">No active litigation matters.</p>
          ) : (
            <div className="space-y-1">
              {litigationMatters.map((m) => (
                <a
                  key={m.id}
                  href={`/litigation/${m.id}`}
                  className="flex items-center gap-2 rounded-sm px-2 py-1.5 font-sans text-xs font-medium text-[#081534] transition-colors hover:bg-[#E4E2DD]"
                >
                  <Gavel className="h-3.5 w-3.5 shrink-0 text-[#45464E]" />
                  <span className="truncate">{m.title}</span>
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </AuthedShell>
  );
}
