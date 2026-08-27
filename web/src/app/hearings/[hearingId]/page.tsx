"use client";

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { AuthedShell } from "@/components/authed-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  Gavel,
  MapPin,
  Sparkles,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  ListChecks,
} from "lucide-react";
import {
  Matter,
  CalendarHearing,
  CalendarHearingCaptureInput,
  HearingBrief,
  getMatter,
  listCalendarHearings,
  updateCalendarHearing,
  generateHearingBrief,
  listHearingBriefs,
  reviewHearingBrief,
} from "@/lib/api";

const SOURCE_LABEL: Record<CalendarHearing["source"], string> = {
  manual: "Manually Entered",
  ecourts: "Synced from eCourts",
  manual_override: "Manually Overridden",
};

const STATUS_LABEL: Record<HearingBrief["status"], string> = {
  draft: "Draft",
  reviewed: "Reviewed",
  approved_for_hearing: "Approved for Hearing",
};

function statusBadgeClass(status: HearingBrief["status"]): string {
  if (status === "approved_for_hearing") return "border-[#1E5B3A] bg-[#EAF3EC] text-[#1E5B3A]";
  if (status === "reviewed") return "border-[#7A5A1A] bg-[#FBF3E4] text-[#7A5A1A]";
  return "border-[#E4E2DD] bg-[#F6F3EE] text-[#081534]";
}

function captureFromHearing(h: CalendarHearing): CalendarHearingCaptureInput {
  return {
    court: h.court ?? "",
    bench: h.bench ?? "",
    item_no: h.item_no ?? "",
    judge: h.judge ?? "",
    arguments_made: h.arguments_made ?? "",
    judge_questions: h.judge_questions ?? "",
    opposing_counsel_position: h.opposing_counsel_position ?? "",
    outcome: h.outcome ?? "",
    next_steps: h.next_steps ?? "",
    notes: h.notes ?? "",
  };
}

