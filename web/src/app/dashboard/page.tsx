"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { createMatter, listMatters, Matter } from "@/lib/api";

const MODULES: Matter["module"][] = ["litigation", "contracts", "rera", "consulting"];

export default function DashboardPage() {
  const router = useRouter();
  const [matters, setMatters] = useState<Matter[]>([]);
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const [module, setModule] = useState<Matter["module"]>("litigation");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setMatters(await listMatters());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const matter = await createMatter({
        title,
        client_name: clientName || undefined,
        module,
      });
      setTitle("");
      setClientName("");
      router.push(`/matters/${matter.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthedShell>
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>New matter</CardTitle>
            <CardDescription>
              Sprint 0 scope: create a matter and send a chat message. Module
              workspaces come later.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input id="title" required value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="client">Client name (optional)</Label>
                <Input
                  id="client"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  placeholder="Used to auto-mask PII before any LLM call"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="module">Module</Label>
                <select
                  id="module"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={module}
                  onChange={(e) => setModule(e.target.value as Matter["module"])}
                >
                  {MODULES.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" disabled={busy}>
                Create matter
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-2">
          <h2 className="text-sm font-medium text-muted-foreground">Your matters</h2>
          {matters.length === 0 && (
            <p className="text-sm text-muted-foreground">No matters yet.</p>
          )}
          {matters.map((m) => (
            <a key={m.id} href={`/matters/${m.id}`} className="block">
              <Card className="transition hover:bg-accent">
                <CardContent className="flex items-center justify-between py-4">
                  <div>
                    <div className="font-medium">{m.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {m.module} {m.client_name ? `· ${m.client_name}` : ""}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </a>
          ))}
        </div>
      </div>
    </AuthedShell>
  );
}
