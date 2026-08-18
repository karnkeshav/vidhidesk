"use client";

import { useRouter } from "next/navigation";
import { AuthedShell, useMatters } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
  FileText,
  Gavel,
  Building2,
  UserSearch,
  ChevronRight,
} from "lucide-react";

export default function DashboardPage() {
  // Auth Request Forensics Sprint, item 8: this used to call listMatters()
  // itself, duplicating the identical fetch AuthedShell already makes for
  // its sidebar -- two concurrent GET /api/matters on every dashboard
  // load. Now shares AuthedShell's single fetch via context.
  const { matters, error } = useMatters();
  const router = useRouter();

  const contractsMatters = matters.filter((m) => m.module === "contracts");
  const litigationMatters = matters.filter((m) => m.module === "litigation");
  const reraMatters = matters.filter((m) => m.module === "rera");
  const consultingMatters = matters.filter((m) => m.module === "consulting");

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        {/* Daily Briefing Top Box (Stitch Approved Layout) */}
        <section className="rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] p-4 md:p-5">
          <div className="space-y-1">
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534] md:text-2xl">
              Good morning, Nitesh.
            </h1>
          </div>
        </section>

        {error && (
          <div
            role="alert"
            className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]"
          >
            {error}
          </div>
        )}

        {/* 12-Column Responsive Dashboard Grid */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Main 4 Module Cards Grid (8 Columns) */}
          <div className="space-y-6 lg:col-span-8">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {/* 1. Contracts Card */}
              <Card className="flex flex-col justify-between rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none transition-all hover:border-[#081534]">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-[#FBF9F4] text-[#081534]">
                      <FileText className="h-6 w-6" strokeWidth={1.5} />
                    </div>
                  </div>
                  <div>
                    <h3 className="font-sans text-lg font-semibold text-[#081534]">Contracts</h3>
                    <p className="font-serif text-xs text-[#45464E]">
                      Management of multi-jurisdictional drafting and execution.
                    </p>
                  </div>
                  <div className="space-y-1.5 pt-1">
                    {contractsMatters.length > 0 ? (
                      contractsMatters.slice(0, 2).map((m) => (
                        <a
                          key={m.id}
                          href={`/contracts/${m.id}`}
                          className="flex items-center gap-1.5 font-serif text-xs italic text-[#081534] hover:underline"
                        >
                          <ChevronRight className="h-3 w-3 text-[#76777F]" />
                          <span>{m.title}</span>
                        </a>
                      ))
                    ) : (
                      <p className="font-serif text-xs text-[#76777F]">No active contract matters.</p>
                    )}
                  </div>
                </div>
                <a href="/contracts" className="mt-4 block">
                  <Button className="w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]">
                    Continue Working
                  </Button>
                </a>
              </Card>

              {/* 2. Litigation Card */}
              <Card className="flex flex-col justify-between rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none transition-all hover:border-[#081534]">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-[#FBF9F4] text-[#081534]">
                      <Gavel className="h-6 w-6" strokeWidth={1.5} />
                    </div>
                  </div>
                  <div>
                    <h3 className="font-sans text-lg font-semibold text-[#081534]">Litigation</h3>
                    <p className="font-serif text-xs text-[#45464E]">
                      Track court dates, evidentiary logs, and ongoing filings.
                    </p>
                  </div>
                  <div className="space-y-1.5 pt-1">
                    {litigationMatters.length > 0 ? (
                      litigationMatters.slice(0, 2).map((m) => (
                        <a
                          key={m.id}
                          href={`/litigation/${m.id}`}
                          className="flex items-center gap-1.5 font-serif text-xs italic text-[#081534] hover:underline"
                        >
                          <ChevronRight className="h-3 w-3 text-[#76777F]" />
                          <span>{m.title}</span>
                        </a>
                      ))
                    ) : (
                      <p className="font-serif text-xs text-[#76777F]">No active litigation matters.</p>
                    )}
                  </div>
                </div>
                <a href="/litigation" className="mt-4 block">
                  <Button className="w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]">
                    Continue Working
                  </Button>
                </a>
              </Card>

              {/* 3. RERA Card */}
              <Card className="flex flex-col justify-between rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none transition-all hover:border-[#081534]">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-[#FBF9F4] text-[#081534]">
                      <Building2 className="h-6 w-6" strokeWidth={1.5} />
                    </div>
                  </div>
                  <div>
                    <h3 className="font-sans text-lg font-semibold text-[#081534]">RERA</h3>
                    <p className="font-serif text-xs text-[#45464E]">
                      Real Estate Regulatory Authority compliance and tracking.
                    </p>
                  </div>
                  <div className="space-y-1.5 pt-1">
                    {reraMatters.length > 0 ? (
                      reraMatters.slice(0, 2).map((m) => (
                        <a
                          key={m.id}
                          href={`/rera/${m.id}`}
                          className="flex items-center gap-1.5 font-serif text-xs italic text-[#081534] hover:underline"
                        >
                          <ChevronRight className="h-3 w-3 text-[#76777F]" />
                          <span>{m.title}</span>
                        </a>
                      ))
                    ) : (
                      <p className="font-serif text-xs text-[#76777F]">No active RERA matters.</p>
                    )}
                  </div>
                </div>
                <a href="/rera" className="mt-4 block">
                  <Button className="w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]">
                    Continue Working
                  </Button>
                </a>
              </Card>

              {/* 4. Consulting Card */}
              <Card className="flex flex-col justify-between rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none transition-all hover:border-[#081534]">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-sm bg-[#FBF9F4] text-[#081534]">
                      <UserSearch className="h-6 w-6" strokeWidth={1.5} />
                    </div>
                  </div>
                  <div>
                    <h3 className="font-sans text-lg font-semibold text-[#081534]">Consulting</h3>
                    <p className="font-serif text-xs text-[#45464E]">
                      Advisory services, legal opinions, and regulatory audits.
                    </p>
                  </div>
                  <div className="space-y-1.5 pt-1">
                    {consultingMatters.length > 0 ? (
                      consultingMatters.slice(0, 2).map((m) => (
                        <a
                          key={m.id}
                          href={`/matters/${m.id}`}
                          className="flex items-center gap-1.5 font-serif text-xs italic text-[#081534] hover:underline"
                        >
                          <ChevronRight className="h-3 w-3 text-[#76777F]" />
                          <span>{m.title}</span>
                        </a>
                      ))
                    ) : (
                      <p className="font-serif text-xs text-[#76777F]">No active consulting matters.</p>
                    )}
                  </div>
                </div>
                <Button
                  onClick={() => router.push("/consulting")}
                  className="mt-4 w-full rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]"
                >
                  Continue Working
                </Button>
              </Card>
            </div>
          </div>

          {/* Right Sidebar Column: Recent Activity (4 Columns) */}
          <div className="lg:col-span-4">
            <Card className="h-full rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none">
              <CardHeader className="p-0 pb-4">
                <CardTitle className="font-sans text-base font-semibold text-[#081534]">
                  Recent Activity
                </CardTitle>
                <CardDescription className="font-serif text-xs text-[#45464E]">
                  Audit log of recent drafting & matter updates
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <p className="font-serif text-xs text-[#76777F]">No recent activity.</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AuthedShell>
  );
}
