"use client";

import React, { useState } from "react";
import { AuthedShell, useMatters } from "@/components/authed-shell";
import { FileText, AlertTriangle, Map, FolderOpen, ArrowRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function RERAHubPage() {
  const { matters, error } = useMatters();
  const [searchQuery, setSearchQuery] = useState("");

  // Filter matters for 'rera' module
  const reraMatters = matters.filter((m) => m.module === "rera");

  const filteredMatters = reraMatters.filter((m) =>
    m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    m.client_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AuthedShell wide>
      <div className="flex h-full flex-col bg-[#FBF9F5]">
        {/* HEADER */}
        <header className="shrink-0 border-b border-[#E4E2DD] bg-white px-6 py-8">
          <h1 className="font-sans text-2xl font-bold text-[#081534]">RERA & Real Estate Hub</h1>
          <p className="font-serif text-sm text-[#45464E] mt-2 max-w-2xl">
            Manage your real estate matters, draft property deeds, and file complaints under the Real Estate (Regulation and Development) Act.
          </p>
        </header>

        {/* MAIN CONTENT */}
        <main className="flex-1 overflow-y-auto p-6 space-y-8">
          {/* WORKFLOWS GRID */}
          <section>
            <h2 className="font-sans text-sm font-bold text-[#081534] mb-4 uppercase tracking-wider">Main Workflows</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Link href="/rera/deeds" className="group flex flex-col bg-white rounded-md border border-[#E4E2DD] p-6 hover:border-[#081534] hover:shadow-sm transition-all">
                <div className="h-10 w-10 rounded-full bg-[#F0EEE9] flex items-center justify-center mb-4 group-hover:bg-[#081534] group-hover:text-white transition-colors">
                  <FileText className="h-5 w-5 text-[#45464E] group-hover:text-white transition-colors" />
                </div>
                <h3 className="font-sans text-lg font-bold text-[#081534] mb-2">Draft Property Deed</h3>
                <p className="font-serif text-sm text-[#45464E] flex-1">Create sale deeds, lease agreements, and other property-related documents.</p>
                <div className="mt-4 flex items-center text-sm font-semibold text-[#081534]">
                  Start drafting <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              </Link>

              <Link href="/rera/complaint/new" className="group flex flex-col bg-white rounded-md border border-[#E4E2DD] p-6 hover:border-[#081534] hover:shadow-sm transition-all">
                <div className="h-10 w-10 rounded-full bg-[#F0EEE9] flex items-center justify-center mb-4 group-hover:bg-[#081534] group-hover:text-white transition-colors">
                  <AlertTriangle className="h-5 w-5 text-[#45464E] group-hover:text-white transition-colors" />
                </div>
                <h3 className="font-sans text-lg font-bold text-[#081534] mb-2">File RERA Complaint</h3>
                <p className="font-serif text-sm text-[#45464E] flex-1">Initiate a formal complaint with the RERA authority against developers or promoters.</p>
                <div className="mt-4 flex items-center text-sm font-semibold text-[#081534]">
                  File a complaint <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              </Link>

              <Link href="/rera/walkthrough" className="group flex flex-col bg-white rounded-md border border-[#E4E2DD] p-6 hover:border-[#081534] hover:shadow-sm transition-all">
                <div className="h-10 w-10 rounded-full bg-[#F0EEE9] flex items-center justify-center mb-4 group-hover:bg-[#081534] group-hover:text-white transition-colors">
                  <Map className="h-5 w-5 text-[#45464E] group-hover:text-white transition-colors" />
                </div>
                <h3 className="font-sans text-lg font-bold text-[#081534] mb-2">Filing Walkthrough</h3>
                <p className="font-serif text-sm text-[#45464E] flex-1">Step-by-step guidance on RERA compliance, registration, and dispute resolution.</p>
                <div className="mt-4 flex items-center text-sm font-semibold text-[#081534]">
                  View walkthrough <ArrowRight className="ml-2 h-4 w-4 transition-transform group-hover:translate-x-1" />
                </div>
              </Link>
            </div>
          </section>

          {/* RECENT MATTERS */}
          <section>
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-4 gap-4">
              <h2 className="font-sans text-sm font-bold text-[#081534] uppercase tracking-wider">Recent RERA Matters</h2>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Search RERA matters..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-64 bg-white border border-[#E4E2DD] rounded-sm px-3 py-1.5 font-sans text-xs focus:outline-none focus:border-[#081534]"
                />
              </div>
            </div>

            {error && (
              <div className="rounded-md bg-red-50 p-4 border border-red-200">
                <p className="text-sm text-[#ba1a1a]">Error loading matters: {error}</p>
              </div>
            )}

            {!error && filteredMatters.length === 0 ? (
              <div className="bg-white border border-[#E4E2DD] rounded-md p-12 flex flex-col items-center justify-center text-center">
                <FolderOpen className="h-12 w-12 text-[#C6C6CF] mb-4" />
                <h3 className="font-sans text-base font-bold text-[#081534] mb-2">No RERA matters found</h3>
                <p className="font-serif text-sm text-[#45464E] max-w-sm mb-6">
                  {searchQuery 
                    ? "No matters matched your search query. Try adjusting your search terms." 
                    : "You don't have any active real estate or RERA matters. Start a new workflow above to create one."}
                </p>
                {!searchQuery && (
                  <Link href="/rera/complaint/new">
                    <Button className="bg-[#081534] text-white hover:bg-[#1E2A4A] h-9 px-4 text-xs font-semibold">
                      File New Complaint
                    </Button>
                  </Link>
                )}
              </div>
            ) : (
              <div className="bg-white border border-[#E4E2DD] rounded-md overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#E4E2DD] bg-[#FBF9F4] font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
                        <th className="p-3">Matter Name</th>
                        <th className="p-3">Client</th>
                        <th className="p-3">Forum / Location</th>
                        <th className="p-3">Status</th>
                        <th className="p-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredMatters.map((m) => (
                        <tr key={m.id} className="border-b border-[#E4E2DD] hover:bg-[#FBF9F4] transition-colors">
                          <td className="p-3">
                            <a href={`/litigation/${m.id}`} className="font-sans text-xs font-semibold text-[#081534] hover:underline">
                              {m.title}
                            </a>
                            {m.case_number_formatted && (
                              <p className="font-serif text-[11px] text-[#45464E] mt-0.5">{m.case_number_formatted}</p>
                            )}
                          </td>
                          <td className="p-3 font-serif text-xs text-[#45464E]">{m.client_name || "-"}</td>
                          <td className="p-3 font-sans text-xs text-[#45464E]">
                            {m.court_category ? `${m.court_category} ${m.jurisdiction_state ? `(${m.jurisdiction_state})` : ""}` : "-"}
                          </td>
                          <td className="p-3">
                            <span className="rounded-xs border border-[#C6C6CF] bg-[#F0EEE9] px-2 py-0.5 font-sans text-[10px] font-semibold text-[#081534]">
                              {m.litigation_stage || "Active"}
                            </span>
                          </td>
                          <td className="p-3 text-right">
                            <a href={`/litigation/${m.id}`} className="font-sans text-xs font-semibold text-[#081534] hover:underline">
                              Open &rarr;
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </main>
      </div>
    </AuthedShell>
  );
}
