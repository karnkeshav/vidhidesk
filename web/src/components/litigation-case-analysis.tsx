"use client";

import React, { useEffect, useState } from "react";
import {
  CaseAnalysis,
  generateCaseAnalysis,
  listCaseAnalyses,
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Sparkles,
  AlertTriangle,
  ShieldAlert,
  FileWarning,
  ListChecks,
  Scale,
  Clock,
  Gavel,
  CheckCircle2,
  History,
} from "lucide-react";
import { cn } from "@/lib/utils";

type LimitationSnapshot = CaseAnalysis["limitation_summary"];
type ForumSnapshot = CaseAnalysis["jurisdiction_summary"];

interface LitigationCaseAnalysisProps {
  matterId: string;
  hasParties: boolean;
  hasFacts: boolean;
  limitationSnapshot: LimitationSnapshot | null;
  forumSnapshot: ForumSnapshot | null;
}

function SectionCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3">
      <div className="flex items-center gap-2 border-b border-[#E4E2DD] pb-2">
        {icon}
        <h4 className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
          {title}
        </h4>
      </div>
      <div className="font-serif text-xs leading-relaxed text-[#1A1A1A]">{children}</div>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const styles: Record<string, string> = {
    High: "bg-[#FFF5F5] text-[#7A2A2A] border-[#F8D7DA]",
    Medium: "bg-[#FFF8E6] text-[#8A6D1F] border-[#F3E3AE]",
    Low: "bg-[#F0F5F0] text-[#3D5A3D] border-[#C3E6CB]",
  };
  return (
    <span
      className={cn(
        "rounded-xs border px-1.5 py-0.5 font-sans text-[10px] font-bold uppercase",
        styles[severity] || styles.Medium
      )}
    >
      {severity}
    </span>
  );
}

/** Citation Gate rendering, exactly per docs/LITIGATION_ARCHITECTURE.md §7 /
 * ADR-005: a case name only ever renders as a live hyperlink when the
 * Citation Verifier confirmed an ik_url — never on the model's say-so. */