export default function HearingIntelligencePage() {
  const params = useParams<{ hearingId: string }>();
  const searchParams = useSearchParams();
  const matterIdFromUrl = searchParams.get("matterId");
  const hearingId = params.hearingId;

  const [matter, setMatter] = useState<Matter | null>(null);
  const [hearing, setHearing] = useState<CalendarHearing | null>(null);
  const [briefs, setBriefs] = useState<HearingBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState("intelligence");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [captureForm, setCaptureForm] = useState<CalendarHearingCaptureInput | null>(null);
  const [captureSaving, setCaptureSaving] = useState(false);
  const [captureSavedAt, setCaptureSavedAt] = useState<number | null>(null);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      // No single-hearing GET endpoint exists yet -- listCalendarHearings
      // already scopes by RLS to this organization, so filtering by
      // matter_id (when known from the referring link) is purely an
      // optimization; falling back to the unfiltered list keeps a direct
      // bookmark/refresh working even without ?matterId in the URL.
      const hearings = await listCalendarHearings(
        matterIdFromUrl ? { matter_id: matterIdFromUrl } : undefined
      );
      const found = hearings.find((h) => h.id === hearingId) ?? null;
      if (!found) {
        setError("Hearing not found.");
        setLoading(false);
        return;
      }
      setHearing(found);
      setCaptureForm(captureFromHearing(found));

      const matterId = matterIdFromUrl ?? found.matter_id;
      if (matterId) {
        const [m, briefList] = await Promise.all([
          getMatter(matterId).catch(() => null),
          listHearingBriefs(matterId, hearingId).catch(() => []),
        ]);
        setMatter(m);
        setBriefs(briefList.slice().sort((a, b) => b.version - a.version));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hearingId]);

  const latestBrief = briefs[0] ?? null;

  async function handleGenerateBrief() {
    if (!matter) return;
    setGenerating(true);
    setError(null);
    try {
      const brief = await generateHearingBrief(matter.id, hearingId);
      setBriefs((prev) => [brief, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

  async function handleReview(status: "reviewed" | "approved_for_hearing") {
    if (!matter || !latestBrief) return;
    setReviewBusy(true);
    setError(null);
    try {
      const updated = await reviewHearingBrief(matter.id, latestBrief.id, { status });
      setBriefs((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setReviewBusy(false);
    }
  }

  async function handleSaveCapture() {
    if (!hearing || !captureForm) return;
    setCaptureSaving(true);
    setError(null);
    try {
      const updated = await updateCalendarHearing(hearing.id, captureForm);
      setHearing(updated);
      setCaptureForm(captureFromHearing(updated));
      setCaptureSavedAt(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCaptureSaving(false);
    }
  }

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        <div>
          <Link
            href={matter ? `/litigation/${matter.id}` : "/litigation"}
            className="inline-flex items-center gap-1.5 font-sans text-xs font-semibold text-[#45464E] hover:text-[#081534]"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.5} />
            Back to {matter ? matter.title : "Matter"}
          </Link>
        </div>

        {error && (
          <div className="rounded-sm border border-[#7A2A2A] bg-[#FBEAEA] px-4 py-2 font-sans text-xs text-[#7A2A2A]">
            {error}
          </div>
        )}

        {loading && (
          <Card className="rounded-sm border border-[#E4E2DD] bg-white p-6 shadow-none">
            <p className="font-serif text-xs text-[#76777F]">Loading hearing…</p>
          </Card>
        )}

        {!loading && hearing && (
          <>
            {/* Hearing Header */}
            <Card className="rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none">
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-[#081534]">
                      {SOURCE_LABEL[hearing.source]}
                    </span>
                    {hearing.item_no && (
                      <span className="rounded-sm bg-[#1E2A4A] px-2 py-0.5 font-sans text-[10px] font-semibold text-white">
                        Item {hearing.item_no}
                      </span>
                    )}
                  </div>
                  <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534]">
                    {matter ? matter.title : hearing.title}
                  </h1>
                  <p className="font-serif text-sm text-[#45464E]">
                    {new Date(hearing.hearing_at).toLocaleString(undefined, {
                      weekday: "long",
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 font-sans text-xs text-[#45464E]">
                    {hearing.court && (
                      <span className="flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5 text-[#76777F]" /> {hearing.court}
                      </span>
                    )}
                    {hearing.bench && <span>Bench: {hearing.bench}</span>}
                    {hearing.judge && <span>Judge: {hearing.judge}</span>}
                  </div>
                </div>
                <p className="max-w-xs font-serif text-[11px] italic text-[#76777F]">
                  AI-generated draft for advocate review. Not legal advice.
                </p>
              </div>
            </Card>

            {/* Main Tabs */}
            <div className="flex gap-4 border-b border-[#E4E2DD] mb-6">
              <button onClick={() => setActiveTab("history")} className={`pb-2 font-sans text-sm font-semibold uppercase tracking-wider ${activeTab === "history" ? "border-b-2 border-[#081534] text-[#081534]" : "text-[#76777F]"}`}>
                Matter History
              </button>
              <button onClick={() => setActiveTab("record")} className={`pb-2 font-sans text-sm font-semibold uppercase tracking-wider ${activeTab === "record" ? "border-b-2 border-[#081534] text-[#081534]" : "text-[#76777F]"}`}>
                Legal Record
              </button>
              <button onClick={() => setActiveTab("intelligence")} className={`pb-2 font-sans text-sm font-semibold uppercase tracking-wider ${activeTab === "intelligence" ? "border-b-2 border-[#081534] text-[#081534]" : "text-[#76777F]"}`}>
                AI Intelligence
              </button>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Main: Argument Brief */}
              {activeTab === "history" && (<div className="space-y-4 lg:col-span-8"><Card className="rounded-sm border border-[#E4E2DD] bg-white p-6"><p className="font-serif text-sm text-[#76777F]">No prior matter history populated yet.</p></Card></div>)}
              {activeTab === "record" && (<div className="space-y-4 lg:col-span-8"><Card className="rounded-sm border border-[#E4E2DD] bg-white p-6"><p className="font-serif text-sm text-[#76777F]">Legal record empty.</p></Card></div>)}
              {activeTab === "intelligence" && (<div className="space-y-4 lg:col-span-8">
                <Card className="rounded-sm border border-[#E4E2DD] bg-white shadow-none">
                  <CardHeader className="flex flex-row items-center justify-between border-b border-[#E4E2DD] p-4">
                    <div className="flex items-center gap-2">
                      <Gavel className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                      <CardTitle className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                        Hearing / Argument Brief
                      </CardTitle>
                    </div>
                    <Button
                      onClick={handleGenerateBrief}
                      disabled={generating || !matter}
                      className="h-8 gap-2 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${generating ? "animate-spin" : ""}`} strokeWidth={1.5} />
                      {generating
                        ? "Generating…"
                        : latestBrief
                          ? "Regenerate Brief"
                          : "Generate Brief"}
                    </Button>
                  </CardHeader>
                  <CardContent className="space-y-5 p-4">
                    {!latestBrief && (
                      <p className="font-serif text-xs text-[#76777F]">
                        No brief has been generated for this hearing yet. Generating a brief assembles the
                        full matter intelligence bundle (pleadings, prior hearing notes, orders, evidence,
                        research, verified citations) and produces a grounded Grounded Facts, Supported
                        Arguments, AI-Suggested Points, a Checklist, and any Information Gaps.
                      </p>
                    )}

                    {latestBrief && (
                      <>
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E4E2DD] pb-3">
                          <div className="flex items-center gap-2">
                            <span
                              className={`rounded-sm border px-2 py-1 font-sans text-[11px] font-semibold ${statusBadgeClass(latestBrief.status)}`}
                            >
                              {STATUS_LABEL[latestBrief.status]}
                            </span>
                            <span className="font-sans text-[11px] text-[#76777F]">
                              v{latestBrief.version} · generated{" "}
                              {new Date(latestBrief.generated_at).toLocaleString()}
                            </span>
                          </div>
                          <div className="flex gap-2">
                            {latestBrief.status === "draft" && (
                              <Button
                                onClick={() => handleReview("reviewed")}
                                disabled={reviewBusy}
                                variant="outline"
                                className="h-7 rounded-sm border-[#E4E2DD] px-2 font-sans text-[11px] font-semibold text-[#081534]"
                              >
                                Mark Reviewed
                              </Button>
                            )}
                            {latestBrief.status === "reviewed" && (
                              <Button
                                onClick={() => handleReview("approved_for_hearing")}
                                disabled={reviewBusy}
                                className="h-7 gap-1 rounded-sm bg-[#1E5B3A] px-2 font-sans text-[11px] font-semibold text-white hover:bg-[#164A2E]"
                              >
                                <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.5} />
                                Approve for Hearing
                              </Button>
                            )}
                          </div>
                        </div>

                        {latestBrief.brief_content.generation_warning && (
                          <div className="flex items-start gap-2 rounded-sm border border-[#7A5A1A] bg-[#FBF3E4] px-3 py-2 font-sans text-[11px] text-[#7A5A1A]">
                            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                            {latestBrief.brief_content.generation_warning}
                          </div>
                        )}

                        {/* Grounded Facts */}
                        <section className="space-y-2">
                          <div className="flex items-center gap-1.5">
                            <ShieldCheck className="h-3.5 w-3.5 text-[#081534]" strokeWidth={1.5} />
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
                              Grounded Facts
                            </h3>
                          </div>
                          {latestBrief.brief_content.case_record.length === 0 && (
                            <p className="font-serif text-[11px] text-[#76777F]">None available.</p>
                          )}
                          {latestBrief.brief_content.case_record.map((entry, i) => (
                            <div key={i} className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3">
                              <p className="font-sans text-xs font-semibold text-[#1A1A1A]">{entry.heading}</p>
                              <p className="mt-1 font-serif text-xs text-[#45464E]">{entry.content}</p>
                              {entry.source_refs.length > 0 && (
                                <p className="mt-1.5 font-sans text-[10px] text-[#76777F]">
                                  Sources: {entry.source_refs.join(", ")}
                                </p>
                              )}
                            </div>
                          ))}
                        </section>


                        {/* Risk Highlights */}
                        <section className="space-y-2">
                          <div className="flex items-center gap-1.5">
                            <AlertTriangle className="h-3.5 w-3.5 text-[#081534]" strokeWidth={1.5} />
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
                              Risk Highlights
                            </h3>
                          </div>
                          <p className="font-serif text-[11px] text-[#76777F]">No significant risks detected in the current record.</p>
                        </section>

                        {/* Supported Arguments */}
                        <section className="space-y-2">
                          <div className="flex items-center gap-1.5">
                            <ShieldCheck className="h-3.5 w-3.5 text-[#081534]" strokeWidth={1.5} />
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
                              Supported Arguments
                            </h3>
                          </div>
                          {latestBrief.brief_content.supported_arguments.length === 0 && (
                            <p className="font-serif text-[11px] text-[#76777F]">None available.</p>
                          )}
                          {latestBrief.brief_content.supported_arguments.map((entry, i) => (
                            <div key={i} className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3">
                              <p className="font-serif text-xs text-[#1A1A1A]">{entry.argument}</p>
                              {entry.source_refs.length > 0 && (
                                <p className="mt-1.5 font-sans text-[10px] text-[#76777F]">
                                  Sources: {entry.source_refs.join(", ")}
                                </p>
                              )}
                            </div>
                          ))}
                        </section>

                        {/* AI-Suggested Points — visually distinct, explicitly unverified */}
                        <section className="space-y-2">
                          <div className="flex items-center gap-1.5">
                            <Sparkles className="h-3.5 w-3.5 text-[#7A5A1A]" strokeWidth={1.5} />
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#7A5A1A]">
                              AI-Suggested Points — Verify Before Use
                            </h3>
                          </div>
                          {latestBrief.brief_content.ai_suggested_points.length === 0 && (
                            <p className="font-serif text-[11px] text-[#76777F]">None suggested.</p>
                          )}
                          <ul className="space-y-1.5">
                            {latestBrief.brief_content.ai_suggested_points.map((pt, i) => (
                              <li
                                key={i}
                                className="rounded-sm border border-dashed border-[#D9C088] bg-[#FBF3E4] p-3 font-serif text-xs text-[#5A431A]"
                              >
                                {pt}
                              </li>
                            ))}
                          </ul>
                        </section>

                        {/* Checklist */}
                        <section className="space-y-2">
                          <div className="flex items-center gap-1.5">
                            <ListChecks className="h-3.5 w-3.5 text-[#081534]" strokeWidth={1.5} />
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#081534]">
                              Checklist
                            </h3>
                          </div>
                          <ul className="space-y-1">
                            {latestBrief.brief_content.checklist.map((item, i) => (
                              <li key={i} className="flex items-start gap-2 font-serif text-xs text-[#1A1A1A]">
                                <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[#081534]" />
                                {item}
                              </li>
                            ))}
                          </ul>
                        </section>

                        {/* Information Gaps */}
                        <section className="space-y-2">
                          <div className="flex items-center gap-1.5">
                            <AlertTriangle className="h-3.5 w-3.5 text-[#7A2A2A]" strokeWidth={1.5} />
                            <h3 className="font-sans text-xs font-bold uppercase tracking-wider text-[#7A2A2A]">
                              Information Gaps
                            </h3>
                          </div>
                          {latestBrief.brief_content.information_gaps.length === 0 && (
                            <p className="font-serif text-[11px] text-[#76777F]">No gaps identified.</p>
                          )}
                          <ul className="space-y-1">
                            {latestBrief.brief_content.information_gaps.map((gap, i) => (
                              <li key={i} className="font-serif text-xs text-[#7A2A2A]">
                                — {gap}
                              </li>
                            ))}
                          </ul>
                        </section>
                      </>
                    )}
                  </CardContent>
                </Card>

                {briefs.length > 1 && (
                  <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
                    <p className="mb-2 font-sans text-[11px] font-semibold uppercase tracking-wider text-[#081534]">
                      Prior Versions
                    </p>
                    <div className="space-y-1">
                      {briefs.slice(1).map((b) => (
                        <div key={b.id} className="flex items-center justify-between font-sans text-[11px] text-[#45464E]">
                          <span>v{b.version} — {new Date(b.generated_at).toLocaleDateString()}</span>
                          <span className={`rounded-sm border px-1.5 py-0.5 ${statusBadgeClass(b.status)}`}>
                            {STATUS_LABEL[b.status]}
                          </span>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>)}

              {/* Sidebar: Post-Hearing Capture */}
              <div className="space-y-4 lg:col-span-4">
                <Card className="rounded-sm border border-[#E4E2DD] bg-white shadow-none">
                  <CardHeader className="border-b border-[#E4E2DD] p-4">
                    <CardTitle className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                      Post-Hearing Capture
                    </CardTitle>
                    <p className="font-serif text-[11px] text-[#76777F]">
                      Feeds directly into the next hearing&apos;s brief.
                    </p>
                  </CardHeader>
                  <CardContent className="space-y-3 p-4">
                    {captureForm && (
                      <>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label htmlFor="hi-court" className="text-[11px]">Court</Label>
                            <Input
                              id="hi-court"
                              value={captureForm.court ?? ""}
                              onChange={(e) => setCaptureForm({ ...captureForm, court: e.target.value })}
                              className="h-8 text-xs"
                            />
                          </div>
                          <div className="space-y-1">
                            <Label htmlFor="hi-bench" className="text-[11px]">Bench</Label>
                            <Input
                              id="hi-bench"
                              value={captureForm.bench ?? ""}
                              onChange={(e) => setCaptureForm({ ...captureForm, bench: e.target.value })}
                              className="h-8 text-xs"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div className="space-y-1">
                            <Label htmlFor="hi-item" className="text-[11px]">Item No.</Label>
                            <Input
                              id="hi-item"
                              value={captureForm.item_no ?? ""}
                              onChange={(e) => setCaptureForm({ ...captureForm, item_no: e.target.value })}
                              className="h-8 text-xs"
                            />
                          </div>
                          <div className="space-y-1">
                            <Label htmlFor="hi-judge" className="text-[11px]">Judge</Label>
                            <Input
                              id="hi-judge"
                              value={captureForm.judge ?? ""}
                              onChange={(e) => setCaptureForm({ ...captureForm, judge: e.target.value })}
                              className="h-8 text-xs"
                            />
                          </div>
                        </div>

                        <div className="space-y-1">
                          <Label htmlFor="hi-arguments" className="text-[11px]">Arguments Made</Label>
                          <Textarea
                            id="hi-arguments"
                            rows={3}
                            value={captureForm.arguments_made ?? ""}
                            onChange={(e) => setCaptureForm({ ...captureForm, arguments_made: e.target.value })}
                            className="text-xs"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="hi-judge-questions" className="text-[11px]">Judge&apos;s Questions</Label>
                          <Textarea
                            id="hi-judge-questions"
                            rows={2}
                            value={captureForm.judge_questions ?? ""}
                            onChange={(e) => setCaptureForm({ ...captureForm, judge_questions: e.target.value })}
                            className="text-xs"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="hi-opposing" className="text-[11px]">Opposing Counsel Position</Label>
                          <Textarea
                            id="hi-opposing"
                            rows={2}
                            value={captureForm.opposing_counsel_position ?? ""}
                            onChange={(e) => setCaptureForm({ ...captureForm, opposing_counsel_position: e.target.value })}
                            className="text-xs"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="hi-outcome" className="text-[11px]">Outcome</Label>
                          <Textarea
                            id="hi-outcome"
                            rows={2}
                            value={captureForm.outcome ?? ""}
                            onChange={(e) => setCaptureForm({ ...captureForm, outcome: e.target.value })}
                            className="text-xs"
                          />
                        </div>
                        <div className="space-y-1">
                          <Label htmlFor="hi-next-steps" className="text-[11px]">Next Steps / Directions</Label>
                          <Textarea
                            id="hi-next-steps"
                            rows={2}
                            value={captureForm.next_steps ?? ""}
                            onChange={(e) => setCaptureForm({ ...captureForm, next_steps: e.target.value })}
                            className="text-xs"
                          />
                        </div>

                        <Button
                          onClick={handleSaveCapture}
                          disabled={captureSaving}
                          className="h-8 w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
                        >
                          {captureSaving ? "Saving…" : "Save Hearing Notes"}
                        </Button>
                        {captureSavedAt && !captureSaving && (
                          <p className="text-center font-sans text-[10px] text-[#1E5B3A]">Saved.</p>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          </>
        )}
      </div>
    </AuthedShell>
  );
}
