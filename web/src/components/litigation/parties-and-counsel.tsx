"use client";

import { CaseAdvocate } from "@/lib/api";

const ROLE_LABELS: Record<CaseAdvocate["role"], string> = {
  PETITIONER_COUNSEL: "Counsel for Petitioner",
  RESPONDENT_COUNSEL: "Counsel for Respondent",
  UNKNOWN: "Role Unconfirmed",
};

/** Advocates linked to this matter (court_advocates joined through
 * case_advocate_links). Real backend/endpoint, but nothing populates it
 * automatically yet -- same unverified-provider-shape reason as
 * ApplicationsTracker; see that component's comment. Always empty until
 * that extraction is written. */
export function PartiesAndCounsel({ advocates }: { advocates: CaseAdvocate[] }) {
  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
      <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
        Parties &amp; Counsel ({advocates.length})
      </h3>

      {advocates.length === 0 ? (
        <p className="font-serif text-xs text-[#76777F]">
          No advocate contact details on record for this matter. Automatic extraction from eCourts isn&apos;t wired
          up yet for this data — this list will stay empty until that&apos;s built.
        </p>
      ) : (
        <div className="divide-y divide-[#E4E2DD]">
          {advocates.map((a) => (
            <div key={a.advocate_id} className="py-2.5 space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-[#081534]">{a.name}</span>
                <span className="rounded-xs bg-[#F0EEE9] px-1.5 py-0.5 text-[10px] font-bold uppercase text-[#081534]">
                  {ROLE_LABELS[a.role]}
                </span>
              </div>
              {a.bar_council_id && <p className="font-serif text-[11px] text-[#76777F]">Bar Council ID: {a.bar_council_id}</p>}
              {(a.phone || a.email) && (
                <p className="font-serif text-[11px] text-[#45464E]">{[a.phone, a.email].filter(Boolean).join(" · ")}</p>
              )}
              {a.office_address && <p className="font-serif text-[11px] text-[#76777F]">{a.office_address}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
