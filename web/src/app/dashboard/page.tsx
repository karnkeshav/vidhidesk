"use client";

import { useEffect, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { listMatters, Matter } from "@/lib/api";
import { Search, Plus, Gavel, FileCheck, FolderOpen, Calendar, ArrowRight } from "lucide-react";

type ModuleFilter = "all" | "contracts" | "litigation" | "rera" | "consulting";

export default function DashboardPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedModule, setSelectedModule] = useState<ModuleFilter>("all");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMatters()
      .then(setMatters)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  const filteredMatters = matters.filter((m) => {
    const matchesModule = selectedModule === "all" || m.module === selectedModule;
    const matchesSearch =
      searchQuery.trim() === "" ||
      m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (m.client_name && m.client_name.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesModule && matchesSearch;
  });

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        {/* Top Header Banner */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="font-sans text-2xl font-semibold tracking-tight text-[#081534]">
              Advocate Workspace
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Manage legal matters, draft contracts, and verify statutory citations.
            </p>
          </div>
          <a href="/contracts">
            <Button className="h-10 gap-2 rounded-sm bg-[#081534] font-sans text-sm font-medium text-white transition-colors hover:bg-[#1E2A4A]">
              <Plus className="h-4 w-4" strokeWidth={1.5} />
              Start a new contract
            </Button>
          </a>
        </div>

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
          {/* Main Matter Column (8 Columns) */}
          <div className="space-y-5 lg:col-span-8">
            <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                {/* Module Filter Tabs */}
                <div className="flex flex-wrap gap-1.5">
                  {(["all", "contracts", "litigation", "rera", "consulting"] as const).map((mod) => (
                    <button
                      key={mod}
                      type="button"
                      onClick={() => setSelectedModule(mod)}
                      className={`rounded-sm px-3 py-1.5 font-sans text-xs font-semibold capitalize transition-colors ${
                        selectedModule === mod
                          ? "bg-[#081534] text-white"
                          : "bg-[#FBF9F4] text-[#45464E] hover:bg-[#E4E2DD]"
                      }`}
                    >
                      {mod === "rera" ? "RERA" : mod}
                    </button>
                  ))}
                </div>

                {/* Client-side Matter Search */}
                <div className="relative w-full sm:w-64">
                  <Search
                    className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#76777F]"
                    strokeWidth={1.5}
                  />
                  <Input
                    type="text"
                    placeholder="Search matters by title..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-9 rounded-sm border-[#E4E2DD] bg-white pl-9 font-serif text-xs text-[#1A1A1A] placeholder:text-[#9A9B9E] focus-visible:ring-1 focus-visible:ring-[#081534]"
                  />
                </div>
              </div>
            </Card>

            {/* Matter Cards List */}
            <div className="space-y-3">
              {filteredMatters.length === 0 && !error && (
                <Card className="rounded-sm border border-dashed border-[#E4E2DD] bg-white p-8 text-center shadow-none">
                  <CardContent className="space-y-2 pt-6">
                    <FolderOpen className="mx-auto h-8 w-8 text-[#76777F]" strokeWidth={1.5} />
                    <p className="font-serif text-sm text-[#45464E]">
                      {searchQuery
                        ? `No matters found matching "${searchQuery}".`
                        : "No active matters in this module yet — start one from Contracts above."}
                    </p>
                  </CardContent>
                </Card>
              )}

              {filteredMatters.map((m) => (
                <a
                  key={m.id}
                  href={m.module === "contracts" ? `/contracts/${m.id}` : `/matters/${m.id}`}
                  className="block transition-all"
                >
                  <Card className="group rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none transition-colors hover:border-[#081534] hover:bg-[#FBF9F4]">
                    <div className="flex items-center justify-between">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] font-semibold uppercase tracking-wider text-[#081534]">
                            {m.module}
                          </span>
                          <span className="font-sans text-xs text-[#76777F]">
                            {new Date(m.created_at).toLocaleDateString("en-IN", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })}
                          </span>
                        </div>
                        <h3 className="font-serif text-base font-medium text-[#1A1A1A] group-hover:text-[#081534]">
                          {m.title}
                        </h3>
                        {m.client_name && (
                          <p className="font-serif text-xs text-[#45464E]">
                            Client: {m.client_name}
                          </p>
                        )}
                      </div>
                      <ArrowRight
                        className="h-5 w-5 text-[#76777F] transition-transform group-hover:translate-x-1 group-hover:text-[#081534]"
                        strokeWidth={1.5}
                      />
                    </div>
                  </Card>
                </a>
              ))}
            </div>
          </div>

          {/* Right Sidebar Column (4 Columns) */}
          <div className="space-y-5 lg:col-span-4">
            {/* Cause List Widget (Empty State Only) */}
            <Card className="rounded-sm border border-[#E4E2DD] bg-white shadow-none">
              <CardHeader className="border-b border-[#E4E2DD] pb-3">
                <div className="flex items-center gap-2">
                  <Gavel className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                  <CardTitle className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
                    Litigation Cause List
                  </CardTitle>
                </div>
                <CardDescription className="font-serif text-xs text-[#45464E]">
                  Upcoming court appearances & hearings
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4">
                <div className="rounded-sm border border-dashed border-[#E4E2DD] bg-[#FBF9F4] p-4 text-center">
                  <Calendar className="mx-auto mb-2 h-6 w-6 text-[#76777F]" strokeWidth={1.5} />
                  <p className="font-sans text-xs font-semibold text-[#1A1A1A]">
                    No court appearances scheduled
                  </p>
                  <p className="mt-1 font-serif text-[11px] text-[#76777F]">
                    Litigation hearing dockets and court dates will be tracked here.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Citation Summary Card (Empty State Only) */}
            <Card className="rounded-sm border border-[#E4E2DD] bg-white shadow-none">
              <CardHeader className="border-b border-[#E4E2DD] pb-3">
                <div className="flex items-center gap-2">
                  <FileCheck className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                  <CardTitle className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
                    Citation Gate Summary
                  </CardTitle>
                </div>
                <CardDescription className="font-serif text-xs text-[#45464E]">
                  Indian Kanoon doc_id verification audit
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4">
                <div className="rounded-sm border border-dashed border-[#E4E2DD] bg-[#FBF9F4] p-4 text-center">
                  <FileCheck className="mx-auto mb-2 h-6 w-6 text-[#76777F]" strokeWidth={1.5} />
                  <p className="font-sans text-xs font-semibold text-[#1A1A1A]">
                    No citation verifications logged
                  </p>
                  <p className="mt-1 font-serif text-[11px] text-[#76777F]">
                    Verified Kanoon citations will be listed here as draft clauses are reviewed.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AuthedShell>
  );
}
