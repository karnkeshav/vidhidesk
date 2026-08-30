"use client";

import { useState } from "react";
import Link from "next/link";
import { AuthedShell, useHearings, useMatters } from "@/components/authed-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Calendar as CalendarIcon,
  Gavel,
  Plus,
  Clock,
  MapPin,
  Search,
  ChevronLeft,
  ChevronRight,
  Pencil,
  Trash2,
  Sparkles,
} from "lucide-react";
import {
  createCalendarHearing,
  updateCalendarHearing,
  deleteCalendarHearing,
  CalendarHearing,
  CalendarHearingInput,
} from "@/lib/api";

const NO_MATTER = "none";

// Local calendar day, not UTC (toISOString() is UTC) -- a hearing_at from
// the backend, "today", and the grid's local-midnight Date objects must
// all bucket by the advocate's own wall-clock day, or the selected/today
// highlight and a hearing's day silently disagree by one day for anyone
// west of UTC (confirmed live: grid highlighted the 26th while the page's
// own "Tuesday, Aug 25" header -- built from toLocaleDateString, i.e.
// local time -- was correct).
function dateKey(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function toDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

type FormState = {
  title: string;
  matter_id: string;
  case_no: string;
  court: string;
  bench: string;
  item_no: string;
  stage: string;
  hearing_at_local: string;
  notes: string;
};

function emptyForm(defaultDate: Date): FormState {
  const d = new Date(defaultDate);
  d.setHours(10, 30, 0, 0);
  return {
    title: "",
    matter_id: NO_MATTER,
    case_no: "",
    court: "",
    bench: "",
    item_no: "",
    stage: "",
    hearing_at_local: toDatetimeLocalValue(d.toISOString()),
    notes: "",
  };
}

function formFromHearing(h: CalendarHearing): FormState {
  return {
    title: h.title,
    matter_id: h.matter_id ?? NO_MATTER,
    case_no: h.case_no ?? "",
    court: h.court ?? "",
    bench: h.bench ?? "",
    item_no: h.item_no ?? "",
    stage: h.stage ?? "",
    hearing_at_local: toDatetimeLocalValue(h.hearing_at),
    notes: h.notes ?? "",
  };
}

// Rendered strictly inside <AuthedShell> (see CalendarPage below) so that
// useHearings()/useMatters() resolve against HearingsContext/MattersContext's
// real Provider (mounted by AuthedShell around its own children) instead of
// each context's default empty value. useContext() resolves against
// ancestors of the calling component's own position in the tree -- a
// component cannot consume a context that only becomes an ancestor because
// of JSX it itself passes down as children (the bug this split fixes: this
// logic used to live directly in CalendarPage, which called useHearings()
// in its own render, one level *above* where AuthedShell -- and therefore
// the Provider -- actually mounts).
function CalendarContent() {
  const { hearings, refetchHearings } = useHearings();
  const { matters } = useMatters();

  const [selectedDate, setSelectedDate] = useState(new Date());
  const [monthCursor, setMonthCursor] = useState(new Date());
  const [searchQuery, setSearchQuery] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingHearing, setEditingHearing] = useState<CalendarHearing | null>(null);
  const [form, setForm] = useState<FormState>(() => emptyForm(new Date()));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hearingsByDay = new Map<string, CalendarHearing[]>();
  for (const h of hearings) {
    const key = dateKey(new Date(h.hearing_at));
    const list = hearingsByDay.get(key) ?? [];
    list.push(h);
    hearingsByDay.set(key, list);
  }

  const selectedDayHearings = (hearingsByDay.get(dateKey(selectedDate)) ?? [])
    .slice()
    .sort((a, b) => new Date(a.hearing_at).getTime() - new Date(b.hearing_at).getTime());

  const filteredHearings = selectedDayHearings.filter(
    (h) =>
      h.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (h.case_no ?? "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (h.court ?? "").toLowerCase().includes(searchQuery.toLowerCase())
  );

  function openCreateDialog() {
    setEditingHearing(null);
    setForm(emptyForm(selectedDate));
    setError(null);
    setDialogOpen(true);
  }

  function openEditDialog(h: CalendarHearing) {
    setEditingHearing(h);
    setForm(formFromHearing(h));
    setError(null);
    setDialogOpen(true);
  }

  async function handleSubmit() {
    if (!form.title.trim()) {
      setError("Case title is required.");
      return;
    }
    if (!form.hearing_at_local) {
      setError("Hearing date & time is required.");
      return;
    }
    setSaving(true);
    setError(null);
    const input: CalendarHearingInput = {
      title: form.title.trim(),
      matter_id: form.matter_id === NO_MATTER ? null : form.matter_id,
      case_no: form.case_no.trim() || null,
      court: form.court.trim() || null,
      bench: form.bench.trim() || null,
      item_no: form.item_no.trim() || null,
      stage: form.stage.trim() || null,
      hearing_at: new Date(form.hearing_at_local).toISOString(),
      notes: form.notes.trim() || null,
    };
    try {
      if (editingHearing) {
        await updateCalendarHearing(editingHearing.id, input);
      } else {
        await createCalendarHearing(input);
      }
      refetchHearings();
      setDialogOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(h: CalendarHearing) {
    if (!window.confirm(`Remove "${h.title}" from the calendar?`)) return;
    try {
      await deleteCalendarHearing(h.id);
      refetchHearings();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  // Month grid: plain Date math, no date library dependency.
  const monthStart = new Date(monthCursor.getFullYear(), monthCursor.getMonth(), 1);
  const monthLabel = monthStart.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const firstWeekday = monthStart.getDay();
  const daysInMonth = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 0).getDate();
  const gridDays: (Date | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => new Date(monthCursor.getFullYear(), monthCursor.getMonth(), i + 1)),
  ];
  const today = new Date();

  return (
    <>
      <div className="space-y-6">
        {/* Page Title Banner */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534] md:text-2xl">
              Advocate Cause List & Calendar
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Track court room dockets, hearing dates, and statutory filing deadlines.
            </p>
          </div>
          <Button
            onClick={openCreateDialog}
            className="h-10 gap-2 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]"
          >
            <Plus className="h-4 w-4" strokeWidth={1.5} />
            Schedule Hearing Date
          </Button>
        </div>

        {error && (
          <div className="rounded-sm border border-[#7A2A2A] bg-[#FBEAEA] px-4 py-2 font-sans text-xs text-[#7A2A2A]">
            {error}
          </div>
        )}

        {/* Cause List Calendar & Schedule Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Main Hearing Dockets Table (8 Columns) */}
          <div className="space-y-4 lg:col-span-8">
            <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <Gavel className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                  <span className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                    Listed Court Appearances (
                    {selectedDate.toLocaleDateString(undefined, {
                      weekday: "long",
                      day: "numeric",
                      month: "short",
                      year: "numeric",
                    })}
                    )
                  </span>
                </div>
                <div className="relative w-full sm:w-60">
                  <Search
                    className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#76777F]"
                    strokeWidth={1.5}
                  />
                  <Input
                    type="text"
                    placeholder="Search hearings or cases..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-8 rounded-sm border-[#E4E2DD] bg-white pl-8 font-serif text-xs text-[#1A1A1A]"
                  />
                </div>
              </div>
            </Card>

            <div className="space-y-3">
              {filteredHearings.length === 0 && (
                <Card className="rounded-sm border border-dashed border-[#E4E2DD] bg-[#FBF9F4] p-6 text-center shadow-none">
                  <p className="font-serif text-xs text-[#76777F]">
                    No hearings scheduled for this date.
                  </p>
                </Card>
              )}
              {filteredHearings.map((h) => (
                <Card
                  key={h.id}
                  className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none transition-all hover:border-[#081534]"
                >
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        {h.case_no && (
                          <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-[#081534]">
                            {h.case_no}
                          </span>
                        )}
                        {h.item_no && (
                          <span className="rounded-sm bg-[#1E2A4A] px-2 py-0.5 font-sans text-[10px] font-semibold text-white">
                            {h.item_no}
                          </span>
                        )}
                      </div>
                      <h3 className="font-serif text-base font-medium text-[#1A1A1A]">{h.title}</h3>
                      {h.court && (
                        <div className="flex items-center gap-1.5 font-sans text-xs text-[#45464E]">
                          <MapPin className="h-3.5 w-3.5 text-[#76777F]" />
                          <span>{h.court}</span>
                        </div>
                      )}
                      {h.bench && <p className="font-serif text-xs italic text-[#76777F]">Bench: {h.bench}</p>}
                    </div>

                    <div className="flex flex-col items-start gap-2 sm:items-end">
                      <div className="flex items-center gap-1 font-sans text-xs font-semibold text-[#7A2A2A]">
                        <Clock className="h-3.5 w-3.5" />
                        <span>
                          {new Date(h.hearing_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      {h.stage && (
                        <span className="rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] px-2 py-1 font-sans text-[11px] font-medium text-[#081534]">
                          Stage: {h.stage}
                        </span>
                      )}
                      <div className="flex items-center gap-2">
                        {h.matter_id && (
                          <Link
                            href={`/hearings/${h.id}?matterId=${h.matter_id}`}
                            className="text-[#45464E] transition-colors hover:text-[#081534]"
                            title="Open Hearing Intelligence Workspace"
                          >
                            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} />
                          </Link>
                        )}
                        <button
                          type="button"
                          onClick={() => openEditDialog(h)}
                          className="text-[#45464E] transition-colors hover:text-[#081534]"
                          title="Edit hearing"
                        >
                          <Pencil className="h-3.5 w-3.5" strokeWidth={1.5} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(h)}
                          className="text-[#45464E] transition-colors hover:text-[#7A2A2A]"
                          title="Remove hearing"
                        >
                          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
                        </button>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* Right Sidebar Calendar Controls (4 Columns) */}
          <div className="space-y-4 lg:col-span-4">
            <Card className="rounded-sm border border-[#E4E2DD] bg-white shadow-none">
              <CardHeader className="border-b border-[#E4E2DD] p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CalendarIcon className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                    <CardTitle className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                      Calendar Month Overview
                    </CardTitle>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() =>
                        setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() - 1, 1))
                      }
                      className="rounded-sm p-0.5 text-[#45464E] hover:bg-[#F0EEE9] hover:text-[#081534]"
                      aria-label="Previous month"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        setMonthCursor(new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 1))
                      }
                      className="rounded-sm p-0.5 text-[#45464E] hover:bg-[#F0EEE9] hover:text-[#081534]"
                      aria-label="Next month"
                    >
                      <ChevronRight className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                </div>
                <CardDescription className="font-serif text-xs text-[#45464E]">{monthLabel}</CardDescription>
              </CardHeader>
              <CardContent className="p-4">
                <div className="grid grid-cols-7 gap-1 text-center">
                  {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                    <span key={i} className="font-sans text-[10px] font-semibold text-[#76777F]">
                      {d}
                    </span>
                  ))}
                  {gridDays.map((d, i) => {
                    if (!d) return <span key={i} />;
                    const key = dateKey(d);
                    const hasHearing = (hearingsByDay.get(key)?.length ?? 0) > 0;
                    const isToday = key === dateKey(today);
                    const isSelected = key === dateKey(selectedDate);
                    return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => setSelectedDate(d)}
                        className={`relative rounded-sm py-1.5 font-sans text-xs transition-colors ${
                          isSelected
                            ? "bg-[#081534] font-semibold text-white"
                            : isToday
                              ? "border border-[#081534] text-[#081534]"
                              : "text-[#1A1A1A] hover:bg-[#F0EEE9]"
                        }`}
                      >
                        {d.getDate()}
                        {hasHearing && (
                          <span
                            className={`absolute bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full ${
                              isSelected ? "bg-white" : "bg-[#7A2A2A]"
                            }`}
                          />
                        )}
                      </button>
                    );
                  })}
                </div>
                <div className="mt-3 rounded-sm border border-dashed border-[#E4E2DD] bg-[#FBF9F4] p-3 text-center">
                  <p className="font-sans text-xs font-semibold text-[#1A1A1A]">
                    {selectedDayHearings.length} Listed Appearance{selectedDayHearings.length === 1 ? "" : "s"} on
                    Selected Date
                  </p>
                  <p className="mt-1 font-serif text-[11px] text-[#76777F]">
                    Click any date to view that day&apos;s hearing dockets.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto rounded-sm">
          <DialogHeader>
            <DialogTitle className="font-sans text-base text-[#081534]">
              {editingHearing ? "Edit Hearing" : "Schedule Hearing Date"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="hearing-title">Case Title *</Label>
              <Input
                id="hearing-title"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Acme Corp vs. Union of India"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="hearing-matter">Linked Matter</Label>
              <Select
                value={form.matter_id}
                onValueChange={(v) => setForm({ ...form, matter_id: v })}
              >
                <SelectTrigger id="hearing-matter">
                  <SelectValue placeholder="No linked matter" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_MATTER}>No linked matter</SelectItem>
                  {matters.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="hearing-case-no">Case No.</Label>
                <Input
                  id="hearing-case-no"
                  value={form.case_no}
                  onChange={(e) => setForm({ ...form, case_no: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="hearing-item-no">Item No.</Label>
                <Input
                  id="hearing-item-no"
                  value={form.item_no}
                  onChange={(e) => setForm({ ...form, item_no: e.target.value })}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="hearing-court">Court</Label>
              <Input
                id="hearing-court"
                value={form.court}
                onChange={(e) => setForm({ ...form, court: e.target.value })}
                placeholder="e.g. Delhi High Court — Court Room 4"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="hearing-bench">Bench</Label>
                <Input
                  id="hearing-bench"
                  value={form.bench}
                  onChange={(e) => setForm({ ...form, bench: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="hearing-stage">Stage</Label>
                <Input
                  id="hearing-stage"
                  value={form.stage}
                  onChange={(e) => setForm({ ...form, stage: e.target.value })}
                  placeholder="e.g. Final Arguments"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="hearing-datetime">Hearing Date & Time *</Label>
              <Input
                id="hearing-datetime"
                type="datetime-local"
                value={form.hearing_at_local}
                onChange={(e) => setForm({ ...form, hearing_at_local: e.target.value })}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="hearing-notes">Notes</Label>
              <Textarea
                id="hearing-notes"
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                rows={2}
              />
            </div>

            {error && <p className="font-sans text-xs text-[#7A2A2A]">{error}</p>}
          </div>

          <DialogFooter>
            <Button
              onClick={handleSubmit}
              disabled={saving}
              className="bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
            >
              {saving ? "Saving…" : editingHearing ? "Save Changes" : "Schedule Hearing"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// Thin wrapper: mounts AuthedShell (and, inside it, HearingsContext.Provider/
// MattersContext.Provider) as a genuine ancestor of CalendarContent, so its
// useHearings()/useMatters() calls resolve against the real, live-fetched
// values rather than each context's default.
export default function CalendarPage() {
  return (
    <AuthedShell wide>
      <CalendarContent />
    </AuthedShell>
  );
}
