"use client";

import { useEffect, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { listTemplateClauses, listTemplates, Template } from "@/lib/api";

type TemplateWithCounts = Template & { reviewedCount: number; clauseCount: number };

export default function AdminTemplatesIndexPage() {
  const [templates, setTemplates] = useState<TemplateWithCounts[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const rows = await listTemplates();
        const withCounts = await Promise.all(
          rows.map(async (t) => {
            const clauses = await listTemplateClauses(t.id);
            return {
              ...t,
              clauseCount: clauses.length,
              reviewedCount: clauses.filter((c) => c.review_status !== "unreviewed").length,
            };
          })
        );
        setTemplates(withCounts);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    }
    void load();
  }, []);

  return (
    <AuthedShell wide>
      <div className="space-y-4">
        <div>
          <h1 className="text-xl font-semibold">Template clause review</h1>
          <p className="text-sm text-muted-foreground">
            Every clause below is either fixed boilerplate (hand-authored, never LLM-generated)
            or an LLM prompt template reviewed at the template level — no client data is
            involved here.
          </p>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        <div className="space-y-2">
          {templates.map((t) => (
            <a key={t.id} href={`/admin/templates/${t.template_key}`} className="block">
              <Card className="transition hover:bg-accent">
                <CardContent className="flex items-center justify-between py-4">
                  <div>
                    <div className="font-medium">{t.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {t.reviewedCount}/{t.clauseCount} clauses reviewed
                    </div>
                  </div>
                  <Badge variant={t.review_status === "reviewed" ? "default" : "secondary"}>
                    {t.review_status === "reviewed" ? "Reviewed" : "Beta — pending clause review"}
                  </Badge>
                </CardContent>
              </Card>
            </a>
          ))}
        </div>
      </div>
    </AuthedShell>
  );
}
