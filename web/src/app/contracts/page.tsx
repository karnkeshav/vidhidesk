"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { createMatter, listTemplates, Template } from "@/lib/api";

export default function ContractsPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Template | null>(null);
  const [title, setTitle] = useState("");
  const [clientName, setClientName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listTemplates()
      .then((rows) => setTemplates(rows.filter((t) => t.category === "contracts")))
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  async function handleStart(e: React.FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const matter = await createMatter({
        title,
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
    <AuthedShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-semibold">Contracts</h1>
          <p className="text-sm text-muted-foreground">
            Select a template to start a new draft.
          </p>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="space-y-3">
          {templates.length === 0 && !error && (
            <p className="text-sm text-muted-foreground">No contract templates yet.</p>
          )}
          {templates.map((t) => (
            <Card
              key={t.id}
              className={
                "cursor-pointer transition hover:bg-accent " +
                (selected?.id === t.id ? "border-primary" : "")
              }
              onClick={() => setSelected(t)}
            >
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <div className="font-medium">{t.name}</div>
                  <div className="text-xs text-muted-foreground">
                    States: {t.states_supported.join(", ") || "Central only"}
                  </div>
                </div>
                <Badge variant={t.review_status === "reviewed" ? "default" : "secondary"}>
                  {t.review_status === "reviewed" ? "Reviewed" : "Beta — pending clause review"}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>

        {selected && (
          <Card>
            <CardHeader>
              <CardTitle>New matter — {selected.name}</CardTitle>
              <CardDescription>
                Create the matter this draft belongs to, then fill in the intake form.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleStart} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="title">Matter title</Label>
                  <Input
                    id="title"
                    required
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
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
                <Button type="submit" disabled={busy}>
                  {busy ? "Creating…" : "Continue to intake form"}
                </Button>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </AuthedShell>
  );
}
