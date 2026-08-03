/**
 * Auto-generating matter title (Sprint 2 Phase 1 Session 1, per
 * docs/UI_UX_Design_Notes.md's "flip the flow" matter-creation
 * redesign): "New [Template Name] — Untitled" until party names are
 * filled, then "[Template Name] — [Party A] / [Party B]" (slash
 * separator — Indian legal convention, not an ampersand). Company/LLP
 * names are shown without their corporate suffix ("Acme Technologies",
 * not "Acme Technologies Pvt Ltd") — the suffix is legally load-bearing
 * in the drafted document itself but adds no identifying value in a
 * short matter title.
 */

const CORPORATE_SUFFIX_RES: RegExp[] = [
  /\bprivate\s+limited\b/gi,
  /\bpvt\.?\s*ltd\.?\b/gi,
  /\bllp\b/gi,
  /\blimited\b/gi,
  /\bltd\.?\b/gi,
  /\bpartnership\s+firm\b/gi,
  /\bproprietorship\b/gi,
];

export function stripCorporateSuffix(name: string): string {
  let result = name.trim();
  for (const re of CORPORATE_SUFFIX_RES) {
    result = result.replace(re, "").trim();
  }
  // A suffix strip commonly leaves a trailing separator behind, e.g.
  // "Acme Technologies, Pvt Ltd" -> "Acme Technologies,".
  result = result.replace(/[,\-–]+$/, "").trim();
  return result || name.trim();
}

const MAX_TITLE_LENGTH = 50;

export function generateMatterTitle(
  templateName: string,
  partyAName: string | undefined,
  partyBName: string | undefined
): string {
  const a = partyAName?.trim() ? stripCorporateSuffix(partyAName) : "";
  const b = partyBName?.trim() ? stripCorporateSuffix(partyBName) : "";

  let title: string;
  if (!a && !b) {
    title = `New ${templateName} — Untitled`;
  } else if (a && b) {
    title = `${templateName} — ${a} / ${b}`;
  } else {
    title = `${templateName} — ${a || b}`;
  }

  if (title.length > MAX_TITLE_LENGTH) {
    title = `${title.slice(0, MAX_TITLE_LENGTH - 1).trimEnd()}…`;
  }
  return title;
}
