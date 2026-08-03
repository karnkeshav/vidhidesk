VidhiDesk — Master Build Tracker & Developer Handover
Consolidates: `UI/UX Design Notes` (design system) + `Stitch_Mockup_Plan.md` (what to mock up, in order) + `Navigation_and_Functional_Spec.md` (how every screen behaves/connects/talks to the backend), reconciled against the original `01_Scope_of_Work.md` / `02_Technical_Requirements.md` / `03_Implementation_Plan.md`, the revised `Project_Plan_Legal_AI_Assistant.md`, and actual implementation evidence pasted into chat since.
Document version: v2 — 3 August 2026 (retrofitted with evidence tagging)
Status: Living tracker — update the Status column, and its evidence tag, as work lands.
---
0. How to use this document
Read §0.1 (evidence tagging system) first — every status claim in this document is tagged, and the tag changes what you're allowed to trust it for.
Read §1 (source docs + which plan wins where they disagree).
Read §3 (design system) once — it applies to every screen.
§5 is the actual tracker: Sprint → Session → Screens → Mockup ID → routes → API endpoints → DB tables → tagged Status.
§7 is "where we are right now," with a real evidence-backed build log — start here if you just want current state.
§8 lists gaps — some resolved since v1, some new, all tagged.
§11 (Evidence Log) is the numbered source list every `[E#]` citation in this document points to.
---
0.1 Evidence & Confidence Tagging System
Every architectural or status claim in this document carries one of five tags. This exists because "confirmed" already decayed once in this project — a clause was marked reviewed (`clause_reviews.review_status = 'kept'`), the underlying content was silently rewritten by re-seeding, and the "confirmed reviewed" status kept asserting something no longer true until a sweep caught it [E11]. Documentation can suffer the identical failure mode if status tags aren't bound to a specific piece of evidence and a date.
Tag	Meaning	Citation requirement
✅ Confirmed	Verified against implementation — code, migrations, git history, terminal output, database schema, API response	Must cite the specific evidence item `[E#]` and the date/commit it reflects. Decays — re-verify before relying on it if time has passed.
📐 Designed	Explicitly specified in SOW/TRD/Project Plan but implementation not yet verified	Must cite the document section
🔍 Inferred	Architectural interpretation derived from confirmed facts	Must name the specific confirmed facts it's built from, inline — not just assert the conclusion
🔮 Envisioned	Future direction, intentionally outside current scope	Roadmap/future-doc reference
⚠ Gap	Known inconsistency, undefined behaviour, or missing implementation already identified	Note whether it's a code gap or a documentation-drift gap (spec exists but was never reconciled into the reference docs) — these need different fixes
Bounding statement (methodology, stated once, applies everywhere): All ✅ Confirmed tags in this document are bounded by evidence pasted into this chat by Keshav — terminal output, migration file contents, commit messages, `openapi.json` dumps, click-through reports. There is no live repository access. Anything built in a Claude Code session since the last paste is invisible here and must not be assumed. Where a claim's freshness matters, the tag states the date/commit explicitly; treat anything older than the last full `git log` pull as "last known," not "current."
---
1. Source Documents & Precedence
Doc	Date	Role	Status
`nitesh_recording.txt`	—	Raw requirements source (transcript)	📐 Reference only
`01_Scope_of_Work.md`	23 Jul 2026	Original Phase 1 scope, Litigation-first build order	📐 Superseded on build order (see §1.1)
`02_Technical_Requirements.md`	23 Jul 2026	Architecture, stack, data model, subsystems	📐 Authoritative for intended architecture — ⚠ the actual schema has since outgrown it (see §8.2)
`03_Implementation_Plan.md`	23 Jul 2026	Original sprint plan (S0–S7), Litigation → Contracts → Consulting → RERA	📐 Superseded by Project Plan's build order
`Project_Plan_Legal_AI_Assistant.md`	23 Jul 2026	Revised plan after IK API secured + no sample drafts available	📐 Authoritative for build order and phasing rationale
`UI_UX_Design_Notes.md`	3 Aug 2026	Design system (palette, type, layout skeleton, tone)	📐 Authoritative for design
`Stitch_Mockup_Plan.md`	3 Aug 2026	Screen-by-screen mockup list, sprint/session breakdown, priority order	📐 Authoritative for screen inventory — ⚠ actual build did not follow session boundaries literally (see §8.8, new)
`Navigation_and_Functional_Spec.md`	3 Aug 2026	Navigation map, link matrix, functional/validation spec per screen	📐 Authoritative for intended behavior/backend wiring
1.1 Key reconciliation — Contracts-first rationale (corrected)
📐 Designed, per Project Plan §2: `01_SOW`/`03_Implementation_Plan` assumed Litigation ships first. The revised Project Plan flipped this to Contracts first.
🔍 Inferred (from: Project Plan §2 "Build order" text + the no-sample-drafts constraint documented in Project Plan §6): These are two separate decisions, previously conflated in an earlier draft of this document's understanding. (1) Contracts-first was a product-strategy decision — largest revenue portfolio, template-constrainable, near-zero citation-hallucination risk, and Litigation is precisely where Nitesh's own expertise makes him least dependent on the tool. (2) Clause-by-clause review exists as a separate response to a different problem — no gold-standard contract drafts existed to imitate, so legal correctness had to be captured incrementally at the clause level instead of via whole-document approval. Contracts wasn't chosen because clause review was invented; clause review was invented because Contracts (like everything else) had no sample corpus.
---
2. Product Recap (📐 Designed — SOW §1.1, unchanged across all docs)
Single dashboard, four module tiles:
Module	Core function	Primary risk	Build status
Litigation	Query → validate → provisions → draft pleading, with verified case citations	Citation hallucination	⚠ Gap — zero screens, mockups, or sprint allocation exist anywhere (see §8.1)
Contracts	Pick 1 of 25–30 templates → intake → generate → amend by chat command	Legal correctness without gold-standard drafts	✅ Confirmed in active build — 5 of 10 planned templates live [E2][E8]
RERA / Real Estate	Property deeds (Transfer of Property Act family) + RERA complaint drafting + state filing walkthroughs	State-by-state rule drift	📐 Designed only — no build evidence
Consulting & Litigation Support	Facts in → applicable law, forum, remedy, limitation; strategy briefs for matters argued by other counsel	~80% reuse of Litigation engine	📐 Designed only — no build evidence
Non-negotiable across all four (📐 Designed, TRD §3.3): every case citation is either verified against the Indian Kanoon API and hyperlinked, or rendered as `⚠ UNVERIFIED`. Enforced in the renderer (no `ik_id` in DB → no hyperlink can render), not just in the prompt. Not yet independently confirmed against live Litigation/Consulting code, since that code doesn't exist yet — the enforcement mechanism itself (renderer gate) was committed in Sprint 1 [E1: commit `0b165e8`], so the mechanism is ✅ Confirmed; its use in a real citation-bearing screen remains 📐 Designed until Consulting or Litigation ships.
🔍 Inferred addition, not in original SOW (from: Project Plan §1 cost framing + TRD stack table — Gemini/Groq/Ollama free tiers, Supabase free tier, Indian Kanoon as sole paid dependency): the effectively-zero-recurring-cost constraint is not a side detail — it explains the multi-provider LLM failover chain, the platform choice, and the deliberate exclusion of SCC Online/Manupatra. It functions as a primary architectural driver, not an isolated requirement line, and should be read as such throughout this document.
---
3. Design System Snapshot (📐 Designed — from `UI_UX_Design_Notes.md` + Stitch base context)
Feel: "Claude's calmness meets a barrister's chambers." Quiet authority, professional restraint. Explicitly not startup-flavored, not colorful, not gamified, not BigLaw-cold.
Reference points: Claude.ai, Notion, FT digital, Apple iBooks (restraint) · Bloomberg Terminal, WSJ app (professional gravity). Avoid: colorful Indian legaltech tiles/gradients/gamification, consumer SaaS chattiness, over-formal BigLaw sites.
Palette (exact hex — use everywhere, no deviation):
Role	Hex
Background	`#FBF9F5` (warm ivory)
Primary text	`#1A1A1A` (warm charcoal)
Primary accent	`#1E2A4A` (deep navy)
Critical actions	`#7A2A2A` (muted burgundy)
Success / verified	`#3D5A3D` (muted forest green)
Secondary text	`#6B6B6B` (warm gray)
Borders	`#E5E3DE` (warm gray)
Typography: IBM Plex Serif (long-form legal content, drafts) · IBM Plex Sans (UI). Body 15–16px, UI labels 14px, headings 20–24px.
Iconography: Monoline, single-color, 1.5px stroke, warm gray or navy only.
Layout skeleton (every screen): Global header (56px) · Global footer disclaimer · Left sidebar (persistent desktop / drawer mobile).
Copy tone: Formal, restrained. "Draft" not "Create." "Matter" not "Case." Indian date convention.
🔍 Inferred (from: E2 file listing showing `web/src/components/authed-shell.tsx` modified, `intake-form.tsx` created, and the Sprint 2.5 commit touching `dashboard/page.tsx` and `admin/templates/page.tsx`): the design system above has been at least partially applied to shipped screens, since those files exist and are in active use. Not confirmed: whether the exact palette/typography values were followed pixel-for-pixel — that requires a visual check against a live screenshot, which hasn't been pasted here.
---
4. Phase (Project Plan) → Sprint (Stitch/Nav Spec) Mapping
Project Plan Phase	Weeks	Stitch/Nav Sprint equivalent	Status
Phase 0 — Scope freeze + template sourcing	3 wks	Sprint 1 (pre-tracker)	✅ Confirmed done [E1: commits `219a9aa`, `28e6e85`]
Phase 1 — Contracts MVP	8–10 wks	Sprint 2 + Sprint 3	✅ Confirmed in progress, substantially advanced [E2][E3][E8][E9] — see §7
Phase 2 — Litigation + citation engine	6–8 wks	⚠ No corresponding Stitch/Nav sprint exists yet	⚠ Gap, unresolved — see §8.1
Phase 3 — RERA + Consulting	6 wks	Sprint 4 (Consulting) + Sprint 5 (RERA)	📐 Designed only, no build evidence
Phase 4 — Productisation (post-launch)	ongoing	Sprint 6 (Hardening) + beyond	📐 Designed only, no build evidence
---
5. Master Sprint / Session / Screen Tracker
Status legend: all cells below carry a tag + evidence citation. Where a Stitch "session" boundary didn't match how the build actually proceeded (see §8.8), that's noted directly in the row.
Sprint 1 — Foundations (pre-tracker)
Screen	Route	Status
Login	`/login`	✅ Confirmed [E1: Sprint 0 commit `28e6e85`, "Hello matter" exit criterion]
Dashboard	`/dashboard`	✅ Confirmed, then rebuilt [E3: Sprint 2.5 commit rewrote `dashboard/page.tsx`]
Contracts Template Picker (initial)	`/contracts`	✅ Confirmed live [E2: `web/src/app/contracts/page.tsx` in Sprint 2 commit]
---
Sprint 2 — Contracts Module Completion — ✅ Confirmed substantially built, NOT session-by-session as originally planned
⚠ Gap (documentation drift, see §8.8): the actual build did not proceed through Sessions 1→5 as discrete design passes. Claude Code built the whole Contracts pipeline (intake → draft → clause review) end-to-end across 5 templates in one continuous push, tracked internally as template "Batches" (1a/1b/2/3/4...), not as the 5 UI-focused sessions below. The session table is kept for planning reference; actual status is reported against what's confirmed built, batch-numbering included.
Session (as planned)	Focus	Route(s)	API Endpoints	DB Tables	Status
1	Intake Form	`/contracts/new?template=[key]`	`POST /api/matters/[id]` · `POST /api/contracts/matters/{matter_id}/drafts` · `GET /api/state-rules`	`matters`, `templates`, `state_rules`, `draft_versions`	✅ Confirmed built [E2: `intake-form.tsx` created; E8: live E2E walkthrough on Service Agreement exercised this screen]. Stitch mockups for this session were deliberately skipped by decision, not pending — design language from Login/Dashboard/Picker was judged sufficient.
2	Draft View	`/contracts/[matterId]`	`GET /api/drafts/[id]/download`, `.pdf` · amendment via drafts POST	`draft_versions`, `matters`	✅ Confirmed built [E2: `contracts/[matterId]/page.tsx`; E8: draft generation, docx download exercised]. Amendment loop (v1→v2+) is 📐 Designed per Nav Spec — not explicitly confirmed exercised in pasted evidence.
3	Clause Review Admin	`/admin/templates/[key]`	`POST /api/contracts/templates/{id}/clauses/{cid}/review` · `.../bulk-keep-boilerplate`	`templates`, `template_clauses` ✅, `clause_reviews` ✅	✅ Confirmed built and exercised [E5: migration 0007 creates these tables; E11: the review-state sweep required actually using this screen's data]. This resolves the "undefined tables" gap from tracker v1 — see §8.2 correction. Bulk-keep-boilerplate + cross-template shared-clause detection were requested in a "Batch 4.5" message [E13] but completion is not confirmed by pasted evidence — treat as 📐 Designed/requested, not ✅ built, until confirmed.
4	Icon Replacement + Header/Footer Consistency	Applies globally	—	—	⬜ No evidence either way — likely not started
5	Mobile Responsive Full Pass	`/contracts`, `/matters` mobile, sidebar drawer	`GET /api/templates`	`templates`, `matters`	⬜ No evidence either way — likely not started
Templates actually shipped (✅ Confirmed [E2][E9], all `review_status = 'beta'` pending Nitesh's clause review):
NDA — 12 clauses
Service Agreement — 11 clauses (list repeater, SLA conditional, 3 fee-structure branches)
Consultancy
MoU
Employment
Templates planned but NOT confirmed built (📐 Designed/approved-in-conversation only [E14] — verify before assuming): Leave & Licence, Lease Deed, Agreement to Sell, Joint Venture, Software Development.
Sprint 2 exit gate (📐 Designed, Implementation Plan AC-2.x, adapted): all Contracts screens generate a complete draft from intake; state selection changes stamp-duty notes; amendment commands version without loss; drafts export .docx and .pdf. Not yet confirmed fully met — amendment loop and PDF export specifically lack pasted confirmation.
---
Sprint 3 — Refinements & Admin Improvements
⚠ Gap correction (§8.8): part of this sprint's planned work landed early, informally, folded into what was called "Sprint 2.5" rather than a discrete Sprint 3.
Session	Focus	Route(s)	Status
S3.1	Admin templates index (all-templates review status at a glance)	`/admin/templates`	✅ Confirmed built [E3: "Sprint 2.5: dashboard + admin templates index + nav link" commit — `web/src/app/admin/templates/page.tsx` created] — shipped ahead of its planned sprint slot.
S3.2	Cross-template shared-clause detection banner	`/admin/templates/[key]` (enhancement)	📐 Requested in Batch 4.5 message [E13], not confirmed built
S3.3	Content-hash mismatch warning (clause changed since review)	`/admin/templates/[key]` (enhancement)	⚠ Gap remains — not requested or built as far as evidence shows
---
Sprint 4 — Consulting & Litigation Support Module
Session	Focus	Route(s)	Status
S4.1–S4.4	Consulting landing, analysis result, mobile, citation card	`/consulting`, `/consulting/[matterId]`	⬜ No evidence of any build — 📐 Designed only
⚠ Gap, unresolved, restated (§8.1): the Nav Spec's app map points `/litigation` at "Sprint 4," but Sprint 4's detail only ever covered Consulting. This inconsistency has not been resolved between v1 and v2 of this tracker.
---
Sprint 5 — RERA / Real Estate Module
All sessions (S5.1–S5.6): ⬜ No evidence of any build — 📐 Designed only.
---
Sprint 6 — Hardening & Admin
All sessions (S6.1–S6.2): ⬜ No evidence of any build — 📐 Designed only.
---
6. Cross-Cutting Backend Subsystems
Subsystem	Status
LLM Gateway (Gemini → Groq → Ollama)	✅ Confirmed built, Sprint 0 [E1: commit `28e6e85`]
Conversation history across turns (not in original TRD as a named risk — discovered in build)	⚠→✅ Was a real functional bug: gateway had no memory across turns, so a follow-up like "what is her PAN?" had no referent. Fixed [E12]: bounded 6-message window, prior user turns reconstructed from stored `masked_prompt` (never raw content), so PII never round-trips unmasked into a new prompt.
PII Masker	✅ Confirmed built, then hardened [E12: per-string masking, `auto_detect_names=False` on outer call, deterministic statute-abbreviation allowlist regex (CrPC, IPC, BNS, RERA, GST, etc.); explicit decision made not to allowlist case titles, since under-masking a live client dispute is worse than harmlessly over-masking a famous case]
RAG Retriever (statute knowledge base)	✅ Confirmed built, Sprint 1 [E1: commit `0b165e8` — "statute RAG + hybrid retrieval + full-text keyword search"]
Citation Verifier (Indian Kanoon API) + renderer gate	✅ Confirmed built, Sprint 1 [E1: same commit, "citation verifier + renderer gate"] — mechanism exists; not yet exercised by any live citation-bearing screen (Litigation/Consulting don't exist yet)
Golden test harness	✅ Confirmed exists and used for regression [E1: commits re: "5 golden test fact patterns," "Fix GT-05 fact pattern"]
Template Engine (Jinja2 → python-docx)	✅ Confirmed built and actively extended [E2][E6]: generic conditional-clause inclusion via `applicable_condition` jsonb (migration 0008), assembly-time clause renumbering, generic "list of sub-objects" repeater field type (built once for Service Agreement's deliverables, explicitly designed to serve Employment/Software Dev/JV/Lease/Agreement-to-Sell later)
Query Validator	📐 Designed (TRD §3.5) — tied to undefined Litigation/Consulting screens, no build evidence
RERA Filing Guides (curated, state-sourced)	📐 Designed only — content curation is Nitesh's task, no evidence of progress
---
7. Current Status Snapshot
7.1 Confirmed build log (✅ — chronological, per pasted evidence)
Sprint 0 [E1, commit `28e6e85`]: foundations, IK API spike, LLM Gateway, PII masker, "Hello matter" exit criterion met.
Sprint 1 [E1, commit `0b165e8`]: statute RAG + citation verifier + renderer gate + hybrid retrieval + keyword search + golden harness. Several RLS/RPC-hardening commits alongside.
Sprint 2 build (local, later committed) [E2, commit `987a1da`]: 5 Contracts templates (NDA, Service Agreement, Consultancy, MoU, Employment), template engine with clause-review workflow, bulk-keep-boilerplate action, re-seed guard, migrations 0007–0008, deployment infra, CORS env-var support, PII masker hardening. 43 files changed, 9,329 insertions.
⚠ Process incident, worth carrying forward as a standing risk: this entire Sprint 2 body of work sat uncommitted locally for a period while Render kept serving stale Sprint-1 code (confirmed via `openapi.json` showing only 5 routes, no `/api/contracts/*`, despite `contracts.router` already being imported in `main.py`) [E4]. Diagnosed and fixed by committing everything in one large push. Recommended standing instruction to Claude Code: commit-and-push should be routine at the end of any turn that changed code, not something that has to be requested.
Post-Sprint-2 [E3, "Sprint 2.5" commit]: dashboard rewrite, new `/admin/templates` index page, one nav link — this is Sprint 3's S3.1 item, shipped early and out of its planned slot.
Deployment [E15]: backend live on Render (`vidhidesk.onrender.com`), frontend live on Vercel; Nitesh has accessed the Vercel URL and confirmed it works for him.
Two real bugs found and fixed during build, both worth keeping visible rather than folding into a generic "bugs fixed" line:
"Party A/B" leak [E8]: LLM-generated recitals produced generic placeholder labels instead of actual party names on the first real end-to-end test. Traced to prompt design, not the masker; fixed.
Review-state regression [E11]: fixing the above required re-seeding clause content, which silently left the old `review_status` (e.g. "kept") attached to the new, substantively different text — meaning a clause could show as "reviewed" against content nobody had actually reviewed. Root cause documented in `lessons_learned.md` as a standing, unautomated manual-check step (auto-invalidating review status on every content change risks over-invalidating trivial wording tweaks) — this is an accepted limitation, not a bug still open.
7.2 Not started / no evidence
Sprint 2 Sessions 4–5 (icon system, mobile pass), all of Sprints 4–6, the entire Litigation module.
7.3 Bounding statement (repeat of §0.1, stated again because it matters most here)
Everything in §7.1 is bounded by the last evidence pasted into this chat. Batches 5–7 (the remaining 5 contract templates) were discussed and approved in principle but have no confirming evidence pasted — do not mark them ✅ until a fresh `git log` / `openapi.json` check is done.
---
8. Flagged Gaps
8.1 ⚠ Litigation module has no screens, no mockups, no dedicated sprint — UNRESOLVED since v1
Still true as of this version. Module 1 in the original SOW, meant to ship first, now has zero product surface. Decision still needed: allocate a sprint (proposed Sprint 3.5 or a new Sprint 7) mirroring Consulting's screens, or explicitly document deferral past Phase 1 exit.
8.2 `template_clauses` / `clause_reviews` — ✅ RESOLVED IN CODE, gap was documentation drift only
v1 flagged these tables as undefined. Correction: they were defined and built via migration 0007 [E5] — `template_clauses`, `clause_reviews`, `draft_clause_fills`, plus `templates.template_key` and `templates.review_status`, with RLS policies and CHECK constraints (`clause_reviews_redraft_has_text`, `clause_reviews_delete_has_notes`). The remaining gap is purely documentary: `02_Technical_Requirements.md` §4's data model was never updated to reflect this. Action: addend the TRD, don't re-design the schema — it already exists and works.
8.3 Sprint 3's two admin features — partially requested, not confirmed built
Cross-template shared-clause detection was requested in the Batch 4.5 message [E13] but no build confirmation exists. Content-hash mismatch warning has no request or build evidence at all. Action: confirm S3.2's actual status with a fresh check; S3.3 still needs the original technical spike (similarity detection, hash-comparison logic, new columns).
8.4 RERA complaint filing / walkthrough progress — still no endpoints or tables (unchanged)
8.5 Settings screen fields exceed current `users` schema — unchanged, still a gap
8.6 Matter export/archive has no route — unchanged, still a gap
8.7 Global state-selector persistence — unchanged, still a gap
8.8 ⚠ NEW — Planning unit (Stitch "sessions") doesn't match actual build unit (template "batches")
The Stitch Mockup Plan and Nav Spec track progress in UI-design sessions (Session 1 = Intake Form, Session 2 = Draft View, etc.). The actual Claude Code build tracks progress in template batches (Batch 1a = NDA, Batch 1b = Service Agreement, Batch 2 = Consultancy...). These are different units measuring different things, and mapping one to the other retroactively (as this tracker just did in §5) is lossy — a batch touches intake form + draft view + clause review simultaneously for one template, while a session touches one UI concern across all templates. Action: going forward, track both dimensions separately rather than forcing batch progress into session rows, or this tracker will keep needing lossy reconciliation like the one just performed above.
8.9 ⚠ NEW — Review-state-on-reseed is an accepted limitation, not a closed bug
Documented in §7.1 and `lessons_learned.md` [E11] as a manual-check process: after any clause content change, someone must check whether previously-reviewed clauses need their `review_status` reset. No automated safeguard exists. Worth tracking here explicitly so it doesn't quietly get treated as "fixed" — it's mitigated by process discipline, not by code.
---
9. Open Decisions
Nitesh's design involvement: 📐 confirmed zero involvement in UI decisions; his review is legal-content only.
Nitesh's review pace vs. review queue: 🔍 Inferred (from: 5 templates shipped as beta, all pending clause review, Employment batch built before NDA/Service Agreement were confirmed genuinely reviewed [E11]): the review queue is growing faster than review throughput. This is a live risk, not hypothetical — worth a direct check with Nitesh on cadence.
Litigation sequencing — see §8.1, still the single biggest open item blocking Sprint 4 from delivering what Phase 2 promised.
Batch 5–7 status — needs a fresh evidence pull before any planning assumes those 5 templates exist.
---
10. Handover Instructions
Read in this order: this tracker (§0.1 first) → source docs (§1) → the current codebase directly.
Get a fresh `git log --oneline --decorate --graph -30` before trusting anything in §7 beyond commit `987a1da` / the Sprint 2.5 commit — this document's ✅ tags are bounded by what's been pasted into chat, not live repo state.
Check `/admin/templates` directly to see real clause-review progress — more reliable than any static document.
Before building any screen in §8, resolve its flagged gap first — check whether it's a code gap or a documentation-drift gap (§8.2 shows these need different fixes).
Every screen must: use the exact palette in §3, carry the advocate-review disclaimer, route citations through the Citation Verifier.
When updating this tracker: don't upgrade a tag from 📐/🔍 to ✅ without a fresh evidence citation added to §11. This is the discipline that was missing in v1 and is the entire point of v2.
---
11. Evidence Log
ID	Evidence	Date/Commit
E1	`git log --oneline -10` pasted by Keshav — commits through Sprint 0/1, `28e6e85` through `f55c9bb`	Prior to 3 Aug 2026 chat
E2	Commit `987a1da` — "Sprint 2: Contracts module — 5 templates..." — 43 files changed, 9,329 insertions; file listing included `contracts.py` router, `intake-form.tsx`, `contracts/page.tsx`, `contracts/[matterId]/page.tsx`, `admin/templates/[key]/page.tsx`, 5 template schema/docx pairs	Pasted 3 Aug 2026
E3	"Sprint 2.5: dashboard + admin templates index + nav link" commit — `dashboard/page.tsx` rewrite, `admin/templates/page.tsx` new, `authed-shell.tsx` nav link	Pasted 3 Aug 2026
E4	`openapi.json` grep showing only 5 routes pre-fix (no `/api/contracts/*` despite router import present in `main.py`), then confirmation instructions to verify 14 routes post-redeploy	Pasted 3 Aug 2026
E5	Migration `0007_contracts_clause_review.sql` verification queries and results — `template_clauses`, `clause_reviews`, `draft_clause_fills` tables confirmed present; `templates.template_key`, `templates.review_status` columns confirmed typed correctly; RLS policies and CHECK constraints confirmed	Pasted 3 Aug 2026
E6	Migration `0008_generic_clause_conditions_and_numbering.sql` — full file content pasted; `applicable_condition` jsonb column, `heading` column	Pasted 3 Aug 2026
E7	NDA seed script verification queries — template row, 11 clauses (8 fixed_boilerplate + 3 llm_fillable), 3 state_rules rows (Delhi/Maharashtra/UP, "pending verification" flags)	Pasted 3 Aug 2026
E8	Service Agreement live E2E — screenshot/description of generated draft; confirmed correct field substitution, `an_or_a` filter, milestone-payment branch, SLA clause, deliverables list, arbitration/governing-law fields; also where the "Party A/B" leak bug and description-truncation issue were found	Pasted 3 Aug 2026
E9	Consultancy + MoU click-through signoff messages — "read clean," proceed to next batch	Pasted 3 Aug 2026
E10	Employment batch — field/clause plan discussed and approved; no build-completion confirmation pasted	3 Aug 2026
E11	Data-integrity sweep — re-seed review-state regression found (NDA recitals `clause_reviews` row from Aug 1 deleted, `template_clauses` reset to unreviewed after confirming zero `draft_clause_fills` referenced it)	Pasted 3 Aug 2026
E12	Conversation-history bug diagnosis + fix approval — bounded 6-message window, `masked_prompt` reuse for prior user turns; PII masker hardening (per-string masking, statute-abbreviation allowlist, no case-title allowlist)	Pasted 3 Aug 2026
E13	"Batch 4.5" message — bulk-keep-boilerplate + cross-template shared-clause detection requested; no completion confirmation pasted	3 Aug 2026
E14	Batches 5–7 (Leave & Licence, Lease Deed, Agreement to Sell, Joint Venture, Software Development) — sequencing approved in principle; no build evidence pasted	3 Aug 2026
E15	Render (`vidhidesk.onrender.com`) and Vercel deployment confirmed live; Nitesh confirmed access and functionality	Pasted 3 Aug 2026
---
Document version: v2 — 3 August 2026
Owner: Keshav
Change from v1: retrofitted every status claim with the 5-tier evidence tagging system (§0.1), added the Evidence Log (§11), corrected the Contracts-first rationale (§1.1), resolved the template_clauses/clause_reviews gap in code while flagging it as a documentation-drift gap (§8.2), added two new gaps (§8.8 session-vs-batch tracking mismatch, §8.9 review-state-on-reseed as accepted limitation), and updated §7 with the actual confirmed build log including both real bugs found.
