"use client";

import React, { useEffect, useRef, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getMatter, listEvidence, listMessages, listParties, addParty, deleteParty, addEvidence, deleteEvidence, uploadEvidenceFile, calculateLimitation, determineForum, sendMessage, Matter, Message } from "@/lib/api";
import { LitigationPartyModal } from "@/components/litigation-party-modal";
import { LitigationFactTimeline, FactItem } from "@/components/litigation-fact-timeline";
import { LitigationCaseAnalysis } from "@/components/litigation-case-analysis";
import { LitigationPleadingWorkbench } from "@/components/litigation-pleading-workbench";
import { UserPlus, Calendar, Plus, Trash2, Send, Clock, Gavel, Sparkles, FileText, Radar, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { CaseAnalysis, listCaseAnalyses } from "@/lib/api";
import {
  CourtCaseTracking,
  CourtCaseSearchItem,
  CourtCasePreview,
  CalendarHearing,
  getCourtTracking,
  updateCourtTracking,
  triggerCourtSync,
  searchCourtCases,
  previewCourtCase,
  listCalendarHearings,
  createCalendarHearing,
} from "@/lib/api";

interface PartyItem {
  id: string;
  party_type: string;
  party_name: string;
  party_number: number;
  address?: string | null;
  advocate_name?: string | null;
}

interface LimitationResult {
  cause_of_action_date: string;
  suit_category: string;
  limitation_expiry_date: string;
  is_barred: boolean;
  days_remaining: number;
  primary_article: {
    article_number: string;
    description: string;
    statutory_period_years: number;
    governing_act: string;
    trigger_event: string;
    notes?: string | null;
  };
  condonation_required: boolean;
  condonation_notes: string;
  notice: string;
}

interface ForumResult {
  recommended_forum: {
    forum_name: string;
    court_category: string;
    territorial_basis: string;
    pecuniary_basis: string;
    governing_provisions: string[];
    confidence: string;
    assumptions: string[];
  };
  viable_options: Array<{
    forum_name: string;
    court_category: string;
    territorial_basis: string;
    pecuniary_basis: string;
    governing_provisions: string[];
    confidence: string;
    assumptions: string[];
  }>;
  is_unambiguous: boolean;
  notice: string;
}

/**
 * Shared workspace shell for a single matter -- renders the full Litigation
 * UI (parties, hearing docket, limitation calculator, forum advisor, AI case
 * analysis, chat) when matter.module === "litigation", and a generic chat
 * fallback otherwise. Reused by both /matters/[id] (generic matter route)
 * and /litigation/[matterId] (dedicated Litigation entry route) so the
 * implementation only exists once.
 */
export function MatterWorkspace({ matterId }: { matterId: string }) {
  const [matter, setMatter] = useState<Matter | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "facts" | "hearings" | "analysis" | "chat" | "pleading">("overview");
  const [messages, setMessages] = useState<Message[]>([]);
  const [parties, setParties] = useState<PartyItem[]>([]);
  const [facts, setFacts] = useState<FactItem[]>([]);
  const [analyses, setAnalyses] = useState<CaseAnalysis[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPartyModal, setShowPartyModal] = useState(false);
  const [showHearingForm, setShowHearingForm] = useState(false);
  const [hearingDate, setHearingDate] = useState("");
  const [hearingPurpose, setHearingPurpose] = useState("");
  const [iaNumber, setIaNumber] = useState("");
  const [limCoaDate, setLimCoaDate] = useState("");
  const [limSuitCategory, setLimSuitCategory] = useState("Money Recovery");
  const [limExclusionDays, setLimExclusionDays] = useState(0);
  const [limCalculating, setLimCalculating] = useState(false);
  const [limResult, setLimResult] = useState<LimitationResult | null>(null);
  const [forumSuitType, setForumSuitType] = useState("Civil Suit");
  const [forumClaimVal, setForumClaimVal] = useState("2500000");
  const [forumState, setForumState] = useState("Delhi");
  const [forumDefState, setForumDefState] = useState("");
  const [forumCalculating, setForumCalculating] = useState(false);
  const [forumResult, setForumResult] = useState<ForumResult | null>(null);
  const [courtTracking, setCourtTracking] = useState<CourtCaseTracking | null>(null);
  const [cnrInput, setCnrInput] = useState("");
  const [cnrPreview, setCnrPreview] = useState<CourtCasePreview | null>(null);
  const [cnrPreviewBusy, setCnrPreviewBusy] = useState(false);
  const [cnrPreviewError, setCnrPreviewError] = useState<string | null>(null);
  const [trackingBusy, setTrackingBusy] = useState(false);
  const [trackedHearings, setTrackedHearings] = useState<CalendarHearing[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchAdvocate, setSearchAdvocate] = useState("");
  const [searchCaseNumber, setSearchCaseNumber] = useState("");
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<CourtCaseSearchItem[] | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function loadData() {
    try {
      const m = await getMatter(matterId);
      setMatter(m);
      if (m.module === "litigation") {
        const [pList, fList, aList, tracking, trackedHearingsList] = await Promise.all([
          listParties(matterId).catch(() => []),
          listEvidence(matterId).catch(() => []),
          listCaseAnalyses(matterId).catch(() => []),
          getCourtTracking(matterId).catch(() => null),
          listCalendarHearings({ matter_id: matterId }).catch(() => []),
        ]);
        setParties(pList);
        setFacts(fList);
        setAnalyses(aList);
        setCourtTracking(tracking);
        setCnrInput(tracking?.cnr_number || "");
        setTrackedHearings(trackedHearingsList);
      }
      setMessages(await listMessages(matterId).catch(() => []));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setBusy(true);
    setError(null);
    const content = draft;
    setDraft("");
    try {
      const [userMsg, assistantMsg] = await sendMessage(matterId, content);
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setDraft(content);
    } finally {
      setBusy(false);
    }
  }

  async function handleAddParty(partyData: Record<string, unknown>) {
    const newParty = (await addParty(matterId, partyData)) as PartyItem;
    setParties((prev) => [...prev, newParty]);
  }

  async function handleDeleteParty(partyId: string) {
    await deleteParty(matterId, partyId);
    setParties((prev) => prev.filter((p) => p.id !== partyId));
  }

  async function handleAddFact(factData: Record<string, unknown>) {
    const newFact = (await addEvidence(matterId, factData)) as FactItem;
    setFacts((prev) => [...prev, newFact]);
  }

  async function handleUploadEvidenceFile(
    file: File,
    fields: { event_date?: string; exhibit_number?: string; document_title?: string; relevance_notes?: string }
  ) {
    const newFact = (await uploadEvidenceFile(matterId, file, fields)) as FactItem;
    setFacts((prev) => [...prev, newFact]);
  }

  async function handleDeleteFact(factId: string) {
    await deleteEvidence(matterId, factId);
    setFacts((prev) => prev.filter((f) => f.id !== factId));
  }

  async function handleAddHearing(e: React.FormEvent) {
    e.preventDefault();
    if (!hearingDate) return;
    try {
      // Canonical public.hearings, source='manual' -- same table/entity
      // Court Tracking (eCourts), the Calendar page, and Hearing
      // Intelligence all read from, so a hearing logged here is
      // immediately visible in all three (see matter-workspace.tsx's
      // "Tracked Hearings" list and /hearings/[hearingId]). The form
      // still only asks for a date; 10:30 is the same default hour the
      // Calendar page's own "Schedule Hearing Date" dialog uses.
      const newH = await createCalendarHearing({
        matter_id: matterId,
        title: hearingPurpose.trim() || `Hearing — ${matter?.title || "Matter"}`,
        hearing_at: new Date(`${hearingDate}T10:30:00`).toISOString(),
        notes: iaNumber.trim() ? `IA Number: ${iaNumber.trim()}` : undefined,
      });
      setTrackedHearings((prev) => [...prev, newH]);
      setHearingDate("");
      setHearingPurpose("");
      setIaNumber("");
      setShowHearingForm(false);
    } catch (err) {
      console.error("Failed to add hearing", err);
    }
  }

  async function handleSearchCnr(e: React.FormEvent) {
    e.preventDefault();
    if (!cnrInput.trim()) return;
    setCnrPreviewBusy(true);
    setCnrPreviewError(null);
    setCnrPreview(null);
    try {
      const preview = await previewCourtCase(cnrInput.trim());
      setCnrPreview(preview);
    } catch (err) {
      setCnrPreviewError(err instanceof Error ? err.message : String(err));
    } finally {
      setCnrPreviewBusy(false);
    }
  }

  async function handleSaveCnr() {
    if (!cnrPreview) return;
    setTrackingBusy(true);
    setError(null);
    try {
      const updated = await updateCourtTracking(matterId, { cnr_number: cnrPreview.cnr });
      setCourtTracking(updated);
      setCnrPreview(null);
      setCnrPreviewError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTrackingBusy(false);
    }
  }

  async function handleToggleTracking(enabled: boolean) {
    setTrackingBusy(true);
    setError(null);
    try {
      const updated = await updateCourtTracking(matterId, { tracking_enabled: enabled });
      setCourtTracking(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTrackingBusy(false);
    }
  }

  async function handleSyncNow() {
    setTrackingBusy(true);
    setError(null);
    try {
      const updated = await triggerCourtSync(matterId);
      setCourtTracking(updated);
      const [hList, pList, fList] = await Promise.all([
        listCalendarHearings({ matter_id: matterId }).catch(() => []),
        listParties(matterId).catch(() => []),
        listEvidence(matterId).catch(() => []),
      ]);
      setTrackedHearings(hList);
      setParties(pList);
      setFacts(fList);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTrackingBusy(false);
    }
  }

  async function handleSearchCourtCases(e: React.FormEvent) {
    e.preventDefault();
    if (!searchAdvocate.trim() && !searchCaseNumber.trim()) {
      setSearchError("Enter an advocate name or a case number to search.");
      return;
    }
    setSearchBusy(true);
    setSearchError(null);
    setSearchResults(null);
    try {
      const result = await searchCourtCases({
        advocates: searchAdvocate.trim() ? [searchAdvocate.trim()] : undefined,
        case_numbers: searchCaseNumber.trim() ? [searchCaseNumber.trim()] : undefined,
      });
      setSearchResults(result.items);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : String(err));
    } finally {
      setSearchBusy(false);
    }
  }

  async function handleUseSearchResult(cnr: string) {
    setTrackingBusy(true);
    setError(null);
    try {
      const updated = await updateCourtTracking(matterId, { cnr_number: cnr });
      setCourtTracking(updated);
      setSearchOpen(false);
      setSearchResults(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTrackingBusy(false);
    }
  }

  const isLitigation = matter?.module === "litigation";

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        {/* Matter Header Banner */}
        <div className="flex flex-col gap-2 rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-xs bg-[#081534] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-white">
                {matter?.module || "MATTER"}
              </span>
              {matter?.court_category && (
                <span className="rounded-xs border border-[#C6C6CF] bg-[#F0EEE9] px-2 py-0.5 font-sans text-[10px] font-semibold text-[#081534]">
                  {matter.court_category} ({matter.jurisdiction_state || "India"})
                </span>
              )}
            </div>
            <h1 className="mt-1 font-sans text-xl font-semibold tracking-tight text-[#081534]">
              {matter?.title || "Loading Matter..."}
            </h1>
            <p className="font-serif text-xs text-[#45464E]">
              Client: {matter?.client_name || "Unspecified Client"} | CNR: {matter?.cnr_number || "Not Registered"}
            </p>
          </div>

          {isLitigation && (
            <div className="flex items-center gap-2">
              <Button
                onClick={() => setShowPartyModal(true)}
                className="h-8 gap-1.5 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
              >
                <UserPlus className="h-3.5 w-3.5" />
                Add Party
              </Button>
            </div>
          )}
        </div>

        {error && (
          <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]">
            {error}
          </div>
        )}

        {isLitigation ? (
          <div className="space-y-4">
            {/* Sub-Navigation Tabs */}
            <div className="flex border-b border-[#E4E2DD] font-sans text-xs font-semibold">
              <button
                onClick={() => setActiveTab("overview")}
                className={cn(
                  "px-4 py-2 border-b-2 font-medium transition-colors",
                  activeTab === "overview"
                    ? "border-[#081534] text-[#081534]"
                    : "border-transparent text-[#76777F] hover:text-[#1A1A1A]"
                )}
              >
                Case Overview & Parties
              </button>
              <button
                onClick={() => setActiveTab("facts")}
                className={cn(
                  "px-4 py-2 border-b-2 font-medium transition-colors",
                  activeTab === "facts"
                    ? "border-[#081534] text-[#081534]"
                    : "border-transparent text-[#76777F] hover:text-[#1A1A1A]"
                )}
              >
                Facts & Exhibits ({facts.length})
              </button>
              <button
                onClick={() => setActiveTab("hearings")}
                className={cn(
                  "px-4 py-2 border-b-2 font-medium transition-colors",
                  activeTab === "hearings"
                    ? "border-[#081534] text-[#081534]"
                    : "border-transparent text-[#76777F] hover:text-[#1A1A1A]"
                )}
              >
                Hearing Docket ({trackedHearings.length})
              </button>
              <button
                onClick={() => setActiveTab("analysis")}
                className={cn(
                  "flex items-center gap-1 px-4 py-2 border-b-2 font-medium transition-colors",
                  activeTab === "analysis"
                    ? "border-[#081534] text-[#081534]"
                    : "border-transparent text-[#76777F] hover:text-[#1A1A1A]"
                )}
              >
                <Sparkles className="h-3 w-3" />
                AI Case Analysis
              </button>
              <button
                onClick={() => setActiveTab("chat")}
                className={cn(
                  "px-4 py-2 border-b-2 font-medium transition-colors",
                  activeTab === "chat"
                    ? "border-[#081534] text-[#081534]"
                    : "border-transparent text-[#76777F] hover:text-[#1A1A1A]"
                )}
              >
                AI Research Assistant
              </button>
              <button
                onClick={() => setActiveTab("pleading")}
                className={cn(
                  "flex items-center gap-1 px-4 py-2 border-b-2 font-medium transition-colors",
                  activeTab === "pleading"
                    ? "border-[#081534] text-[#081534]"
                    : "border-transparent text-[#76777F] hover:text-[#1A1A1A]"
                )}
              >
                <FileText className="h-3 w-3" />
                Pleading Workbench
              </button>
            </div>

            {/* Tab 1: Overview & Parties */}
            {activeTab === "overview" && (
              <div className="grid grid-cols-1 gap-6 md:grid-cols-12">
                <div className="space-y-4 md:col-span-8">
                  <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-4">
                    <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
                      Litigation Parties ({parties.length})
                    </h3>

                    {parties.length === 0 ? (
                      <p className="font-serif text-xs text-[#76777F]">
                        No parties added yet. Click &quot;Add Party&quot; above to list Petitioners, Respondents, or Opposing Counsel.
                      </p>
                    ) : (
                      <div className="divide-y divide-[#E4E2DD]">
                        {parties.map((p) => (
                          <div key={p.id} className="flex items-center justify-between py-2.5 font-sans text-xs">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="rounded-xs bg-[#F0EEE9] px-1.5 py-0.5 text-[10px] font-bold text-[#081534]">
                                  {p.party_type} #{p.party_number}
                                </span>
                                <span className="font-semibold text-[#1A1A1A]">{p.party_name}</span>
                              </div>
                              {p.address && <p className="mt-0.5 font-serif text-[11px] text-[#45464E]">{p.address}</p>}
                              {p.advocate_name && (
                                <p className="font-serif text-[11px] text-[#76777F]">Counsel: {p.advocate_name}</p>
                              )}
                            </div>
                            <button
                              onClick={() => handleDeleteParty(p.id)}
                              className="text-[#76777F] hover:text-[#7A2A2A]"
                              title="Delete Party"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-4 md:col-span-4">
                  <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
                    <h4 className="font-semibold uppercase tracking-wider text-[#081534]">Docket Summary</h4>
                    <div className="space-y-1.5 text-[#45464E]">
                      <p><strong className="text-[#081534]">Forum:</strong> {matter?.court_category || "Unspecified"}</p>
                      <p><strong className="text-[#081534]">State:</strong> {matter?.jurisdiction_state || "Unspecified"}</p>
                      <p><strong className="text-[#081534]">Case No:</strong> {matter?.case_number_formatted || "Pending"}</p>
                      <p><strong className="text-[#081534]">CNR:</strong> {matter?.cnr_number || "Not Assigned"}</p>
                    </div>
                  </div>

                  {/* Court Tracking / CNR (Litigation Intelligence + eCourts, 27 Aug 2026) --
                      extends this existing screen rather than a new one, per the
                      "reuse before creating" rule; CNR belongs to the Matter. */}
                  <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
                    <div className="flex items-center justify-between border-b border-[#E4E2DD] pb-2">
                      <div className="flex items-center gap-2">
                        <Radar className="h-4 w-4 text-[#081534]" />
                        <h4 className="font-semibold uppercase tracking-wider text-[#081534]">Court Tracking</h4>
                      </div>
                      <a
                        href={`/litigation/${matterId}/case-details`}
                        className="font-serif text-[10px] text-[#081534] underline underline-offset-2"
                      >
                        Case Intelligence &rarr;
                      </a>
                    </div>

                    <form onSubmit={handleSearchCnr} className="space-y-2">
                      <label className="font-semibold text-[#081534]">CNR Number</label>
                      <div className="flex gap-1.5">
                        <input
                          type="text"
                          placeholder="e.g. DLND020047882015"
                          value={cnrInput}
                          onChange={(e) => {
                            setCnrInput(e.target.value);
                            // Typing after a preview invalidates it -- never let a
                            // stale preview (for a DIFFERENT CNR than what's now in
                            // the box) be what "Save & Track" ends up saving.
                            setCnrPreview(null);
                            setCnrPreviewError(null);
                          }}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        />
                        <Button
                          type="submit"
                          disabled={cnrPreviewBusy || !cnrInput.trim()}
                          size="sm"
                          variant="outline"
                          className="h-8 shrink-0 rounded-sm border-[#081534] px-3 font-sans text-[11px] font-semibold text-[#081534]"
                        >
                          {cnrPreviewBusy ? "Searching..." : "Search"}
                        </Button>
                      </div>
                    </form>

                    {cnrPreviewError && (
                      <p className="font-serif text-[10px] text-[#7A2A2A]">{cnrPreviewError}</p>
                    )}

                    {cnrPreview && (
                      <div className="space-y-1.5 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
                        <p className="font-semibold text-[#081534]">
                          {[...cnrPreview.petitioners, ...cnrPreview.respondents].join(" vs ") || "Parties unknown"}
                        </p>
                        <p className="font-serif text-[10px] text-[#76777F]">
                          {cnrPreview.court_name || "Court unknown"}
                          {cnrPreview.status ? ` · ${cnrPreview.status}` : ""}
                          {cnrPreview.judge ? ` · ${cnrPreview.judge}` : ""}
                        </p>
                        <div className="flex gap-1.5">
                          <Button
                            type="button"
                            size="sm"
                            disabled={trackingBusy}
                            onClick={handleSaveCnr}
                            className="h-7 rounded-sm bg-[#081534] px-3 font-sans text-[11px] font-semibold text-white hover:bg-[#1E2A4A]"
                          >
                            {trackingBusy ? "Saving..." : "Looks right — Save & Track"}
                          </Button>
                          <button
                            type="button"
                            onClick={() => setCnrPreview(null)}
                            className="font-serif text-[10px] text-[#76777F] underline underline-offset-2"
                          >
                            Discard
                          </button>
                        </div>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => setSearchOpen((v) => !v)}
                      className="font-serif text-[11px] text-[#081534] underline underline-offset-2"
                    >
                      {searchOpen ? "Hide eCourts search" : "Don't know the CNR? Search by advocate or case number"}
                    </button>

                    {searchOpen && (
                      <div className="space-y-2 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
                        <form onSubmit={handleSearchCourtCases} className="space-y-1.5">
                          <input
                            type="text"
                            placeholder="Advocate name"
                            value={searchAdvocate}
                            onChange={(e) => setSearchAdvocate(e.target.value)}
                            className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                          />
                          <input
                            type="text"
                            placeholder="Case number, e.g. CS 1/2026"
                            value={searchCaseNumber}
                            onChange={(e) => setSearchCaseNumber(e.target.value)}
                            className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                          />
                          <Button
                            type="submit"
                            disabled={searchBusy}
                            size="sm"
                            className="h-8 w-full rounded-sm bg-[#081534] font-sans text-[11px] font-semibold text-white hover:bg-[#1E2A4A]"
                          >
                            {searchBusy ? "Searching..." : "Search eCourts"}
                          </Button>
                        </form>

                        {searchError && <p className="font-serif text-[10px] text-[#7A2A2A]">{searchError}</p>}

                        {searchResults && searchResults.length === 0 && !searchError && (
                          <p className="font-serif text-[10px] text-[#76777F]">No matching cases found.</p>
                        )}

                        {searchResults && searchResults.length > 0 && (
                          <div className="space-y-1.5 border-t border-[#E4E2DD] pt-1.5">
                            {searchResults.map((item, i) => (
                              <div key={item.cnr || i} className="rounded-sm border border-[#E4E2DD] bg-white p-1.5">
                                <p className="font-semibold text-[#081534]">
                                  {item.case_number || "Case number unknown"}
                                  {item.court_name ? ` · ${item.court_name}` : ""}
                                </p>
                                <p className="font-serif text-[10px] text-[#76777F]">
                                  {[...item.petitioners, ...item.respondents].join(" vs ") || "Parties unknown"}
                                  {item.advocates.length > 0 ? ` · Adv. ${item.advocates.join(", ")}` : ""}
                                </p>
                                {item.cnr ? (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="outline"
                                    disabled={trackingBusy}
                                    onClick={() => handleUseSearchResult(item.cnr as string)}
                                    className="mt-1 h-6 rounded-sm border-[#E4E2DD] px-2 font-sans text-[10px] font-semibold text-[#081534]"
                                  >
                                    Use this CNR
                                  </Button>
                                ) : (
                                  <p className="mt-1 font-serif text-[10px] text-[#76777F]">No CNR returned for this result.</p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={courtTracking?.tracking_enabled || false}
                        disabled={trackingBusy || !courtTracking?.cnr_number}
                        onChange={(e) => handleToggleTracking(e.target.checked)}
                        className="rounded border-[#E4E2DD]"
                      />
                      <span className="text-[#45464E]">
                        Enable automated eCourts tracking
                        {!courtTracking?.cnr_number && " (enter a CNR first)"}
                      </span>
                    </label>

                    {courtTracking?.tracking_enabled && (
                      <div className="space-y-1.5 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
                        <div className="flex items-center justify-between">
                          <span
                            className={cn(
                              "rounded-xs px-1.5 py-0.5 text-[10px] font-bold uppercase",
                              courtTracking.sync_status === "synced" && "bg-[#D4EDDA] text-[#155724]",
                              courtTracking.sync_status === "error" && "bg-[#FFF5F5] text-[#7A2A2A]",
                              (courtTracking.sync_status === "idle" || courtTracking.sync_status === "syncing") &&
                                "bg-[#F0EEE9] text-[#45464E]"
                            )}
                          >
                            {courtTracking.sync_status}
                          </span>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={trackingBusy}
                            onClick={handleSyncNow}
                            className="h-7 gap-1 rounded-sm border-[#E4E2DD] px-2 font-sans text-[11px] font-semibold text-[#081534]"
                          >
                            <RefreshCw className="h-3 w-3" />
                            {trackingBusy ? "Syncing..." : "Sync Now"}
                          </Button>
                        </div>
                        {courtTracking.last_synced_at && (
                          <p className="font-serif text-[10px] text-[#76777F]">
                            Last synced: {new Date(courtTracking.last_synced_at).toLocaleString()}
                          </p>
                        )}
                        {courtTracking.last_error && (
                          <p className="font-serif text-[10px] text-[#7A2A2A]">{courtTracking.last_error}</p>
                        )}
                      </div>
                    )}

                    {trackedHearings.length > 0 && (
                      <div className="space-y-1 border-t border-[#E4E2DD] pt-2">
                        <p className="font-semibold text-[#081534]">Tracked Hearings</p>
                        {trackedHearings.map((h) => (
                          <a
                            key={h.id}
                            href={`/hearings/${h.id}?matterId=${matterId}`}
                            className="block rounded-sm px-1.5 py-1 hover:bg-[#F0EEE9]"
                          >
                            <span className="font-medium text-[#1A1A1A]">
                              {new Date(h.hearing_at).toLocaleDateString()}
                            </span>
                            {h.court && <span className="text-[#76777F]"> — {h.court}</span>}
                            {h.bench && <span className="text-[#76777F]">, {h.bench}</span>}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Limitation Intelligence Assistant (Sprint 3.5.2A) */}
                  <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
                    <div className="flex items-center gap-2 border-b border-[#E4E2DD] pb-2">
                      <Clock className="h-4 w-4 text-[#081534]" />
                      <h4 className="font-semibold uppercase tracking-wider text-[#081534]">
                        Limitation Calculator
                      </h4>
                    </div>

                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        if (!limCoaDate) return;
                        setLimCalculating(true);
                        try {
                          const res = await calculateLimitation({
                            cause_of_action_date: limCoaDate,
                            suit_category: limSuitCategory,
                            exclusion_days: Number(limExclusionDays) || 0,
                          });
                          setLimResult(res);
                        } catch (err: unknown) {
                          console.error("Limitation calculation error", err);
                        } finally {
                          setLimCalculating(false);
                        }
                      }}
                      className="space-y-2.5"
                    >
                      <div>
                        <label className="font-semibold text-[#081534]">Cause of Action Date</label>
                        <input
                          type="date"
                          required
                          value={limCoaDate}
                          onChange={(e) => setLimCoaDate(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        />
                      </div>

                      <div>
                        <label className="font-semibold text-[#081534]">Suit Category</label>
                        <select
                          value={limSuitCategory}
                          onChange={(e) => setLimSuitCategory(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        >
                          <option value="Money Recovery">Money Recovery (Art 19/20)</option>
                          <option value="Specific Performance">Specific Performance (Art 54)</option>
                          <option value="Possession">Possession of Property (Art 64/65)</option>
                          <option value="Declaratory">Declaratory Suit (Art 58)</option>
                          <option value="Breach of Contract">Breach of Contract (Art 55)</option>
                          <option value="Appeal">Appeal (Art 115/116)</option>
                          <option value="Execution">Execution of Decree (Art 136)</option>
                        </select>
                      </div>

                      <div>
                        <label className="font-semibold text-[#081534]">Exclusion Days (Sec 4-15)</label>
                        <input
                          type="number"
                          min={0}
                          value={limExclusionDays}
                          onChange={(e) => setLimExclusionDays(parseInt(e.target.value) || 0)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        />
                      </div>

                      <Button
                        type="submit"
                        disabled={limCalculating}
                        className="h-8 w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
                      >
                        {limCalculating ? "Calculating..." : "Compute Statutory Limitation"}
                      </Button>
                    </form>

                    {limResult && (
                      <div
                        className={cn(
                          "rounded-sm border p-3 space-y-2 mt-3 font-sans text-xs",
                          limResult.is_barred
                            ? "border-[#F8D7DA] bg-[#FFF5F5] text-[#7A2A2A]"
                            : "border-[#C3E6CB] bg-[#D4EDDA] text-[#155724]"
                        )}
                      >
                        <div className="flex items-center justify-between font-bold">
                          <span>{limResult.is_barred ? "STATUTORY BARRED" : "WITHIN LIMITATION"}</span>
                          <span className="rounded-xs bg-white px-1.5 py-0.5 text-[10px] border border-[#E4E2DD]">
                            {limResult.days_remaining} days {limResult.is_barred ? "past" : "remaining"}
                          </span>
                        </div>

                        <p className="font-serif text-[11px]">
                          <strong>Expiry Date:</strong> {limResult.limitation_expiry_date}
                        </p>
                        <p className="font-serif text-[11px]">
                          <strong>Governing Provision:</strong> {limResult.primary_article.article_number} ({limResult.primary_article.description})
                        </p>

                        <p className="font-serif text-[11px] leading-relaxed italic border-t border-black/10 pt-1.5">
                          {limResult.condonation_notes}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Forum & Jurisdiction Intelligence Assistant (Sprint 3.5.2B) */}
                  <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
                    <div className="flex items-center gap-2 border-b border-[#E4E2DD] pb-2">
                      <Gavel className="h-4 w-4 text-[#081534]" />
                      <h4 className="font-semibold uppercase tracking-wider text-[#081534]">
                        Forum & Jurisdiction Advisor
                      </h4>
                    </div>

                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        setForumCalculating(true);
                        try {
                          const res = await determineForum({
                            suit_type: forumSuitType,
                            claim_value_inr: Number(forumClaimVal) || 0,
                            jurisdiction_state: forumState,
                            defendant_residence_state: forumDefState || undefined,
                          });
                          setForumResult(res);
                        } catch (err: unknown) {
                          console.error("Forum advisor error", err);
                        } finally {
                          setForumCalculating(false);
                        }
                      }}
                      className="space-y-2.5"
                    >
                      <div>
                        <label className="font-semibold text-[#081534]">Dispute / Suit Type</label>
                        <select
                          value={forumSuitType}
                          onChange={(e) => setForumSuitType(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        >
                          <option value="Civil Suit">Civil Suit</option>
                          <option value="Property Dispute">Property Dispute</option>
                          <option value="Commercial Dispute">Commercial Dispute</option>
                          <option value="RERA">RERA Real Estate Dispute</option>
                        </select>
                      </div>

                      <div>
                        <label className="font-semibold text-[#081534]">Claim Value (INR)</label>
                        <input
                          type="number"
                          min={0}
                          value={forumClaimVal}
                          onChange={(e) => setForumClaimVal(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        />
                      </div>

                      <div>
                        <label className="font-semibold text-[#081534]">Primary State Jurisdiction</label>
                        <select
                          value={forumState}
                          onChange={(e) => setForumState(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        >
                          <option value="Delhi">Delhi</option>
                          <option value="Maharashtra">Maharashtra</option>
                          <option value="Karnataka">Karnataka</option>
                          <option value="Tamil Nadu">Tamil Nadu</option>
                          <option value="DEFAULT">Other / State Default</option>
                        </select>
                      </div>

                      <div>
                        <label className="font-semibold text-[#081534]">Defendant Residence State (Optional)</label>
                        <input
                          type="text"
                          placeholder="e.g. Maharashtra"
                          value={forumDefState}
                          onChange={(e) => setForumDefState(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs text-[#1A1A1A]"
                        />
                      </div>

                      <Button
                        type="submit"
                        disabled={forumCalculating}
                        className="h-8 w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
                      >
                        {forumCalculating ? "Analyzing Jurisdiction..." : "Analyze Jurisdiction & Forum"}
                      </Button>
                    </form>

                    {forumResult && (
                      <div className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3 space-y-2 mt-3 font-sans text-xs">
                        <div className="flex items-center justify-between font-bold text-[#081534]">
                          <span>{forumResult.recommended_forum.forum_name}</span>
                          <span
                            className={cn(
                              "rounded-xs px-1.5 py-0.5 text-[10px] uppercase font-bold",
                              forumResult.is_unambiguous
                                ? "bg-[#D4EDDA] text-[#155724]"
                                : "bg-[#FFF3CD] text-[#856404]"
                            )}
                          >
                            {forumResult.recommended_forum.confidence}
                          </span>
                        </div>

                        <p className="font-serif text-[11px] text-[#45464E]">
                          <strong>Category:</strong> {forumResult.recommended_forum.court_category}
                        </p>
                        <p className="font-serif text-[11px] text-[#45464E]">
                          <strong>Territorial Basis:</strong> {forumResult.recommended_forum.territorial_basis}
                        </p>
                        <p className="font-serif text-[11px] text-[#45464E]">
                          <strong>Pecuniary Basis:</strong> {forumResult.recommended_forum.pecuniary_basis}
                        </p>
                        <p className="font-serif text-[11px] text-[#45464E]">
                          <strong>Provisions:</strong> {forumResult.recommended_forum.governing_provisions.join(", ")}
                        </p>

                        {!forumResult.is_unambiguous && (
                          <div className="mt-2 border-t border-[#E4E2DD] pt-2 space-y-1">
                            <span className="font-bold text-[#7A2A2A]">Multiple Viable Forums Identified:</span>
                            {forumResult.viable_options.map((opt, i) => (
                              <p key={i} className="font-serif text-[10px] text-[#45464E]">
                                Option {i + 1}: <strong>{opt.forum_name}</strong> ({opt.territorial_basis})
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Tab 2: Facts & Exhibits */}
            {activeTab === "facts" && (
              <div className="rounded-sm border border-[#E4E2DD] bg-white p-5">
                <LitigationFactTimeline
                  facts={facts}
                  matterId={matterId}
                  onAddFact={handleAddFact}
                  onUploadFile={handleUploadEvidenceFile}
                  onDeleteFact={handleDeleteFact}
                />
              </div>
            )}

            {/* Tab 3: Hearing Docket */}
            {activeTab === "hearings" && (
              <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-4 font-sans text-xs">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
                      Court Hearing Docket
                    </h3>
                    <p className="font-serif text-xs text-[#45464E]">
                      Scheduled court appearances, IA stay motions, and hearing outcomes
                    </p>
                  </div>
                  <Button
                    onClick={() => setShowHearingForm(!showHearingForm)}
                    className="h-8 gap-1.5 rounded-sm bg-[#081534] text-xs font-semibold text-white hover:bg-[#1E2A4A]"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Log Hearing
                  </Button>
                </div>

                {showHearingForm && (
                  <form onSubmit={handleAddHearing} className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-4 space-y-3">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                      <div>
                        <label className="font-semibold text-[#081534]">Hearing Date *</label>
                        <input
                          type="date"
                          required
                          value={hearingDate}
                          onChange={(e) => setHearingDate(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="font-semibold text-[#081534]">IA Number (Optional)</label>
                        <input
                          type="text"
                          placeholder="e.g. IA 101/2026"
                          value={iaNumber}
                          onChange={(e) => setIaNumber(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs"
                        />
                      </div>
                      <div>
                        <label className="font-semibold text-[#081534]">Purpose of Hearing</label>
                        <input
                          type="text"
                          placeholder="e.g. Admission / Stay Arguments"
                          value={hearingPurpose}
                          onChange={(e) => setHearingPurpose(e.target.value)}
                          className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs"
                        />
                      </div>
                    </div>

                    <div className="flex justify-end gap-2 pt-1">
                      <Button type="button" variant="outline" onClick={() => setShowHearingForm(false)} className="h-7 text-xs">
                        Cancel
                      </Button>
                      <Button type="submit" className="h-7 bg-[#081534] text-xs font-semibold text-white">
                        Save Hearing Log
                      </Button>
                    </div>
                  </form>
                )}

                {trackedHearings.length === 0 ? (
                  <p className="font-serif text-xs text-[#76777F]">No court hearing dates logged yet.</p>
                ) : (
                  <div className="divide-y divide-[#E4E2DD]">
                    {trackedHearings.map((h) => (
                      <a
                        key={h.id}
                        href={`/hearings/${h.id}?matterId=${matterId}`}
                        className="block py-2.5 space-y-1 hover:bg-[#F0EEE9]"
                      >
                        <div className="flex items-center gap-2 font-semibold text-[#081534]">
                          <Calendar className="h-3.5 w-3.5 text-[#081534]" />
                          <span>{new Date(h.hearing_at).toLocaleDateString()}</span>
                          {h.item_no && (
                            <span className="rounded-xs border border-[#C6C6CF] bg-[#F0EEE9] px-1.5 py-0.5 text-[10px] uppercase text-[#081534]">
                              {h.item_no}
                            </span>
                          )}
                          <span className="text-xs text-[#45464E]">- {h.title || "Scheduled Hearing"}</span>
                        </div>
                        {(h.court || h.bench) && (
                          <p className="pl-5.5 font-serif text-[11px] text-[#76777F]">
                            {[h.court, h.bench].filter(Boolean).join(" · ")}
                          </p>
                        )}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 4: AI Case Analysis */}
            {activeTab === "analysis" && (
                <LitigationCaseAnalysis
                  matterId={matterId}
                  hasParties={parties.length > 0}
                  hasFacts={facts.length > 0}
                  limitationSnapshot={limResult}
                  forumSnapshot={
                    forumResult
                      ? { recommended_forum: forumResult.recommended_forum, is_unambiguous: forumResult.is_unambiguous }
                      : null
                  }
                  onAnalysisGenerated={(newAnalysis) => {
                    setAnalyses((prev) => {
                      const filtered = prev.filter((item) => item.id !== newAnalysis.id);
                      return [newAnalysis, ...filtered];
                    });
                  }}
                />
            )}

            {/* Tab 5: AI Research Chat */}
            {activeTab === "chat" && (
              <div className="flex h-[60vh] flex-col rounded-sm border border-[#E4E2DD] bg-white p-4">
                <div className="flex-1 space-y-3 overflow-y-auto p-2">
                  {messages.length === 0 && (
                    <div className="text-center py-8 text-xs font-sans text-[#76777F]">
                      Ask the AI Research Assistant about statutory provisions, court procedures, limitation periods, or legal grounds relevant to this matter.
                    </div>
                  )}
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={cn(
                        "max-w-[80%] rounded-sm px-3 py-2 text-xs font-sans whitespace-pre-wrap leading-relaxed",
                        m.role === "user"
                          ? "ml-auto bg-[#081534] text-white"
                          : "bg-[#F0EEE9] text-[#1A1A1A]"
                      )}
                    >
                      <div>{m.content}</div>
                    </div>
                  ))}
                  {busy && (
                    <div className="max-w-[80%] rounded-sm px-3 py-2 text-xs font-sans bg-[#F0EEE9] text-[#76777F] animate-pulse flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5 animate-spin text-[#081534]" />
                      <span>AI Assistant is researching and drafting response...</span>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>
                <form onSubmit={handleSend} className="mt-3 flex gap-2">
                  <input
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder="Ask AI litigation assistant statutory or procedural questions..."
                    className="flex-1 rounded-sm border border-[#E4E2DD] px-3 text-xs"
                    disabled={busy}
                  />
                  <Button type="submit" disabled={busy || !draft.trim()} className="h-9 bg-[#081534] text-xs font-semibold text-white">
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                </form>
              </div>
            )}
            {/* Tab 6: Pleading Workbench */}
            {activeTab === "pleading" && (
              <LitigationPleadingWorkbench
                matterId={matterId}
                latestCaseAnalysis={analyses.length > 0 ? analyses[0] : null}
              />
            )}
          </div>
        ) : (
          /* Default Contracts Chat View */
          <div className="flex h-[75vh] flex-col">
            <div className="flex-1 space-y-3 overflow-y-auto rounded-md border bg-background p-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={cn(
                    "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                    m.role === "user"
                      ? "ml-auto bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  <div>{m.content}</div>
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
            <form onSubmit={handleSend} className="mt-3 flex gap-2">
              <Textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type a fact pattern or question…"
                className="flex-1"
                rows={2}
              />
              <Button type="submit" disabled={busy}>
                Send
              </Button>
            </form>
          </div>
        )}
      </div>

      <LitigationPartyModal
        isOpen={showPartyModal}
        onClose={() => setShowPartyModal(false)}
        onSubmit={handleAddParty}
      />
    </AuthedShell>
  );
}
