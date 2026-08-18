"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createMatter, listTemplates, listMatters, Matter, Template, ApiError } from "@/lib/api";
import { Search, FolderOpen, FileText, AlertCircle, RotateCcw } from "lucide-react";

function friendlyLoadError(err: unknown): string {
  if (err && typeof err === "object" && "name" in err && (err as { name?: string }).name === "AbortError") {
    return "The server took too long to respond after several attempts. Please try again in a moment.";
  }
  if (err instanceof ApiError && err.status >= 500) {
    return "The server is temporarily unavailable. This usually resolves within a few seconds -- try again.";
  }
  if (err instanceof Error && /server error '?5\d\d/i.test(err.message)) {
    return "An upstream service had a brief connectivity issue. Try again -- this is not something wrong with your account.";
  }
  if (err instanceof Error && /Not signed in/i.test(err.message)) {
    return "Your session has ended. Please sign in again.";
  }
  if (err instanceof TypeError) {
    return "Couldn't reach the server -- check your connection and try again.";
  }
  return err instanceof Error ? err.message : String(err);
}

export default function PropertyDeedsPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [matters, setMatters] = useState<Matter[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busyTemplateId, setBusyTemplateId] = useState<string | null>(null);

  function loadData() {
    setError(null);
    listTemplates()
      .then((rows) => setTemplates(rows.filter((t) => t.category === "rera")))
      .catch((err) => setError(friendlyLoadError(err)));

    listMatters()
      .then((rows) => setMatters(rows.filter((m) => m.module === "rera")))
      .catch(() => {});
  }

  useEffect(() => {
    loadData();
  }, []);

  const filteredMatters = matters.filter((m) =>
    searchQuery.trim() === ""
      ? true
      : m.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (m.client_name && m.client_name.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const filteredTemplates = templates.filter((t) => {
    const rawKey = (t.template_key || "").toLowerCase();
    const key = rawKey.replace(/_/g, "-");
    const name = t.name.toLowerCase();
    const query = searchQuery.trim().toLowerCase();

    return !query || name.includes(query) || key.includes(query) || rawKey.includes(query);
  });

  async function handleStart(template: Template) {
    setBusyTemplateId(template.id);
    setError(null);
    try {
      const matter = await createMatter({
        title: `New ${template.name}`,
        module: "rera",
        template_id: template.id,
      });
      router.push(`/rera/${matter.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusyTemplateId(null);
    }
  }

  return (
    <AuthedShell wide>
      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Left Sidebar: Matter Navigator */}
        <aside className="w-full shrink-0 space-y-4 rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] p-4 lg:w-[280px]">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#76777F]" />
            <Input
              type="text"
              placeholder="Search deeds & matters..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 rounded-sm border-[#E4E2DD] bg-white pl-8 font-sans text-xs text-[#1A1A1A]"
            />
          </div>

          <div className="space-y-3 pt-2">
            <div>
              <p className="px-1 font-sans text-[10px] font-bold uppercase tracking-wider text-[#45464E]">
                Active Property Matters ({filteredMatters.length})
              </p>
              <div className="mt-1.5 space-y-1">
                {filteredMatters.length === 0 ? (
                  <p className="px-1 font-serif text-xs text-[#76777F]">No active property matters</p>
                ) : (
                  filteredMatters.map((m) => (
                    <a
                      key={m.id}
                      href={`/rera/${m.id}`}
                      className="flex items-center gap-2 rounded-sm px-2 py-1.5 font-sans text-xs font-medium text-[#081534] transition-colors hover:bg-[#E4E2DD]"
                    >
                      <FolderOpen className="h-3.5 w-3.5 shrink-0 text-[#45464E]" />
                      <span className="truncate">{m.title}</span>
                    </a>
                  ))
                )}
              </div>
            </div>
          </div>
        </aside>

        {/* Main Center Area: Template Picker */}
        <div className="flex-1 space-y-6">
          <div>
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534]">
              Property Deeds
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Select a verified property template to start drafting.
            </p>
          </div>

          {error && (
            <div role="alert" className="rounded-sm border border-[#FFDAD6] bg-[#FFF5F5] p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="h-5 w-5 shrink-0 text-[#7A2A2A]" />
                <div className="flex-1">
                  <h4 className="font-sans text-xs font-bold uppercase tracking-wider text-[#7A2A2A]">
                    System Error
                  </h4>
                  <p className="mt-1 font-serif text-xs text-[#1A1A1A]">{error}</p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadData}
                  className="h-8 gap-1.5 rounded-sm border-[#7A2A2A] font-sans text-xs font-semibold text-[#7A2A2A] hover:bg-[#FFDAD6]/30"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Try Again
                </Button>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {templates.length === 0 && !error && (
              <p className="font-serif text-sm text-[#45464E] col-span-full">Loading property templates…</p>
            )}
            {templates.length > 0 && filteredTemplates.length === 0 && (
              <div className="col-span-full rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-6 text-center space-y-3">
                <p className="font-sans text-sm font-semibold text-[#081534]">
                  No templates match your search
                </p>
                <p className="font-serif text-xs text-[#76777F]">
                  Try adjusting your search query.
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSearchQuery("")}
                  className="rounded-sm border-[#E4E2DD] font-sans text-xs font-semibold text-[#081534]"
                >
                  Clear Search
                </Button>
              </div>
            )}
            {filteredTemplates.map((t) => (
              <Card
                key={t.id}
                className="flex flex-col justify-between rounded-sm border border-[#E4E2DD] bg-white p-5 shadow-none transition-all hover:border-[#081534]"
              >
                <div className="space-y-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-[#081534]" />
                      <h3 className="font-sans text-base font-semibold text-[#081534]">{t.name}</h3>
                    </div>
                    <p className="font-serif text-xs text-[#45464E] min-h-[32px]">
                      A legally verified deed template ready for intake. Supported States: {t.states_supported.join(", ") || "Central Jurisdictions"}.
                    </p>
                  </div>
                  <div>
                    <Badge variant={t.review_status === "reviewed" ? "default" : "secondary"}>
                      {t.review_status === "reviewed" ? "Reviewed" : "Beta"}
                    </Badge>
                  </div>
                </div>
                <div className="pt-4 mt-auto">
                  <Button
                    onClick={() => handleStart(t)}
                    disabled={busyTemplateId === t.id}
                    className="w-full h-9 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]"
                  >
                    {busyTemplateId === t.id ? "Drafting..." : "Start Drafting"}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </AuthedShell>
  );
}
