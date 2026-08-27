"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  getOrganization,
  updateOrganizationAccess,
  OrganizationDetail,
  ApiError,
} from "@/lib/api";
import { AlertCircle, ArrowLeft, RotateCcw } from "lucide-react";

// Dashboard clarity (security review round 3, 27 Aug 2026): the owner
// asked for exactly two, clearly separated states shown on this screen --
// ORGANIZATION ACCESS (this org, derived from access_enabled/
// subscription_status) and MEMBER ACCOUNT ACCESS (each member's own
// account_security state, entirely independent of the org-level one).
// This 3-way label collapses the org's access_enabled + subscription_status
// pair into the single glanceable state the owner actually cares about --
// the raw badges below remain visible too, for anyone who wants the detail.
function organizationAccessLabel(org: { access_enabled: boolean; subscription_status: string }): "Enabled" | "Suspended" | "Expired" {
  if (!org.access_enabled || org.subscription_status === "suspended") return "Suspended";
  if (org.subscription_status === "expired") return "Expired";
  return "Enabled";
}

const ORG_ACCESS_VARIANT: Record<string, "default" | "destructive"> = {
  Enabled: "default",
  Suspended: "destructive",
  Expired: "destructive",
};

const ACCOUNT_STATUS_LABEL: Record<string, string> = {
  trial_active: "Trial Active",
  trial_expired: "Trial Expired",
  payment_received: "Payment Received",
  not_started: "Not Started",
};

const ACCOUNT_STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  trial_active: "secondary",
  trial_expired: "destructive",
  payment_received: "default",
  not_started: "secondary",
};

function friendlyError(err: unknown): string {
  if (err instanceof ApiError && err.status === 403) {
    return "You don't have platform-owner access.";
  }
  if (err instanceof ApiError && err.status === 404) {
    return "Organization not found.";
  }
  return err instanceof Error ? err.message : String(err);
}

