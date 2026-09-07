"use client";

import { InterlocutoryApplication } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Interlocutory applications (CM APPLs) for this matter -- populated by
 * app/services/court_sync.py from a real, confirmed eCourts field
 * (courtCaseData.interlocutoryApplications). Empty either because the
 * matter hasn't been synced yet or genuinely has none on record. */
export function ApplicationsTracker({ applications }: { applications: InterlocutoryApplication[] }) {
  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
      <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
        Interlocutory Applications ({applications.length})
      </h3>

      {applications.length === 0 ? (
        <p className="font-serif text-xs text-[#76777F]">
          No pending applications on record. Run a Court Tracking sync to pull the latest from eCourts.
        </p>
      ) : (
        <div className="divide-y divide-[#E4E2DD]">
          {applications.map((ia) => (
            <div key={ia.id} className="py-2.5 space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-[#081534]">{ia.application_number}</span>
                <span
                  className={cn(
                    "rounded-xs px-1.5 py-0.5 text-[10px] font-bold uppercase",
                    ia.current_status === "PENDING" && "bg-[#FFF3CD] text-[#856404]",
                    ia.current_status === "GRANTED" && "bg-[#D4EDDA] text-[#155724]",
                    ia.current_status === "REJECTED" && "bg-[#FFF5F5] text-[#7A2A2A]",
                    ia.current_status === "WITHDRAWN" && "bg-[#F0EEE9] text-[#45464E]"
                  )}
                >
                  {ia.current_status}
                </span>
              </div>
              <p className="font-serif text-[11px] text-[#45464E]">
                Filed by {ia.filed_by} on {new Date(ia.filing_date).toLocaleDateString()}
              </p>
              {ia.relief_sought && <p className="font-serif text-[11px] text-[#76777F]">{ia.relief_sought}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
