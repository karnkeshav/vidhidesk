"use client";

import type { ReactNode } from "react";
import { CourtCaseTracking, Matter } from "@/lib/api";
import { cn } from "@/lib/utils";

/** CNR/court/status header for the case-details page -- reads only
 * court_case_tracking's typed fields (court_name/judge/case_status/
 * petitioners/respondents), never provider_metadata's raw envelope
 * directly (see CourtCaseTracking's own comment in lib/api.ts). */
export function CaseMetadata({ matter, tracking }: { matter: Matter | null; tracking: CourtCaseTracking | null }) {
  const hasCnr = !!tracking?.cnr_number;

  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
      <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">Case Metadata</h3>

      {!hasCnr ? (
        <p className="font-serif text-xs text-[#76777F]">
          No CNR registered for this matter yet. Add one from the Court Tracking panel on the Overview tab.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
          <Field label="CNR" value={tracking?.cnr_number} />
          <Field label="Case No." value={matter?.case_number_formatted} />
          <Field label="Court" value={tracking?.court_name || matter?.court_name} />
          <Field label="Judge" value={tracking?.judge} />
          <Field
            label="Status"
            value={
              tracking?.case_status ? (
                <span
                  className={cn(
                    "rounded-xs px-1.5 py-0.5 text-[10px] font-bold uppercase",
                    /pending/i.test(tracking.case_status) ? "bg-[#FFF3CD] text-[#856404]" : "bg-[#F0EEE9] text-[#45464E]"
                  )}
                >
                  {tracking.case_status}
                </span>
              ) : null
            }
          />
          <Field label="Sync Status" value={tracking?.sync_status} />
          <Field
            label="Last Synced"
            value={tracking?.last_synced_at ? new Date(tracking.last_synced_at).toLocaleString() : null}
          />
          {tracking?.petitioners && tracking.petitioners.length > 0 && (
            <div className="sm:col-span-2">
              <p className="font-semibold text-[#081534]">Petitioners</p>
              <p className="font-serif text-[11px] text-[#45464E]">{tracking.petitioners.join(", ")}</p>
            </div>
          )}
          {tracking?.respondents && tracking.respondents.length > 0 && (
            <div className="sm:col-span-2">
              <p className="font-semibold text-[#081534]">Respondents</p>
              <p className="font-serif text-[11px] text-[#45464E]">{tracking.respondents.join(", ")}</p>
            </div>
          )}
          {tracking?.interim_orders && tracking.interim_orders.length > 0 && (
            <div className="sm:col-span-2">
              <p className="font-semibold text-[#081534]">eCourts Orders & Files ({tracking.interim_orders.length})</p>
              <div className="mt-1 space-y-1">
                {tracking.interim_orders.map((io, idx) => (
                  <div key={idx} className="flex items-center gap-2 font-serif text-[11px] text-[#45464E]">
                    <span className="font-sans font-semibold text-[#081534]">{io.order_date || "Undated"}:</span>
                    <span>{io.description || "Order"}</span>
                    {io.order_url && (
                      <span className="rounded-xs border border-[#E4E2DD] bg-[#FBF9F4] px-1 font-mono text-[9px]">
                        {io.order_url}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          {tracking?.last_error && (
            <div className="sm:col-span-2">
              <p className="font-semibold text-[#7A2A2A]">Last Sync Error</p>
              <p className="font-serif text-[11px] text-[#7A2A2A]">{tracking.last_error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: ReactNode }) {
  if (!value) return null;
  return (
    <div>
      <p className="font-semibold text-[#081534]">{label}</p>
      <div className="font-serif text-[11px] text-[#45464E]">{value}</div>
    </div>
  );
}
