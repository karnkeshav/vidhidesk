"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { createMatter, listTemplates, listMatters, Matter, Template } from "@/lib/api";
import { Search, Plus, FolderOpen, History, FileText } from "lucide-react";

export default function ContractsPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [matters, setMatters] = useState<Matter[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Template | null>(null);
  const [clientName, setClientName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listTemplates()
      .then((rows) => setTemplates(rows.filter((t) => t.category === "contracts")))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));

    listMatters()
      .then(setMatters)
      .catch(() => {});
  }, []);

  const filteredMatters = matters.filter((m) =>
    searchQuery.trim() === ""
      ? true
      : m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (m.client_name && m.client_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const matter = await createMatter({
        title: `New ${selected.name} — Untitled`,
        client_name: clientName || undefined,
        module: "contracts",
      });
      router.push(`/contracts/${matter.id}?template=${selected.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <AuthedShell wide>
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Left Sidebar: Matter Navigator (280px Stitch Design) */}
        <aside className="w-full shrink-0 space-y-4 rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] p-4 lg:w-[280px]">
          <Button
            onClick={() => setSelected(templates[0] || null)}
            className="flex w-full items-center justify-center gap-2 rounded-sm bg-[#081534] py-2.5 font-sans text-xs font-semibold uppercase tracking-wider text-white hover:bg-[#1E2A4A]"
          >
            <Plus className="h-4 w-4" strokeWidth={1.5} />
            New Contract
          </Button>

          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#76777F]" />
            <Input
              type="text"
              placeholder="Search matters..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 rounded-sm border-[#E4E2DD] bg-white pl-8 font-sans text-xs text-[#1A1A1A]"
            />
          </div>

          <div className="space-y-3 pt-2">
            <div>
              <p className="px-1 font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
                Active Matters ({filteredMatters.length})
              </p>
              <div className="mt-1.5 space-y-1">
                {filteredMatters.length === 0 ? (
                  <p className="px-1 font-serif text-xs text-[#76777F]">No active contract matters</p>
                ) : (
                  filteredMatters.map((m) => (
                    <a
                      key={m.id}
                      href={`/contracts/${m.id}`}
                      className="flex items-center gap-2 rounded-sm px-2 py-1.5 font-sans text-xs font-medium text-[#081534] transition-colors hover:bg-[#E4E2DD]"
                    >
                      <FolderOpen className="h-3.5 w-3.5 shrink-0 text-[#45464E]" />
                      <span className="truncate">{m.title}</span>
                    </a>
                  ))
                )}
              </div>
            </div>

            <div className="border-t border-[#E4E2DD] pt-3">
              <p className="px-1 font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
                Recent Drafts
              </p>
              <div className="mt-1.5 space-y-1">
                <a
                  href="/contracts"
                  className="flex items-center gap-2 rounded-sm px-2 py-1 font-sans text-xs text-[#45464E] hover:bg-[#E4E2DD]"
                >
                  <History className="h-3.5 w-3.5" />
                  <span>NDAs - Q4 Batch</span>
                </a>
                <a
                  href="/contracts"
                  className="flex items-center gap-2 rounded-sm px-2 py-1 font-sans text-xs text-[#45464E] hover:bg-[#E4E2DD]"
                >
                  <History className="h-3.5 w-3.5" />
                  <span>Vendor Onboarding</span>
                </a>
              </div>
            </div>

            <div className="border-t border-[#E4E2DD] pt-3">
              <p className="px-1 font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
                Contract Type
              </p>
              <div className="mt-1.5 space-y-1.5 px-1 font-sans text-xs text-[#45464E]">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" defaultChecked className="rounded border-[#E4E2DD]" />
                  Commercial & Service
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded border-[#E4E2DD]" />
                  Employment & HR
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" className="rounded border-[#E4E2DD]" />
                  Intellectual Property
                </label>
              </div>
            </div>
          </div>
        </aside>

        {/* Main Center Area: Template Picker & Matter Creation Canvas */}
        <div className="flex-1 space-y-6">
          <div>
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534]">
              Contracts Workspace
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Select a verified legal template to generate an advocate-reviewed contract draft.
            </p>
          </div>

          {error && (
            <p role="alert" className="font-sans text-sm text-[#7A2A2A]">
              {error}
            </p>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {templates.length === 0 && !error && (
              <p className="font-serif text-sm text-[#45464E]">Loading contract templates…</p>
            )}
            {templates.map((t) => (
              <Card
                key={t.id}
                className={
                  "cursor-pointer rounded-sm border bg-white p-4 shadow-none transition-all " +
                  (selected?.id === t.id
                    ? "border-[#081534] bg-[#FBF9F4]"
                    : "border-[#E4E2DD] hover:border-[#081534]")
                }
                onClick={() => setSelected(t)}
              >
                <div className="flex flex-col justify-between h-full space-y-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-[#081534]" />
                      <h3 className="font-sans text-base font-semibold text-[#081534]">{t.name}</h3>
                    </div>
                    <p className="font-serif text-xs text-[#45464E]">
                      Supported States: {t.states_supported.join(", ") || "Central Jurisdictions"}
                    </p>
                  </div>
                  <div>
                    <Badge variant={t.review_status === "reviewed" ? "default" : "secondary"}>
                      {t.review_status === "reviewed" ? "Reviewed" : "Beta — pending clause review"}
                    </Badge>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {selected && (
            <Card className="rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none">
              <CardHeader className="p-0 pb-4">
                <CardTitle className="font-sans text-base text-[#081534]">
                  New Contract Matter — {selected.name}
                </CardTitle>
                <CardDescription className="font-serif text-xs text-[#45464E]">
                  The matter title generates automatically from the contracting party names as you complete the intake form.
                </CardDescription>
              </CardHeader>
              <CardContent className="p-0 pt-2">
                <form onSubmit={handleStart} className="space-y-4">
                  <div className="space-y-1">
                    <Label htmlFor="client" className="font-sans text-xs font-semibold text-[#081534]">
                      Client / Organization Name (Optional)
                    </Label>
                    <Input
                      id="client"
                      value={clientName}
                      onChange={(e) => setClientName(e.target.value)}
                      placeholder="e.g. Acme Industries Ltd."
                      className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                    />
                  </div>
                  <Button
                    type="submit"
                    disabled={busy}
                    className="h-10 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]"
                  >
                    {busy ? "Creating Matter…" : "Continue to Intake Form"}
                  </Button>
                </form>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </AuthedShell>
  );
}
