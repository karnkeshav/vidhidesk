"use client";

import { useEffect, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { listMatters, Matter } from "@/lib/api";

// The Contracts module (via /contracts) is the only module with a real
// per-matter workflow (template selection -> intake form -> draft ->
// clause review) as of Sprint 2. litigation/rera/consulting have no
// module-specific UI yet, so this page is deliberately a read-only
// overview, not a matter-creation form — an earlier generic "New
// matter" form here let a matter be created without a template
// attached, landing on a bare, unfinished chat page regardless of which
// module was picked. Removed 2026-08-02 ahead of Nitesh's first login,
// rather than leaving a control that only works for one of its four
// listed options.
export default function DashboardPage() {
  const [matters, setMatters] = useState<Matter[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMatters()
      .then(setMatters)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);

  return (
    <AuthedShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Your matters</h1>
          <a href="/contracts">
            <Button>Start a new contract</Button>
          </a>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="space-y-2">
          {matters.length === 0 && !error && (
            <p className="text-sm text-muted-foreground">
              No matters yet — start one from Contracts above.
            </p>
          )}
          {matters.map((m) => (
            <a
              key={m.id}
              href={m.module === "contracts" ? `/contracts/${m.id}` : `/matters/${m.id}`}
              className="block"
            >
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