function PrecedentCard({
  precedent,
}: {
  precedent: CaseAnalysis["possible_precedents"][number];
}) {
  const verified = precedent.status === "verified" && precedent.ik_url;
  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3 space-y-1">
      {verified ? (
        <a
          href={precedent.ik_url!}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-sans text-xs font-semibold text-[#081534] underline"
        >
          {precedent.case_name}
          <CheckCircle2 className="h-3 w-3 text-[#3D5A3D]" />
        </a>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-sans text-xs font-semibold text-[#7A2A2A]">{precedent.case_name}</span>
          <span className="rounded-xs bg-[#FFDAD6] px-1 py-0.5 font-sans text-[9px] font-bold uppercase text-[#7A2A2A]">
            ⚠ Unverified — confirm manually
          </span>
        </div>
      )}
      {precedent.note && <p className="font-serif text-[11px] text-[#45464E]">{precedent.note}</p>}
      {precedent.court && <p className="font-serif text-[10px] text-[#76777F]">{precedent.court}</p>}
    </div>
  );
}

export function LitigationCaseAnalysis({
  matterId,
  hasParties,
  hasFacts,
  limitationSnapshot,
  forumSnapshot,
}: LitigationCaseAnalysisProps) {
  const [versions, setVersions] = useState<CaseAnalysis[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listCaseAnalyses(matterId)
      .then((list) => {
        if (!cancelled) {
          setVersions(list);
          setSelectedIdx(0);
        }
      })
      .catch(() => {
        if (!cancelled) setVersions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [matterId]);

  const canGenerate = hasParties && hasFacts;
  const current = versions[selectedIdx] ?? null;

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const result = await generateCaseAnalysis(matterId, {
        limitation: limitationSnapshot || undefined,
        forum: forumSnapshot || undefined,
      });
      setVersions((prev) => [result, ...prev]);
      setSelectedIdx(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-sm border border-[#E4E2DD] bg-white p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="flex items-center gap-2 font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
            <Sparkles className="h-4 w-4" />
            AI Case Analysis
          </h3>
          <p className="mt-1 font-serif text-xs text-[#45464E]">
            A pre-drafting review the advocate reviews before deciding whether — and how — to draft.
            This is analysis, not a pleading.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {versions.length > 1 && (
            <select
              value={selectedIdx}
              onChange={(e) => setSelectedIdx(Number(e.target.value))}
              className="h-8 rounded-sm border border-[#E4E2DD] bg-white px-2 font-sans text-xs text-[#1A1A1A]"
            >
              {versions.map((v, i) => (
                <option key={v.id} value={i}>
                  Version {v.version_no}
                  {i === 0 ? " (latest)" : ""}
                </option>
              ))}
            </select>
          )}
          <Button
            onClick={handleGenerate}
            disabled={!canGenerate || generating}
            title={!canGenerate ? "Add at least one party and one fact before generating an analysis" : undefined}
            className="h-8 gap-1.5 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A] disabled:opacity-50"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {generating ? "Analyzing…" : versions.length > 0 ? "Regenerate Analysis" : "Generate AI Case Analysis"}
          </Button>
        </div>
      </div>

      {!canGenerate && (
        <div className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3 font-serif text-xs text-[#76777F]">
          Add at least one party (Case Overview tab) and one fact entry (Facts & Exhibits tab) before generating a
          case analysis.
        </div>
      )}

      {error && (
        <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="rounded-sm border border-dashed border-[#E4E2DD] p-8 text-center font-sans text-xs text-[#76777F]">
          Loading analysis history…
        </div>
      ) : !current ? (
        <div className="rounded-sm border border-dashed border-[#E4E2DD] p-8 text-center font-sans text-xs text-[#76777F]">
          No AI Case Analysis generated yet for this matter.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-sm border border-[#C6C6CF] bg-[#F0EEE9] px-3 py-2 font-sans text-[10px] font-semibold text-[#081534]">
            <span className="flex items-center gap-1.5">
              <History className="h-3 w-3" />
              Version {current.version_no} · {new Date(current.created_at).toLocaleString("en-IN")}
              {current.model_used ? ` · ${current.model_used}` : ""}
            </span>
          </div>

          <div className="rounded-sm border border-[#C6C6CF] bg-[#FFF8E6] px-3 py-2 font-serif text-[11px] italic text-[#8A6D1F]">
            {current.notice}
          </div>

          {current.generation_warning && (
            <div className="flex items-start gap-2 rounded-sm border border-[#F3E3AE] bg-[#FFF8E6] p-3 font-serif text-xs text-[#8A6D1F]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {current.generation_warning}
            </div>
          )}

          <SectionCard icon={<ListChecks className="h-4 w-4 text-[#081534]" />} title="Matter Summary">
            <p>{current.matter_summary || "No summary generated."}</p>
          </SectionCard>

          <SectionCard icon={<Clock className="h-4 w-4 text-[#081534]" />} title="Chronological Facts">
            {current.chronological_facts.length === 0 ? (
              <p className="text-[#76777F]">No facts recorded.</p>
            ) : (
              <ol className="space-y-2">
                {current.chronological_facts.map((f, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="w-24 shrink-0 font-sans text-[10px] font-semibold text-[#45464E]">
                      {f.event_date || "Undated"}
                    </span>
                    <span className="flex-1">
                      {f.fact_summary}
                      {f.exhibit_number && (
                        <span className="ml-1.5 rounded-xs bg-[#F0EEE9] px-1 py-0.5 font-sans text-[9px] font-bold text-[#081534]">
                          {f.exhibit_number}
                        </span>
                      )}
                      {!f.has_evidence_file && (
                        <span className="ml-1.5 font-sans text-[9px] uppercase text-[#76777F]">no file attached</span>
                      )}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </SectionCard>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <SectionCard icon={<Gavel className="h-4 w-4 text-[#081534]" />} title="Jurisdiction Summary">
              {current.jurisdiction_summary ? (
                <div className="space-y-1">
                  <p className="font-semibold text-[#081534]">
                    {current.jurisdiction_summary.recommended_forum.forum_name}
                  </p>
                  <p className="text-[#45464E]">{current.jurisdiction_summary.recommended_forum.territorial_basis}</p>
                  {!current.jurisdiction_summary.is_unambiguous && (
                    <p className="italic text-[#7A2A2A]">Multiple viable forums identified — manual review required.</p>
                  )}
                </div>
              ) : (
                <p className="text-[#76777F]">Not yet determined — run the Forum Advisor on the Case Overview tab.</p>
              )}
            </SectionCard>

            <SectionCard icon={<Clock className="h-4 w-4 text-[#081534]" />} title="Limitation Summary">
              {current.limitation_summary ? (
                <div className="space-y-1">
                  <p
                    className={cn(
                      "font-semibold",
                      current.limitation_summary.is_barred ? "text-[#7A2A2A]" : "text-[#3D5A3D]"
                    )}
                  >
                    {current.limitation_summary.is_barred ? "Statutory Barred" : "Within Limitation"} ·{" "}
                    {current.limitation_summary.limitation_expiry_date}
                  </p>
                  <p className="text-[#45464E]">{current.limitation_summary.condonation_notes}</p>
                </div>
              ) : (
                <p className="text-[#76777F]">Not yet calculated — run the Limitation Calculator on the Case Overview tab.</p>
              )}
            </SectionCard>
          </div>

          <SectionCard icon={<Scale className="h-4 w-4 text-[#081534]" />} title="Applicable Statutes">
            {current.applicable_statutes.length === 0 ? (
              <p className="text-[#76777F]">No statutory provisions retrieved for these facts.</p>
            ) : (
              <div className="space-y-2">
                {current.applicable_statutes.map((s, i) => (
                  <div key={i} className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
                    <p className="font-sans text-xs font-semibold text-[#081534]">
                      {s.act} — Section {s.section_no}
                    </p>
                    <p className="mt-0.5 text-[11px] text-[#45464E]">{s.chunk_excerpt}</p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard icon={<Gavel className="h-4 w-4 text-[#081534]" />} title="Possible Causes of Action">
            {current.possible_causes_of_action.length === 0 ? (
              <p className="text-[#76777F]">None identified.</p>
            ) : (
              <div className="space-y-3">
                {current.possible_causes_of_action.map((c, i) => (
                  <div key={i} className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3">
                    <p className="font-sans text-xs font-semibold text-[#081534]">{c.title}</p>
                    <p className="mt-1 text-[11px] text-[#1A1A1A]">{c.description}</p>
                    {c.statutes_relied_upon.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {c.statutes_relied_upon.map((s, j) => (
                          <span
                            key={j}
                            className={cn(
                              "rounded-xs border px-1.5 py-0.5 font-sans text-[9px] font-bold uppercase",
                              s.grounded
                                ? "border-[#C3E6CB] bg-[#F0F5F0] text-[#3D5A3D]"
                                : "border-[#F8D7DA] bg-[#FFF5F5] text-[#7A2A2A]"
                            )}
                            title={s.grounded ? "Matches a retrieved statute chunk" : "Not found in retrieved corpus — verify manually"}
                          >
                            {s.act} § {s.section_no} {s.grounded ? "✓" : "⚠"}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <SectionCard icon={<FileWarning className="h-4 w-4 text-[#081534]" />} title="Missing Information">
              {current.missing_information.length === 0 ? (
                <p className="text-[#76777F]">None flagged.</p>
              ) : (
                <ul className="list-disc space-y-1 pl-4">
                  {current.missing_information.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard icon={<FileWarning className="h-4 w-4 text-[#081534]" />} title="Evidence Gaps">
              {current.evidence_gaps.length === 0 ? (
                <p className="text-[#76777F]">None flagged.</p>
              ) : (
                <ul className="list-disc space-y-1 pl-4">
                  {current.evidence_gaps.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>

          <SectionCard icon={<ShieldAlert className="h-4 w-4 text-[#081534]" />} title="Potential Risks">
            {current.potential_risks.length === 0 ? (
              <p className="text-[#76777F]">None flagged.</p>
            ) : (
              <div className="space-y-2">
                {current.potential_risks.map((r, i) => (
                  <div key={i} className="flex items-start gap-2 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-2.5">
                    <SeverityBadge severity={r.severity} />
                    <div>
                      <p>{r.risk}</p>
                      {r.mitigation && <p className="mt-0.5 text-[11px] italic text-[#45464E]">Mitigation: {r.mitigation}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard icon={<ListChecks className="h-4 w-4 text-[#081534]" />} title="Recommended Next Steps">
            {current.recommended_next_steps.length === 0 ? (
              <p className="text-[#76777F]">None generated.</p>
            ) : (
              <ol className="list-decimal space-y-1 pl-4">
                {current.recommended_next_steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
            )}
          </SectionCard>

          {current.possible_precedents.length > 0 && (
            <SectionCard icon={<Scale className="h-4 w-4 text-[#081534]" />} title="Possible Precedents">
              <div className="space-y-2">
                {current.possible_precedents.map((p, i) => (
                  <PrecedentCard key={i} precedent={p} />
                ))}
              </div>
            </SectionCard>
          )}
        </div>
      )}
    </div>
  );
}
