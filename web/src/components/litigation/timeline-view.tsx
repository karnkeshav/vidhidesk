"use client";

import { Gavel, FileText, ListChecks, FilePlus, FileCheck, Scale, Layers } from "lucide-react";
import { CalendarHearing, CauselistEntry, OrderOut, CourtCaseTracking, InterlocutoryApplication } from "@/lib/api";

type EventIconType = "filing" | "registration" | "first_hearing" | "disposal" | "application" | "past_hearing";

type TimelineEntry =
  | { kind: "hearing"; date: string; data: CalendarHearing }
  | { kind: "order"; date: string; data: OrderOut }
  | { kind: "causelist"; date: string; data: CauselistEntry }
  | {
      kind: "event";
      date: string;
      title: string;
      subtitle?: string;
      description?: string;
      badge?: string;
      badgeVariant?: "default" | "success" | "warning" | "info" | "neutral";
      iconType: EventIconType;
    };

function isAbsoluteUrl(value?: string | null): boolean {
  if (!value) return false;
  return /^https?:\/\//i.test(value);
}

/** Chronological merge of hearings + orders + causelist + case lifecycle
 * events (filing, registration, first hearing, disposal, applications). */
export function TimelineView({
  hearings,
  orders,
  causelist,
  tracking,
  applications,
}: {
  hearings: CalendarHearing[];
  orders: OrderOut[];
  causelist: CauselistEntry[];
  tracking?: CourtCaseTracking | null;
  applications?: InterlocutoryApplication[];
}) {
  const eventEntries: TimelineEntry[] = [];

  const providerMeta = tracking?.provider_metadata as Record<string, unknown> | null;
  const courtCaseData = (
    providerMeta?.courtCaseData || (providerMeta?.data as Record<string, unknown> | undefined)?.courtCaseData
  ) as Record<string, unknown> | undefined;

  if (courtCaseData) {
    // 1. Case Filing
    const filingDate = (courtCaseData.filingDate || courtCaseData.filing_date) as string | undefined;
    if (filingDate) {
      const filingNo = (courtCaseData.filingNumber || courtCaseData.filing_number) as string | undefined;
      const caseType = (courtCaseData.caseTypeRaw || courtCaseData.caseType || courtCaseData.case_type) as string | undefined;
      const courtName = (courtCaseData.courtName || tracking?.court_name) as string | undefined;
      eventEntries.push({
        kind: "event",
        date: filingDate,
        title: filingNo ? `Case Filed (Filing No. ${filingNo})` : "Case Filed",
        subtitle: [caseType, courtName].filter(Boolean).join(" · "),
        description: tracking?.petitioners && tracking.petitioners.length > 0 ? `Petitioner: ${tracking.petitioners.join(", ")}` : undefined,
        badge: "Filing",
        badgeVariant: "neutral",
        iconType: "filing",
      });
    }

    // 2. Case Registration
    const regDate = (courtCaseData.registrationDate || courtCaseData.registration_date) as string | undefined;
    if (regDate) {
      const regNo = (courtCaseData.registrationNumber || courtCaseData.registration_number) as string | undefined;
      const section = (courtCaseData.judicialSectionRaw || courtCaseData.judicialSection) as string | undefined;
      eventEntries.push({
        kind: "event",
        date: regDate,
        title: regNo ? `Case Registered (${regNo})` : "Case Registered",
        subtitle: section ? `Judicial Section: ${section}` : undefined,
        badge: "Registration",
        badgeVariant: "info",
        iconType: "registration",
      });
    }

    // 3. First Hearing
    const firstHearingDate = (courtCaseData.firstHearingDate || courtCaseData.first_hearing_date) as string | undefined;
    if (firstHearingDate) {
      const stage = (courtCaseData.purpose || courtCaseData.stageOfCaseRaw || courtCaseData.stageOfCase) as string | undefined;
      const judges = Array.isArray(courtCaseData.judges) ? (courtCaseData.judges as string[]).join(", ") : undefined;
      eventEntries.push({
        kind: "event",
        date: firstHearingDate,
        title: "First Court Hearing",
        subtitle: judges ? `Bench: ${judges}` : undefined,
        description: stage ? `Stage / Purpose: ${stage}` : undefined,
        badge: "First Hearing",
        badgeVariant: "default",
        iconType: "first_hearing",
      });
    }

    // 4. Case Disposal / Decision
    const decisionDate = (courtCaseData.decisionDate || courtCaseData.decision_date) as string | undefined;
    if (decisionDate) {
      const disposalType = (courtCaseData.disposalTypeRaw || courtCaseData.disposalType) as string | undefined;
      const status = (courtCaseData.caseStatus || tracking?.case_status) as string | undefined;
      eventEntries.push({
        kind: "event",
        date: decisionDate,
        title: "Case Disposed / Decided",
        subtitle: disposalType && disposalType !== "UNKNOWN" ? `Disposal: ${disposalType}` : status ? `Status: ${status}` : undefined,
        badge: status || "Disposed",
        badgeVariant: "success",
        iconType: "disposal",
      });
    }

    // 5. History of Case Hearings (past hearings from eCourts)
    const historyOfHearings = (courtCaseData.historyOfCaseHearings || courtCaseData.history_of_case_hearings) as Array<Record<string, unknown>> | undefined;
    if (Array.isArray(historyOfHearings)) {
      historyOfHearings.forEach((hh) => {
        const hDate = (hh.hearingDate || hh.businessOnDate || hh.date || hh.hearing_date) as string | undefined;
        if (hDate) {
          const purpose = (hh.purposeOfHearing || hh.purpose || hh.stage) as string | undefined;
          const judgeName = (hh.judge || hh.bench || hh.courtNo) as string | undefined;
          const business = (hh.business || hh.order) as string | undefined;
          eventEntries.push({
            kind: "event",
            date: hDate,
            title: purpose ? `Hearing — ${purpose}` : "Court Hearing",
            subtitle: judgeName ? `Bench: ${judgeName}` : undefined,
            description: business ? `Business: ${business}` : undefined,
            badge: "Hearing History",
            badgeVariant: "default",
            iconType: "past_hearing",
          });
        }
      });
    }
  }

  // 6. Interlocutory Applications
  if (applications && applications.length > 0) {
    applications.forEach((ia) => {
      if (ia.filing_date) {
        eventEntries.push({
          kind: "event",
          date: ia.filing_date,
          title: `Application Filed — ${ia.application_number}`,
          subtitle: `Filed by: ${ia.filed_by}`,
          description: ia.current_status ? `Status: ${ia.current_status}` : undefined,
          badge: "Application",
          badgeVariant: "warning",
          iconType: "application",
        });
      }
    });
  }

  const allRawEntries: TimelineEntry[] = [
    ...hearings.map((h): TimelineEntry => ({ kind: "hearing", date: h.hearing_at, data: h })),
    ...orders
      .filter((o) => o.order_date)
      .map((o): TimelineEntry => ({ kind: "order", date: o.order_date as string, data: o })),
    ...causelist.map((c): TimelineEntry => ({ kind: "causelist", date: c.hearing_date, data: c })),
    ...eventEntries,
  ];

  // Deduplicate entries by kind + date + unique key
  const seen = new Set<string>();
  const entries: TimelineEntry[] = [];

  for (const item of allRawEntries) {
    if (!item.date) continue;
    let key = "";
    if (item.kind === "hearing") key = `hearing-${item.data.id || item.date}`;
    else if (item.kind === "order") key = `order-${item.data.id || item.date}`;
    else if (item.kind === "causelist") key = `causelist-${item.data.id || item.date}`;
    else key = `event-${item.date}-${item.title}`;

    if (!seen.has(key)) {
      seen.add(key);
      entries.push(item);
    }
  }

  entries.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

  if (entries.length === 0) {
    return (
      <div className="rounded-sm border border-[#E4E2DD] bg-white p-5">
        <p className="font-serif text-xs text-[#76777F]">
          No hearings, orders, or case timeline entries recorded for this matter yet.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">Case Timeline</h3>
        <span className="font-mono text-[10px] text-[#76777F]">{entries.length} Events</span>
      </div>
      <div className="divide-y divide-[#E4E2DD]">
        {entries.map((entry, idx) => (
          <TimelineRow key={idx} entry={entry} />
        ))}
      </div>
    </div>
  );
}

function TimelineRow({ entry }: { entry: TimelineEntry }) {
  const dateLabel = new Date(entry.date).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  if (entry.kind === "hearing") {
    const h = entry.data;
    return (
      <div className="flex gap-3 py-2.5 font-sans text-xs">
        <Gavel className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />
        <div className="space-y-0.5">
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
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-[#081534]">{dateLabel} — Order</span>
            <span className="rounded-xs bg-[#F0EEE9] px-1 text-[9px] uppercase text-[#45464E]">{o.status}</span>
            <span className="rounded-xs border border-[#C6C6CF] px-1 text-[9px] uppercase text-[#76777F]">
              {o.source}
            </span>
          </div>
          {o.court && <p className="font-serif text-[11px] text-[#45464E]">{o.court}</p>}
          {o.raw_text && <p className="font-serif text-[11px] text-[#76777F]">{o.raw_text}</p>}
          {o.file_url && isAbsoluteUrl(o.file_url) && (
            <div className="pt-1">
              <a
                href={o.file_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-xs border border-[#E4E2DD] bg-[#FBF9F4] px-1.5 py-0.5 font-mono text-[9px] text-[#081534] hover:bg-[#F0EEE9]"
              >
                📄 View Order PDF
              </a>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (entry.kind === "causelist") {
    const c = entry.data;
    return (
      <div className="flex gap-3 py-2.5 font-sans text-xs">
        <ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />
        <div className="space-y-0.5">
          <p className="font-semibold text-[#081534]">{dateLabel} — Causelist Entry</p>
          <p className="font-serif text-[11px] text-[#45464E]">
            {[c.court_location, c.bench_number, c.causelist_type].filter(Boolean).join(" · ") || "Listed"}
          </p>
        </div>
      </div>
    );
  }

  // Generic case lifecycle event
  const renderIcon = () => {
    switch (entry.iconType) {
      case "filing":
        return <FilePlus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />;
      case "registration":
        return <FileCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#155724]" />;
      case "first_hearing":
      case "past_hearing":
        return <Gavel className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />;
      case "disposal":
        return <Scale className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#155724]" />;
      case "application":
        return <Layers className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#856404]" />;
      default:
        return <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#081534]" />;
    }
  };

  const getBadgeStyle = () => {
    switch (entry.badgeVariant) {
      case "success":
        return "bg-[#D4EDDA] text-[#155724]";
      case "warning":
        return "bg-[#FFF3CD] text-[#856404]";
      case "info":
        return "bg-[#D1ECF1] text-[#0C5460]";
      case "neutral":
        return "bg-[#F0EEE9] text-[#45464E]";
      default:
        return "bg-[#E8EEF5] text-[#081534]";
    }
  };

  return (
    <div className="flex gap-3 py-2.5 font-sans text-xs">
      {renderIcon()}
      <div className="space-y-0.5">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[#081534]">{dateLabel}</span>
          <span className="text-[#76777F]">—</span>
          <span className="font-medium text-[#081534]">{entry.title}</span>
          {entry.badge && (
            <span className={`rounded-xs px-1 text-[9px] uppercase font-semibold ${getBadgeStyle()}`}>
              {entry.badge}
            </span>
          )}
        </div>
        {entry.subtitle && <p className="font-serif text-[11px] text-[#45464E]">{entry.subtitle}</p>}
        {entry.description && <p className="font-serif text-[11px] text-[#76777F]">{entry.description}</p>}
      </div>
    </div>
  );
}
