"use client";

import { CalendarDays, Download } from "lucide-react";
import { CalendarHearing, CourtCaseTracking, Matter } from "@/lib/api";
import { buildHearingIcs, downloadIcs } from "@/lib/ics";

/** Surfaces the soonest upcoming hearing for this matter. Prefers a real
 * `hearings` row (has an exact time and richer fields) whose date matches
 * court_case_tracking.next_hearing_date; falls back to the bare date from
 * tracking if no matching hearing row exists yet. Never fabricates a time
 * -- an unmatched next_hearing_date renders as a date-only alert. */
export function NextHearingAlert({
  matter,
  tracking,
  hearings,
}: {
  matter: Matter | null;
  tracking: CourtCaseTracking | null;
  hearings: CalendarHearing[];
}) {
  const nextDate = tracking?.next_hearing_date;
  if (!nextDate) return null;

  const matchedHearing = hearings.find((h) => h.hearing_at.slice(0, 10) === nextDate);
  const hearingAtIso = matchedHearing?.hearing_at ?? `${nextDate}T10:30:00`;
  const daysAway = Math.ceil((new Date(nextDate).getTime() - Date.now()) / 86400000);

  function handleExport() {
    const title = `Hearing — ${matter?.title || "Matter"}`;
    const ics = buildHearingIcs({
      uid: matchedHearing?.id || `${matter?.id}-${nextDate}`,
      title,
      hearingAt: hearingAtIso,
      location: [matchedHearing?.court || tracking?.court_name, matchedHearing?.bench].filter(Boolean).join(", ") || undefined,
      description: tracking?.cnr_number ? `CNR: ${tracking.cnr_number}` : undefined,
    });
    downloadIcs(`hearing-${nextDate}.ics`, ics);
  }

  return (
    <div
      className={
        "flex items-center justify-between gap-3 rounded-sm border p-4 font-sans text-xs " +
        (daysAway <= 2 ? "border-[#F8D7DA] bg-[#FFF5F5]" : "border-[#E4E2DD] bg-[#FBF9F4]")
      }
    >
      <div className="flex items-center gap-3">
        <CalendarDays className={"h-5 w-5 shrink-0 " + (daysAway <= 2 ? "text-[#7A2A2A]" : "text-[#081534]")} />
        <div>
          <p className={"font-bold " + (daysAway <= 2 ? "text-[#7A2A2A]" : "text-[#081534]")}>
            Next Hearing: {new Date(nextDate).toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            {daysAway >= 0 && ` (${daysAway === 0 ? "today" : daysAway === 1 ? "tomorrow" : `${daysAway} days away`})`}
          </p>
          {(matchedHearing?.court || tracking?.court_name) && (
            <p className="font-serif text-[11px] text-[#45464E]">
              {[matchedHearing?.court || tracking?.court_name, matchedHearing?.bench, matchedHearing?.item_no]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={handleExport}
        className="flex shrink-0 items-center gap-1.5 rounded-sm border border-[#081534] px-3 py-1.5 font-semibold text-[#081534] hover:bg-[#081534] hover:text-white"
      >
        <Download className="h-3.5 w-3.5" />
        Add to Calendar
      </button>
    </div>
  );
}
