"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell, useMatters } from "@/components/authed-shell";
import { Gavel, Search, Filter, LayoutGrid, List, Plus, X } from "lucide-react";
import { createMatter } from "@/lib/api";
import { Button } from "@/components/ui/button";

export default function LitigationPage() {
  const router = useRouter();
  const { matters, error } = useMatters();
  const litigationMatters = matters.filter((m) => m.module === "litigation");

  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"list" | "grid">("list");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // New Matter Form State
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const [courtCategory, setCourtCategory] = useState("High Court");
  const [jurisdictionState, setJurisdictionState] = useState("Delhi");

  const filteredMatters = litigationMatters.filter(
    (m) =>
      m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.client_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.cnr_number?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.case_number_formatted?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  async function handleCreateMatter(e: React.FormEvent) {
    e.preventDefault();
    if (!title) return;
    setIsCreating(true);
    try {
      const m = await createMatter({
        title,
        module: "litigation",
        client_name: clientName,
        court_category: courtCategory,
        jurisdiction_state: jurisdictionState,
      });
      router.push(`/litigation/${m.id}`);
    } catch (err) {
      console.error(err);
      setIsCreating(false);
    }
  }

  return (
    <AuthedShell wide>
      <div className="flex h-full min-h-[80vh]">
        {/* CENTER COLUMN: Litigation Matters List */}
        <main className="flex-1 flex flex-col min-w-0 pr-4">
          <header className="flex flex-col md:flex-row justify-between items-start md:items-center py-4 border-b border-[#E4E2DD] gap-4">
            <div>
              <h2 className="font-sans text-xl font-semibold text-[#081534]">Litigation Matters</h2>
              <p className="font-serif text-sm text-[#45464E] mt-1">{litigationMatters.length} active cases requiring attention.</p>
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <div className="relative w-full md:w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#45464E]" />
                <input
                  type="text"
                  placeholder="Search title, ref, party..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-white border border-[#E4E2DD] rounded-sm pl-9 pr-3 py-1.5 font-sans text-xs focus:outline-none focus:border-[#081534]"
                />
              </div>
              <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-[#E4E2DD] rounded-sm font-sans text-xs font-semibold text-[#081534] hover:bg-[#F0EEE9]">
                <Filter className="h-3.5 w-3.5" />
                Filters
              </button>
              <div className="flex bg-white border border-[#E4E2DD] rounded-sm overflow-hidden">
                <button
                  onClick={() => setViewMode("list")}
                  className={`p-1.5 transition-colors ${viewMode === "list" ? "bg-[#E4E2DD] text-[#081534]" : "text-[#45464E] hover:bg-[#F0EEE9]"}`}
                >
                  <List className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setViewMode("grid")}
                  className={`p-1.5 transition-colors ${viewMode === "grid" ? "bg-[#E4E2DD] text-[#081534]" : "text-[#45464E] hover:bg-[#F0EEE9]"}`}
                >
                  <LayoutGrid className="h-4 w-4" />
                </button>
              </div>
              <Button
                onClick={() => setIsDrawerOpen(true)}
                className="hidden md:flex h-8 gap-1.5 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
              >
                <Plus className="h-3.5 w-3.5" />
                New Matter
              </Button>
            </div>
          </header>

          <div className="py-6">
            {error && (
              <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A] mb-4">
                {error}
              </div>
            )}

            {filteredMatters.length === 0 ? (
              <div className="text-center py-10 font-serif text-sm text-[#45464E]">
                No litigation matters found.
              </div>
            ) : viewMode === "list" ? (
              <div className="bg-white rounded-sm border border-[#E4E2DD] overflow-hidden">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-[#F0EEE9] border-b border-[#E4E2DD] font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
                      <th className="p-3">Matter Name</th>
                      <th className="p-3">Client</th>
                      <th className="p-3">Forum</th>
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
                          {m.case_number_formatted && <p className="font-serif text-[11px] text-[#45464E] mt-0.5">{m.case_number_formatted}</p>}
                        </td>
                        <td className="p-3 font-serif text-xs text-[#45464E]">{m.client_name || "-"}</td>
                        <td className="p-3 font-sans text-xs text-[#45464E]">
                          {m.court_category ? `${m.court_category} (${m.jurisdiction_state || "India"})` : "-"}
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
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredMatters.map((m) => (
                  <a key={m.id} href={`/litigation/${m.id}`} className="block bg-white rounded-sm border border-[#E4E2DD] p-4 hover:border-[#081534] transition-colors">
                    <div className="flex items-start justify-between mb-2">
                      <div className="rounded-xs bg-[#F0EEE9] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-[#081534]">
                        {m.litigation_stage || "Active"}
                      </div>
                      <Gavel className="h-4 w-4 text-[#45464E]" />
                    </div>
                    <h3 className="font-sans text-sm font-semibold text-[#081534] mb-1 line-clamp-2">{m.title}</h3>
                    <p className="font-serif text-xs text-[#45464E] line-clamp-1">{m.client_name || "Unspecified Client"}</p>
                    <div className="mt-3 pt-3 border-t border-[#E4E2DD] flex justify-between font-sans text-[11px] text-[#45464E]">
                      <span>{m.court_category || "Unspecified Forum"}</span>
                      <span className="font-semibold text-[#081534]">View &rarr;</span>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        </main>

        {/* RIGHT COLUMN: New Litigation Matter Drawer */}
        {isDrawerOpen && (
          <aside className="w-80 shrink-0 border-l border-[#E4E2DD] bg-[#FBF9F4] flex flex-col fixed top-16 right-0 h-[calc(100vh-64px)] z-40 shadow-xl overflow-y-auto transform transition-transform md:static md:shadow-none md:translate-x-0">
            <header className="flex justify-between items-center p-4 border-b border-[#E4E2DD] bg-white sticky top-0 z-10">
              <h2 className="font-sans text-sm font-semibold text-[#081534]">New Litigation Matter</h2>
              <button onClick={() => setIsDrawerOpen(false)} className="text-[#45464E] hover:text-[#081534]">
                <X className="h-4 w-4" />
              </button>
            </header>

            <form onSubmit={handleCreateMatter} className="p-4 flex-1 space-y-4">
              <div>
                <label className="block font-sans text-xs font-semibold text-[#081534] mb-1">Matter Title *</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Sharma vs. TechCorp"
                  className="w-full bg-white border border-[#E4E2DD] rounded-sm px-2 py-1.5 font-sans text-xs focus:outline-none focus:border-[#081534]"
                />
              </div>

              <div>
                <label className="block font-sans text-xs font-semibold text-[#081534] mb-1">Client Name</label>
                <input
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="Client's name"
                  className="w-full bg-white border border-[#E4E2DD] rounded-sm px-2 py-1.5 font-sans text-xs focus:outline-none focus:border-[#081534]"
                />
              </div>

              <div>
                <label className="block font-sans text-xs font-semibold text-[#081534] mb-1">Court Category</label>
                <select
                  value={courtCategory}
                  onChange={(e) => setCourtCategory(e.target.value)}
                  className="w-full bg-white border border-[#E4E2DD] rounded-sm px-2 py-1.5 font-sans text-xs focus:outline-none focus:border-[#081534]"
                >
                  <option value="Supreme Court">Supreme Court of India</option>
                  <option value="High Court">High Court</option>
                  <option value="District Court">District Court</option>
                  <option value="NCLT">NCLT / NCLAT</option>
                  <option value="Consumer Forum">Consumer Forum</option>
                  <option value="Arbitration">Arbitration Tribunal</option>
                </select>
              </div>

              <div>
                <label className="block font-sans text-xs font-semibold text-[#081534] mb-1">Jurisdiction State</label>
                <select
                  value={jurisdictionState}
                  onChange={(e) => setJurisdictionState(e.target.value)}
                  className="w-full bg-white border border-[#E4E2DD] rounded-sm px-2 py-1.5 font-sans text-xs focus:outline-none focus:border-[#081534]"
                >
                  <option value="Delhi">Delhi</option>
                  <option value="Maharashtra">Maharashtra</option>
                  <option value="Karnataka">Karnataka</option>
                  <option value="Tamil Nadu">Tamil Nadu</option>
                  <option value="UP">Uttar Pradesh</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div className="pt-4 border-t border-[#E4E2DD]">
                <Button type="submit" disabled={isCreating} className="w-full bg-[#081534] text-white font-sans text-xs font-semibold hover:bg-[#1E2A4A] h-8">
                  {isCreating ? "Creating..." : "Create Matter Workspace"}
                </Button>
              </div>
            </form>
          </aside>
        )}

        {/* Mobile FAB (Visible when drawer is closed) */}
        {!isDrawerOpen && (
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="md:hidden fixed bottom-20 right-4 h-12 w-12 bg-[#081534] text-white rounded-full flex items-center justify-center shadow-lg"
          >
            <Plus className="h-6 w-6" />
          </button>
        )}
      </div>
    </AuthedShell>
  );
}
