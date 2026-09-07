"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { NextHearingAlert } from "@/components/litigation/next-hearing-alert";
import { CaseMetadata } from "@/components/litigation/case-metadata";
import { TimelineView } from "@/components/litigation/timeline-view";
import { OrdersSection } from "@/components/litigation/orders-section";
import { ApplicationsTracker } from "@/components/litigation/applications-tracker";
import { PartiesAndCounsel } from "@/components/litigation/parties-and-counsel";
import {
  Matter,
  CourtCaseTracking,
  CalendarHearing,
  OrderOut,
  CauselistEntry,
  InterlocutoryApplication,
  CaseAdvocate,
  getMatter,
  getCourtTracking,
  listCalendarHearings,
  listOrders,
  addOrder,
  listCauselist,
  listInterlocutoryApplications,
  listCaseAdvocates,
} from "@/lib/api";

/** Case Intelligence workspace for one matter -- consolidates everything
 * court_sync.py and the manual data-entry paths have recorded for a
 * matter's CNR: next hearing, timeline, orders, applications, and
 * counsel. Everything rendered here is real data from real endpoints;
 * ApplicationsTracker/PartiesAndCounsel show an honest empty state where
 * no extraction code exists yet (see those components' own comments). */
export default function CaseDetailsPage() {
  const params = useParams<{ matterId: string }>();
  const matterId = params.matterId;

  const [matter, setMatter] = useState<Matter | null>(null);
  const [tracking, setTracking] = useState<CourtCaseTracking | null>(null);
  const [hearings, setHearings] = useState<CalendarHearing[]>([]);
  const [orders, setOrders] = useState<OrderOut[]>([]);
  const [causelist, setCauselist] = useState<CauselistEntry[]>([]);
  const [applications, setApplications] = useState<InterlocutoryApplication[]>([]);
  const [advocates, setAdvocates] = useState<CaseAdvocate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [m, t, hList, oList, clList, iaList, advList] = await Promise.all([
        getMatter(matterId),
        getCourtTracking(matterId).catch(() => null),
        listCalendarHearings({ matter_id: matterId }).catch(() => []),
        listOrders(matterId).catch(() => []),
        listCauselist(matterId).catch(() => []),
        listInterlocutoryApplications(matterId).catch(() => []),
        listCaseAdvocates(matterId).catch(() => []),
      ]);
      setMatter(m);
      setTracking(t);
      setHearings(hList);
      setOrders(oList);
      setCauselist(clList);
      setApplications(iaList);
      setAdvocates(advList);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId]);

  async function handleAddOrder(input: { order_date?: string; court?: string; raw_text?: string }) {
    const newOrder = await addOrder(matterId, input);
    setOrders((prev) => [newOrder, ...prev]);
  }

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        <div className="flex flex-col gap-2 rounded-sm border border-[#E4E2DD] bg-white p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-xs bg-[#081534] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-white">
                Case Intelligence
              </span>
            </div>
            <h1 className="mt-1 font-sans text-xl font-semibold tracking-tight text-[#081534]">
              {matter?.title || "Loading Matter..."}
            </h1>
          </div>
          <a
            href={`/litigation/${matterId}`}
            className="font-serif text-xs text-[#081534] underline underline-offset-2"
          >
            &larr; Back to Matter Workspace
          </a>
        </div>

        {error && (
          <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]">
            {error}
          </div>
        )}

        {loading ? (
          <p className="font-serif text-xs text-[#76777F]">Loading case details...</p>
        ) : (
          <div className="space-y-4">
            <NextHearingAlert matter={matter} tracking={tracking} hearings={hearings} />

            <div className="grid grid-cols-1 gap-4 md:grid-cols-12">
              <div className="space-y-4 md:col-span-8">
                <TimelineView hearings={hearings} orders={orders} causelist={causelist} />
                <OrdersSection orders={orders} onAddOrder={handleAddOrder} />
              </div>
              <div className="space-y-4 md:col-span-4">
                <CaseMetadata matter={matter} tracking={tracking} />
                <ApplicationsTracker applications={applications} />
                <PartiesAndCounsel advocates={advocates} />
              </div>
            </div>
          </div>
        )}
      </div>
    </AuthedShell>
  );
}