export default function OrganizationDetailPage() {
  const params = useParams<{ orgId: string }>();
  const router = useRouter();
  const [org, setOrg] = useState<OrganizationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");

  function load() {
    setError(null);
    getOrganization(params.orgId)
      .then(setOrg)
      .catch((err) => setError(friendlyError(err)));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.orgId]);

  async function runAction(action: "mark_payment" | "enable" | "suspend" | "reactivate" | "extend_trial") {
    if (action === "suspend" && !window.confirm(`Suspend access for ${org?.name}?`)) return;
    setBusy(true);
    setError(null);
    try {
      await updateOrganizationAccess(params.orgId, {
        action,
        reason: reason.trim() || undefined,
        extend_days: action === "extend_trial" ? 5 : undefined,
      });
      setReason("");
      load();
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setBusy(false);
    }
  }

  if (error && !org) {
    return (
      <AuthedShell wide>
        <div className="space-y-4">
          <Button variant="outline" size="sm" onClick={() => router.push("/platform")} className="gap-1.5 rounded-sm">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Platform Dashboard
          </Button>
          <div role="alert" className="rounded-sm border border-[#FFDAD6] bg-[#FFF5F5] p-4">
            <p className="font-serif text-sm text-[#7A2A2A]">{error}</p>
          </div>
        </div>
      </AuthedShell>
    );
  }

  if (!org) {
    return (
      <AuthedShell wide>
        <p className="font-serif text-sm text-[#45464E]">Loading…</p>
      </AuthedShell>
    );
  }

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        <Button variant="outline" size="sm" onClick={() => router.push("/platform")} className="gap-1.5 rounded-sm">
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Platform Dashboard
        </Button>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534]">{org.name}</h1>
              <Badge variant="secondary" className="capitalize">{org.organization_type}</Badge>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="font-sans text-[10px] font-bold uppercase tracking-wider text-[#76777F]">
                Organization Access:
              </span>
              <Badge variant={ORG_ACCESS_VARIANT[organizationAccessLabel(org)]}>
                {organizationAccessLabel(org)}
              </Badge>
              <span className="font-serif text-[11px] text-[#76777F]">
                ({org.subscription_status}{!org.access_enabled ? ", access_enabled=false" : ""})
              </span>
            </div>
            <p className="mt-1 font-serif text-xs text-[#76777F]">
              Created {new Date(org.created_at).toLocaleDateString()} · Trial ends{" "}
              {new Date(org.trial_ends_at).toLocaleDateString()}
              {org.payment_marked_at && ` · Payment marked ${new Date(org.payment_marked_at).toLocaleDateString()}`}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={load} className="h-8 gap-1.5 rounded-sm">
            <RotateCcw className="h-3.5 w-3.5" /> Refresh
          </Button>
        </div>

        {error && (
          <div role="alert" className="rounded-sm border border-[#FFDAD6] bg-[#FFF5F5] p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-[#7A2A2A]" />
              <p className="font-serif text-xs text-[#1A1A1A]">{error}</p>
            </div>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
            <CardHeader className="p-0 pb-2">
              <CardTitle className="font-sans text-sm text-[#081534]">Usage</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 p-0 font-serif text-sm text-[#1A1A1A]">
              <p>{org.matter_count} matter{org.matter_count === 1 ? "" : "s"}</p>
              <p>
                Modules used:{" "}
                {org.modules_used.length ? org.modules_used.join(", ") : "none yet"}
              </p>
              <p>
                Last activity:{" "}
                {org.last_activity_at ? new Date(org.last_activity_at).toLocaleString() : "none yet"}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
            <CardHeader className="p-0 pb-2">
              <CardTitle className="font-sans text-sm text-[#081534]">Members</CardTitle>
              <p className="font-serif text-[11px] text-[#76777F]">
                Member Account Access — each person&apos;s own 5-day trial/payment status, separate
                from Organization Access above.
              </p>
            </CardHeader>
            <CardContent className="space-y-2 p-0 font-serif text-sm text-[#1A1A1A]">
              {org.members.map((m) => (
                <div key={m.id} className="flex items-center justify-between gap-2">
                  <span className="truncate">{m.email || m.user_id}</span>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Badge variant="secondary" className="capitalize">{m.role.replace("_", " ")}</Badge>
                    {m.account_status && (
                      <Badge variant={ACCOUNT_STATUS_VARIANT[m.account_status]}>
                        {ACCOUNT_STATUS_LABEL[m.account_status]}
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
          <CardHeader className="p-0 pb-3">
            <CardTitle className="font-sans text-sm text-[#081534]">Owner Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-0">
            <div className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3 font-serif text-xs text-[#45464E]">
              These actions control <strong>organization-level</strong> access only. Each member&apos;s
              individual 5-day trial (and payment status) is separate and is not changed by anything
              below — if a member&apos;s own trial has expired, they still need their per-account
              payment status updated separately, even after you enable this organization.
            </div>
            <Textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Optional note — why this change (kept in the audit trail)"
              rows={2}
              className="font-serif text-sm"
            />
            <div className="flex flex-wrap gap-2">
              <Button size="sm" disabled={busy} onClick={() => runAction("mark_payment")} className="rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]">
                Mark Organization Payment Made
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => runAction("enable")} className="rounded-sm font-sans text-xs font-semibold">
                Enable Access
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => runAction("reactivate")} className="rounded-sm font-sans text-xs font-semibold">
                Reactivate
              </Button>
              <Button size="sm" variant="outline" disabled={busy} onClick={() => runAction("extend_trial")} className="rounded-sm font-sans text-xs font-semibold">
                Extend Trial +5 Days
              </Button>
              <Button size="sm" variant="destructive" disabled={busy} onClick={() => runAction("suspend")} className="rounded-sm font-sans text-xs font-semibold">
                Suspend
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </AuthedShell>
  );
}
