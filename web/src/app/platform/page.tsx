"use client";

import { useEffect, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  getPlatformOverview,
  listOrganizations,
  OrganizationListItem,
  PlatformOverview,
  ApiError,
} from "@/lib/api";
import { AlertCircle, Building2, RotateCcw } from "lucide-react";

// Built directly against the existing VidhiDesk visual language (same
// Tailwind tokens as /contracts, /rera/deeds, /admin/templates) rather than
// through the Google Stitch design lifecycle -- this is a platform-owner-
// only operational screen, not a Litigation feature (which IS strictly
// Stitch-gated per docs/50_Reference/Stitch_Guidelines.md /
// Build_Tracker.md §0.3). Flagged explicitly in this session's delivery
// report as a disclosed tradeoff, not a silent process skip.

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  trial: "secondary",
  active: "default",
  suspended: "destructive",
  expired: "destructive",
};

const STATUS_FILTERS = ["all", "trial", "active", "suspended", "expired"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

function friendlyError(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) {
    return "You don't have platform-owner access.";
  }
  return err instanceof Error ? err.message : String(err);
}

export default function PlatformDashboardPage() {
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [orgs, setOrgs] = useState<OrganizationListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  function load() {
    setError(null);
    setLoading(true);
    Promise.all([
      getPlatformOverview(),
      listOrganizations(statusFilter === "all" ? undefined : { status: statusFilter }),
    ])
      .then(([ov, list]) => {
        setOverview(ov);
        setOrgs(list);
      })
      .catch((err) => setError(friendlyError(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Building2 className="h-5 w-5 text-[#081534]" strokeWidth={1.5} />
          <div>
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534]">
              Platform Dashboard
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Onboarding and access status across every organization. Owner-only.
            </p>
          </div>
        </div>

        {error && (
          <div role="alert" className="rounded-sm border border-[#FFDAD6] bg-[#FFF5F5] p-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 shrink-0 text-[#7A2A2A]" />
              <div className="flex-1">
                <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-[#7A2A2A]">
                  Error
                </h4>
                <p className="mt-1 font-serif text-xs text-[#1A1A1A]">{error}</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={load}
                className="h-8 gap-1.5 rounded-sm border-[#7A2A2A] font-sans text-xs font-semibold text-[#7A2A2A] hover:bg-[#FFDAD6]/30"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Try Again
              </Button>
            </div>
          </div>
        )}

        {overview && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
            {[
              ["Organizations", overview.total_organizations],
              ["Individual", overview.individual_organizations],
              ["Firm", overview.firm_organizations],
              ["Trial", overview.trial_organizations],
              ["Active", overview.active_organizations],
              ["Suspended", overview.suspended_organizations],
              ["Expired", overview.expired_organizations],
            ].map(([label, value]) => (
              <Card key={label as string} className="rounded-sm border border-[#E4E2DD] bg-white p-3 shadow-none">
                <p className="font-sans text-[10px] font-bold uppercase tracking-wider text-[#76777F]">{label}</p>
                <p className="mt-1 font-sans text-xl font-semibold text-[#081534]">{value}</p>
              </Card>
            ))}
          </div>
        )}

        {overview && (
          <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
            <p className="font-sans text-xs font-bold uppercase tracking-wider text-[#45464E]">
              Onboarding Funnel
            </p>
            <p className="mt-1 font-serif text-[11px] text-[#76777F]">
              Approximated from existing timestamps (matters, drafts, first login) — see the delivery notes for what this can and can&apos;t yet measure precisely.
            </p>
            <div className="mt-3 flex flex-wrap gap-4">
              {Object.entries(overview.onboarding_funnel).map(([step, count]) => (
                <div key={step} className="min-w-[120px]">
                  <p className="font-sans text-[10px] uppercase tracking-wider text-[#76777F]">
                    {step.replace(/_/g, " ")}
                  </p>
                  <p className="font-sans text-lg font-semibold text-[#081534]">{count}</p>
                </div>
              ))}
            </div>
          </Card>
        )}

        <div className="flex items-center gap-2">
          {STATUS_FILTERS.map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={
                "rounded-sm border px-3 py-1.5 font-sans text-xs font-semibold capitalize transition-colors " +
                (statusFilter === s
                  ? "border-[#081534] bg-[#081534] text-white"
                  : "border-[#E4E2DD] bg-white text-[#45464E] hover:border-[#081534]")
              }
            >
              {s}
            </button>
          ))}
        </div>

        <div className="space-y-2">
          {loading && <p className="font-serif text-sm text-[#45464E]">Loading organizations…</p>}
          {!loading && orgs.length === 0 && !error && (
            <p className="font-serif text-sm text-[#76777F]">No organizations match this filter.</p>
          )}
          {orgs.map((org) => (
            <a key={org.id} href={`/platform/${org.id}`} className="block">
              <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none transition-colors hover:border-[#081534]">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-sans text-sm font-semibold text-[#081534]">{org.name}</span>
                      <Badge variant="secondary" className="capitalize">{org.organization_type}</Badge>
                      <Badge variant={STATUS_VARIANT[org.subscription_status]} className="capitalize">
                        {org.subscription_status}
                      </Badge>
                      {!org.access_enabled && <Badge variant="destructive">Access disabled</Badge>}
                    </div>
                    <p className="mt-1 font-serif text-xs text-[#76777F]">
                      {org.member_count} member{org.member_count === 1 ? "" : "s"} · {org.matter_count} matter
                      {org.matter_count === 1 ? "" : "s"} · trial ends{" "}
                      {new Date(org.trial_ends_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className="font-sans text-xs font-semibold text-[#081534]">View →</span>
                </div>
              </Card>
            </a>
          ))}
        </div>
      </div>
    </AuthedShell>
  );
}
