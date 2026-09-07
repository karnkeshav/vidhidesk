"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CourtCaseTracking } from "@/lib/api";

/** Collapsed by default -- the complete raw eCourts response for this
 * matter's CNR (court_case_tracking.provider_metadata), everything the
 * provider returned, not just the fields the app has chosen to extract
 * into typed columns/UI cards elsewhere on this page (Case Metadata,
 * Applications, Parties & Counsel). Exists because those cards
 * deliberately surface only a curated subset -- this is the ground
 * truth underneath them, for confirming exactly what eCourts sent back
 * (FIR details, filing/registration numbers, order/hearing counts,
 * listing history, and anything not yet wired into a dedicated field). */
export function RawProviderData({ tracking }: { tracking: CourtCaseTracking | null }) {
  const [open, setOpen] = useState(false);

  if (!tracking?.provider_metadata) return null;

  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white font-sans text-xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 p-5 text-left"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 text-[#081534]" /> : <ChevronRight className="h-3.5 w-3.5 text-[#081534]" />}
        <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
          Raw eCourts Response
        </h3>
      </button>
      {open && (
        <div className="border-t border-[#E4E2DD] p-5 pt-3">
          <p className="mb-2 font-serif text-[11px] text-[#76777F]">
            Everything the provider returned for this CNR as of the last sync -- the complete source the fields
            above were extracted from.
          </p>
          <pre className="max-h-[32rem] overflow-auto rounded-sm bg-[#0B1220] p-3 font-mono text-[10px] leading-relaxed text-[#D5DAE5]">
            {JSON.stringify(tracking.provider_metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
