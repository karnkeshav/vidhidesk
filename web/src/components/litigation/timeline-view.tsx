"use client";

import { Gavel, FileText, ListChecks } from "lucide-react";
import { CalendarHearing, CauselistEntry, OrderOut } from "@/lib/api";

type TimelineEntry =
  | { kind: "hearing"; date: string; data: CalendarHearing }
  | { kind: "order"; date: string; data: OrderOut }
  | { kind: "causelist"; date: string; data: CauselistEntry };

/** Chronological merge of hearings + orders + causelist entries -- all
 * real, already-fetched data; no separate endpoint of its own. */
export function TimelineView({
  hearings,
  orders,
  causelist,
}: {
  hearings: CalendarHearing[];
  orders: OrderOut[];
  causelist: CauselistEntry[];
}) {
  const entries: TimelineEntry[] = [
    ...hearings.map((h): TimelineEntry => ({ kind: "hearing", date: h.hearing_at, data: h })),
    ...orders
      .filter((o) => o.order_date)
      .map((o): TimelineEntry => ({ kind: "order", date: o.order_date as string, data: o })),
    ...causelist.map((c): TimelineEntry => ({ kind: "causelist", date: c.hearing_date, data: c })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  if (entries.length === 0) {
    return (
      <div className="rounded-sm border border-[#E4E2DD] bg-white p-5">
        <p className="font-serif text-xs text-[#76777F]">
          No hearings, orders, or causelist entries recorded for this matter yet.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5">
      <h3 className="mb-3 font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">Case Timeline</h3>
      <div className="divide-y divide-[#E4E2DD]">
        {entries.map((entry) => (
          <TimelineRow key={`${entry.kind}-${"id" in entry.data ? entry.data.id : entry.date}`} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function TimelineRow({ entry }: { entry: TimelineEntry }) {
  const dateLabel = new Date(entry.date).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

  if (entry.kind === "hearing") {
    const h = entry.data;
    return (
      <div className="flex gap-3 py-2.5 font-sans text-xs">
        <Gavel className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />
        <div>
          <p className="font-semibold text-[#081534]">
            {dateLabel} — Hearing
            {h.source === "manual_override" && (
              <span className="ml-1.5 rounded-xs border border-[#C6C6CF] px-1 text-[9px] uppercase text-[#76777F]">
                Manually Corrected
              </span>
            )}
          </p>
          <p className="font-serif text-[11px] text-[#45464E]">
            {[h.court, h.bench, h.item_no].filter(Boolean).join(" · ") || "Details pending"}
          </p>
          {h.outcome && <p className="font-serif text-[11px] text-[#76777F]">Outcome: {h.outcome}</p>}
        </div>
      </div>
    );
  }

  if (entry.kind === "order") {
    const o = entry.data;
    return (
      <div className="flex gap-3 py-2.5 font-sans text-xs">
        <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />
        <div>
          <p className="font-semibold text-[#081534]">
            {dateLabel} — Order
            <span className="ml-1.5 rounded-xs bg-[#F0EEE9] px-1 text-[9px] uppercase text-[#45464E]">{o.status}</span>
          </p>
          {o.court && <p className="font-serif text-[11px] text-[#45464E]">{o.court}</p>}
          {o.raw_text && <p className="font-serif text-[11px] text-[#76777F] line-clamp-2">{o.raw_text}</p>}
        </div>
      </div>
    );
  }

  const c = entry.data;
  return (
    <div className="flex gap-3 py-2.5 font-sans text-xs">
      <ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />
      <div>
        <p className="font-semibold text-[#081534]">{dateLabel} — Causelist Entry</p>
        <p className="font-serif text-[11px] text-[#45464E]">
          {[c.court_location, c.bench_number, c.causelist_type].filter(Boolean).join(" · ") || "Listed"}
        </p>
      </div>
    </div>
  );
}
