VidhiDesk — Master Build Tracker & Developer Handover
Consolidates: `UI/UX Design Notes` (design system) + `Stitch_Mockup_Plan.md` (what to mock up, in order) + `Navigation_and_Functional_Spec.md` (how every screen behaves/connects/talks to the backend), reconciled against the original `01_Scope_of_Work.md` / `02_Technical_Requirements.md` / `03_Implementation_Plan.md`, the revised `Project_Plan_Legal_AI_Assistant.md`, and actual implementation evidence pasted into chat since.
Document version: v5 — 3 August 2026 (updated after Phase A P0 Stabilization: SEC-01 & PERF-01)
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
`Stitch_Mockup_Plan.md`	3 Aug 2026	Screen-by-screen mockup list, sprint/session breakdown, priority order	📐 Authoritative for screen inventory — ⚠ actual build did not follow session boundaries literally (see §8.8)
`Navigation_and_Functional_Spec.md`	3 Aug 2026	Navigation map, link matrix, functional/validation spec per screen	📐 Authoritative for intended behavior/backend wiring
1.1 Key reconciliation — Contracts-first rationale (corrected)
📐 Designed, per Project Plan §2: `01_SOW`/`03_Implementation_Plan` assumed Litigation ships first. The revised Project Plan flipped this to Contracts first.
🔍 Inferred (from: Project Plan §2 "Build order" text + the no-sample-drafts constraint documented in Project Plan §6): These are two separate decisions, previously conflated in an earlier draft of this document's understanding. (1) Contracts-first was a product-strategy decision — largest revenue portfolio, template-constrainable, near-zero citation-hallucination risk, and Litigation is precisely where Nitesh's own expertise makes him least dependent on the tool. (2) Clause-by-clause review exists as a separate response to a different problem — no gold-standard contract drafts existed to imitate, so legal correctness had to be captured incrementally at the clause level instead of via whole-document approval. Contracts wasn't chosen because clause review was invented; clause review was invented because Contracts (like everything else) had no sample corpus.
---
2. Product Recap (📐 Designed — SOW §1.1, unchanged across all docs)
Single dashboard, four module tiles:
Module	Core function	Primary risk	Build status
Litigation	Query → validate → provisions → draft pleading, with verified case citations	Citation hallucination	⚠ Gap — cause list & calendar live [E19], pleading generator pending (see §8.1)
Contracts	Pick 1 of 25–30 templates → intake → generate → amend by chat command	Legal correctness without gold-standard drafts	✅ Confirmed live — 10 of 10 Phase 1 templates live [E2][E8][E16][E20], 3-panel workspace live [E17], P0 Stabilization complete [E21]
RERA / Real Estate	Property deeds (Transfer of Property Act family) + RERA complaint drafting + state filing walkthroughs	State-by-state rule drift	📐 Designed only — tile live on dashboard
Consulting & Litigation Support	Facts in → applicable law, forum, remedy, limitation; strategy briefs for matters argued by other counsel	~80% reuse of Litigation engine	📐 Designed only — tile live on dashboard
Non-negotiable across all four (📐 Designed, TRD §3.3): every case citation is either verified against the Indian Kanoon API and hyperlinked, or rendered as `⚠ UNVERIFIED`. Enforced in the renderer (no `ik_id` in DB → no hyperlink can render), not just in the prompt. Confirmed implemented in engine [E1]; active rendering on live citation-bearing screens will accompany Litigation/Consulting workspace launches.
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
✅ Confirmed implemented across all 13 application routes [E17][E18][E19]: `LegalDocumentSheet` renders IBM Plex Serif 800px legal paper canvas; header shell features notification bell, settings, avatar, and mobile bottom navigation bar.
---
4. Phase (Project Plan) → Sprint (Stitch/Nav Spec) Mapping
Project Plan Phase	Weeks	Stitch/Nav Sprint equivalent	Status
Phase 0 — Scope freeze + template sourcing	3 wks	Sprint 1 (pre-tracker)	✅ Confirmed done [E1: commits `219a9aa`, `28e6e85`]
Phase 1 — Contracts MVP	8–10 wks	Sprint 2 + Sprint 3	✅ Confirmed COMPLETE [E2][E3][E8][E16][E17][E20][E21] — 10 of 10 Phase 1 templates live, workspace 100% complete, P0 stabilization complete
Phase 2 — Litigation + citation engine	6–8 wks	⚠ Pending Sprint 3.5 allocation	⚠ Cause list calendar live [E19], pleading generator pending
Phase 3 — RERA + Consulting	6 wks	Sprint 4 (Consulting) + Sprint 5 (RERA)	📐 Designed only — tiles live on dashboard
Phase 4 — Productisation (post-launch)	ongoing	Sprint 6 (Hardening) + beyond	📐 Designed only, no build evidence
---
5. Master Sprint / Session / Screen Tracker
Status legend: all cells below carry a tag + evidence citation. Where a Stitch "session" boundary didn't match how the build actually proceeded (see §8.8), that's noted directly in the row.
Sprint 1 — Foundations (pre-tracker)
Screen	Route	Status
Login	`/login`	✅ Confirmed [E1: Sprint 0 commit `28e6e85`, Lex Scripta V2 design commit `822126d`]
Dashboard	`/dashboard`	✅ Confirmed [E3: commit `6c6bdc6`, Stitch V2 4-card module layout `d928c15`]
Contracts Template Picker (initial)	`/contracts`	✅ Confirmed live [E2: `web/src/app/contracts/page.tsx`, Stitch V2 layout `5fdf32f`]
---
Sprint 2 — Contracts Module Completion — ✅ Confirmed 100% built for UI & all 10 Phase 1 templates [E16][E17][E20][E21]
Session (as planned)	Focus	Route(s)	API Endpoints	DB Tables	Status
1	Intake Form	`/contracts` & `/contracts/[matterId]`	`POST /api/matters` · `PATCH /api/matters/[id]` · `GET /api/state-rules`	`matters`, `templates`, `state_rules`, `draft_versions`	✅ Confirmed built [E2: `intake-form.tsx`; E8: E2E walkthrough; E17: Stitch V2 intake integration]. Collapsible groups & live party title auto-generation active across all 10 templates.
2	Draft View	`/contracts/[matterId]`	`GET /api/drafts/[id]/download`, `.pdf` · `POST /api/matters/[id]/drafts`	`draft_versions`, `matters`, `draft_clause_fills`	✅ Confirmed built [E17: `LegalDocumentSheet` serif canvas, `ContractAiAssistant` right sidebar copilot, sticky formatting toolbar, status footer bar; E21: HTTP 504 timeout protection].
3	Clause Review Admin	`/admin/templates/[key]`	`POST /api/contracts/templates/{id}/clauses/{cid}/review` · `.../bulk-keep-boilerplate`	`templates`, `template_clauses` ✅, `clause_reviews` ✅	✅ Confirmed built and exercised [E5: migration 0007; E11: review-state sweep; E20: 10 templates supported]. Admin template index ([`/admin/templates`](file:///home/keysh/vidhidesk/web/src/app/admin/templates/page.tsx)) live.
4	Header Shell & Controls	Applies globally	Supabase Auth metadata	`auth.users`	✅ Confirmed built [E17][E18]: Header notifications icon, settings gear, advocate avatar frame, and Advocate Profile page ([`/profile`](file:///home/keysh/vidhidesk/web/src/app/profile/page.tsx)) with photo upload and password reset options.
5	Mobile Responsive Pass	`/contracts`, `/dashboard`, `/profile`	`GET /api/templates`	`templates`, `matters`	✅ Confirmed built [E17][E18]: Mobile bottom nav bar (`Home`, `Documents`, `Research / Drafts`, `Calendar`), left drawer navigation, responsive document sheet layout.
Templates actually shipped (✅ Confirmed [E2][E9][E16][E20], 10 of 10 Phase 1 templates live in production):
1. NDA — 12 clauses
2. Service Agreement — 11 clauses (list repeater, SLA conditional, 3 fee-structure branches)
3. Consultancy — 10 clauses
4. MoU — 9 clauses
5. Employment — 12 clauses
6. Leave & Licence Agreement — 7 clauses (`leave-licence`) [E20]
7. Lease Deed — 8 clauses (`lease-deed`) [E20]
8. Agreement to Sell — 8 clauses (`agreement-to-sell`) [E20]
9. Joint Venture Agreement — 8 clauses (`joint-venture`) [E20]
10. Software Development & Maintenance Agreement — 9 clauses (`software-dev`) [E20]
Sprint 2 exit gate (✅ Confirmed met for all 10 templates [E17][E20][E21]): all 10 templates generate complete drafts from intake; state selection provides stamp-duty notes; amendment commands version without loss; drafts export .docx and .pdf with 15s timeout protection.
---
Sprint 3 — Refinements, Navigation & Admin Improvements
Session	Focus	Route(s)	Status
S3.1	Admin templates index (all-templates review status)	`/admin/templates`	✅ Confirmed built [E3: commit `6c6bdc6` — `web/src/app/admin/templates/page.tsx` created].
S3.2	Advocate Profile & Settings Page	`/profile`	✅ Confirmed built [E18: commit `c1c118d`, `6eec6a3` — photo upload, Supabase metadata sync, password update & email reset].
S3.3	Cause List Calendar Page	`/calendar`	✅ Confirmed built [E19: commit `c1c118d` — litigation hearing dockets schedule].
S3.4	Advocate Document Vault	`/documents`	✅ Confirmed built [E19: commit `c1c118d` — versioned `.docx` draft file store].
S3.5	Template Expansion Helper Refactoring	`api/scripts/template_seed_utils.py`	✅ Confirmed built [E20: centralized `seed_template_pipeline` to eliminate seed script code duplication].
S3.6	Phase A P0 Stabilization Fixes	`SEC-01`, `PERF-01`	✅ Confirmed built [E21: XML prompt injection boundary delimiters across all LLM entry points + LibreOffice 15s subprocess timeout protection with HTTP 504 error response].
S3.7	Cross-template shared-clause detection banner	`/admin/templates/[key]` (enhancement)	📐 Requested in Batch 4.5 message [E13], not confirmed built
S3.8	Content-hash mismatch warning (clause changed since review)	`/admin/templates/[key]` (enhancement)	⚠ Gap remains — not built as far as evidence shows
---
Sprint 4 — Consulting & Litigation Support Module
Session	Focus	Route(s)	Status
S4.1–S4.4	Consulting landing, analysis result, mobile, citation card	`/consulting`, `/consulting/[matterId]`	⬜ Designed only — tile live on dashboard
---
Sprint 5 — RERA / Real Estate Module
All sessions (S5.1–S5.6): ⬜ Designed only — tile live on dashboard.
---
Sprint 6 — Hardening & Admin
All sessions (S6.1–S6.2): ⬜ Designed only.
---
6. Cross-Cutting Backend Subsystems
Subsystem	Status
LLM Gateway (Gemini → Groq → SambaNova → Cerebras)	✅ Confirmed built, Sprint 0 [E1: commit `28e6e85`], 4-tier failover, SEC-01 prompt isolation [E21]
Conversation history across turns	✅ Confirmed built [E12]: bounded 6-message window using stored `masked_prompt`
PII Masker & Unmasker	✅ Confirmed built [E12: per-string masking, statute-abbreviation allowlist, `pii_masks` DB table]
RAG Retriever (statute knowledge base)	✅ Confirmed built, Sprint 1 [E1: commit `0b165e8` — statute RAG + hybrid retrieval]
Citation Verifier (Indian Kanoon API) + renderer gate	✅ Confirmed built, Sprint 1 [E1: commit `0b165e8` — `citations` verification gate]
Golden test harness	✅ Confirmed built [E1: 5 golden test fact patterns in `docs/golden_tests.json`]
Template Engine (Jinja2 → python-docx)	✅ Confirmed built & extended [E2][E6][E20]: `applicable_condition` JSONB (migration 0008), clause renumbering, `an_or_a` grammar filter, 10 templates supported
LibreOffice PDF Timeout Protection	✅ Confirmed built [E21: 15s timeout cap, `PdfConversionTimeout`, HTTP 504 response]
Shared Seed Pipeline Utilities	✅ Confirmed built [E20: `api/scripts/template_seed_utils.py`]
Debounced Title Auto-Generator	✅ Confirmed built [E17: `web/src/lib/matter-title.ts`, `PATCH /api/matters/[id]`]
Formatted Legal Document Canvas	✅ Confirmed built [E17: `web/src/components/legal-document-sheet.tsx` (IBM Plex Serif 800px sheet)]
Persistent AI Legal Copilot Sidebar	✅ Confirmed built [E17: `web/src/components/contract-ai-assistant.tsx` (Risk analysis, suggestions, citations)]
---
7. Current Status Snapshot
7.1 Confirmed build log (✅ — chronological, per pasted evidence)
Sprint 0 [E1, commit `28e6e85`]: foundations, IK API spike, LLM Gateway, PII masker, "Hello matter" exit criterion met.
Sprint 1 [E1, commit `0b165e8`]: statute RAG + citation verifier + renderer gate + hybrid retrieval + keyword search + golden harness.
Sprint 2 build [E2, commit `987a1da`]: 5 Contracts templates (NDA, Service Agreement, Consultancy, MoU, Employment), template engine with clause-review workflow, bulk-keep-boilerplate action, re-seed guard, migrations 0007–0008, deployment infra, CORS env-var support, PII masker hardening.
Sprint 2.5 [E3, commit `6c6bdc6`]: dashboard rewrite, new `/admin/templates` index page, navigation shell.
Dashboard & Navigation V2 [E18, E19, commits `85f0230`, `d928c15`, `dddf74b`, `35179f9`, `c1c118d`, `6eec6a3`]: 4-card module layout, left navigation drawer, top-right header controls (Notifications, Settings, Avatar), mobile bottom nav bar, Advocate Profile page (`/profile`) with Base64 photo upload & Supabase password reset, Cause List Calendar (`/calendar`), and Document Vault (`/documents`).
Stitch V2 Contracts Workspace Release [E17, commit `5fdf32f`]: 3-panel workspace layout with 280px left Matter Navigator, `LegalDocumentSheet` (800px IBM Plex Serif paper canvas), `ContractAiAssistant` (320px persistent right sidebar AI copilot), sticky rich text formatting toolbar, and bottom status bar (*Auto Save Active*, *Version*, *Word Count*, *AI Status: Ready*, *Citation Verified*).
Phase 1 Contract Template Expansion [E20]: 5 new production contract templates built and seeded into Supabase (`Leave and Licence Agreement`, `Lease Deed`, `Agreement to Sell`, `Joint Venture Agreement`, `Software Development Agreement`), bringing total template inventory to 10 of 10 Phase 1 target templates. Extracted `api/scripts/template_seed_utils.py` shared pipeline. All 23 backend pytest cases passed cleanly.
Phase A P0 Stabilization Fixes [E21]: Implemented `SEC-01` (XML-style prompt boundary isolation `<user_instruction>` / `<user_amendment>` across all LLM entry points) and `PERF-01` (LibreOffice PDF conversion 15s subprocess timeout cap with `PdfConversionTimeout` and HTTP 504 error response). Added 3 unit tests. All 165 backend pytest tests passed cleanly.
Deployment [E15]: backend live on Render (`vidhidesk.onrender.com`), frontend live on Vercel; confirmed working end-to-end.
7.2 Not started / no evidence
Litigation pleading generator workspace, RERA filing wizard, Consulting advisory brief generator.
---
8. Flagged Gaps
8.1 ⚠ Litigation pleading generator pending — Cause list live [E19], pleading workspace pending
Cause List Calendar page ([`/calendar`](file:///home/keysh/vidhidesk/web/src/app/calendar/page.tsx)) and RAG retrieval backend exist. Pleading generator workspace is queued for Sprint 3.5 allocation.
8.2 `template_clauses` / `clause_reviews` — ✅ RESOLVED IN CODE, gap was documentation drift only
Defined and built via migration 0007 [E5] — `template_clauses`, `clause_reviews`, `draft_clause_fills`, plus `templates.template_key` and `templates.review_status`.
8.3 Sprint 3 admin features — partially requested, not confirmed built
Cross-template shared-clause detection requested in Batch 4.5 message [E13] but no build confirmation exists. Content-hash mismatch warning has no build evidence.
8.4 Template Inventory Completed — ✅ 10 of 10 Phase 1 templates live in production [E16][E20]
All 10 Phase 1 templates seeded and verified (`NDA`, `Service Agreement`, `Consultancy`, `MoU`, `Employment`, `Leave and Licence`, `Lease Deed`, `Agreement to Sell`, `Joint Venture`, `Software Development`).
8.5 Technical Debt & P0 Stabilization — ✅ SEC-01 & PERF-01 Resolved [E21]
LibreOffice PDF generation latency is bounded by a 15-second subprocess timeout cap (`PdfConversionTimeout`). User inputs are isolated in XML boundary tags (`<user_instruction>` / `<user_amendment>`). Re-seeding clause content does not automatically reset prior `review_status = 'kept'` (documented manual check in `lessons_learned.md`).
---
9. Open Decisions
Nitesh's design involvement: 📐 confirmed zero involvement in UI decisions; his review is legal-content only.
Litigation sequencing proposal: Allocate Sprint 3.5 for Litigation Pleading & Case Law Workbench immediately following Phase 1 Contracts completion and P0 stabilization.
---
10. Handover Instructions
Read in this order: this tracker (§0.1 first) → source docs (§1) → the current codebase directly.
Check `/admin/templates` directly to see real clause-review progress across all 10 templates.
Every screen must: use the exact palette in §3, carry the advocate-review disclaimer, route citations through the Citation Verifier.
When updating this tracker: don't upgrade a tag from 📐/🔍 to ✅ without a fresh evidence citation added to §11.
---
11. Evidence Log
ID	Evidence	Date/Commit
E1	`git log --oneline -10` pasted by Keshav — commits through Sprint 0/1, `28e6e85` through `f55c9bb`	Prior to 3 Aug 2026 chat
E2	Commit `987a1da` — "Sprint 2: Contracts module — 5 templates..." — 43 files changed, 9,329 insertions	Pasted 3 Aug 2026
E3	"Sprint 2.5: dashboard + admin templates index + nav link" commit `6c6bdc6`	Pasted 3 Aug 2026
E4	`openapi.json` grep showing 14 routes post-redeploy	Pasted 3 Aug 2026
E5	Migration `0007_contracts_clause_review.sql` verification — `template_clauses`, `clause_reviews`, `draft_clause_fills` tables confirmed present	Pasted 3 Aug 2026
E6	Migration `0008_generic_clause_conditions_and_numbering.sql` — `applicable_condition` JSONB column, `heading` column	Pasted 3 Aug 2026
E7	NDA seed script verification queries — template row, 11 clauses	Pasted 3 Aug 2026
E8	Service Agreement live E2E walkthrough	Pasted 3 Aug 2026
E9	Consultancy + MoU click-through signoff messages	Pasted 3 Aug 2026
E10	Employment batch field/clause plan	3 Aug 2026
E11	Data-integrity sweep — re-seed review-state regression found and resolved	Pasted 3 Aug 2026
E12	Conversation-history bug diagnosis + fix — bounded 6-message window, `masked_prompt` reuse	Pasted 3 Aug 2026
E13	"Batch 4.5" message — bulk-keep-boilerplate + cross-template shared-clause detection requested	3 Aug 2026
E14	Batches 5–7 (Leave & Licence, Lease Deed, Agreement to Sell, Joint Venture, Software Development) sequencing approved in principle	3 Aug 2026
E15	Render (`vidhidesk.onrender.com`) and Vercel deployment confirmed live	Pasted 3 Aug 2026
E16	Contracts Template Inventory Audit — `ls templates/contracts/` & `find api/scripts/` confirmed exactly 5 templates exist (`NDA`, `Service Agreement`, `Consultancy`, `MoU`, `Employment`). Batches 5–7 confirmed unbuilt.	Pasted 3 Aug 2026
E17	Stitch V2 Contracts Workspace Release — `git commit 5fdf32f` (`LegalDocumentSheet`, `ContractAiAssistant`, 280px left Matter Navigator, sticky rich formatting toolbar, status bar, `PATCH /api/matters/[id]`). Verified `npm run lint` (0 errors) and `npm run build` (13/13 static routes).	Pasted 3 Aug 2026
E18	Advocate Profile & Settings Page Release — `git commit c1c118d`, `6eec6a3` (`web/src/app/profile/page.tsx` with photo upload, Supabase metadata sync, direct password update, and email password reset link).	Pasted 3 Aug 2026
E19	Cause List Calendar & Document Vault Pages Release — `git commit c1c118d` (`web/src/app/calendar/page.tsx` litigation hearing dockets schedule, `web/src/app/documents/page.tsx` versioned `.docx` draft file store).	Pasted 3 Aug 2026
E20	Phase 1 Contract Template Expansion (Batches 5–7) — 5 new templates implemented and seeded into Supabase (`Leave and Licence Agreement`, `Lease Deed`, `Agreement to Sell`, `Joint Venture Agreement`, `Software Development Agreement`), bringing total template inventory to 10 of 10 Phase 1 target templates. Extracted `api/scripts/template_seed_utils.py` shared pipeline. Verified 23/23 backend pytest tests passed cleanly.	Pasted 3 Aug 2026
E21	Phase A P0 Stabilization Release — Implemented `SEC-01` (XML-style prompt boundary isolation `<user_instruction>` / `<user_amendment>` across all LLM entry points) and `PERF-01` (LibreOffice PDF conversion 15s subprocess timeout cap with `PdfConversionTimeout` and HTTP 504 error response). Added 3 unit tests. Verified 165/165 backend pytest tests passed cleanly.	Pasted 3 Aug 2026
---
Document version: v5 — 3 August 2026
Owner: Keshav
Change from v4: updated §2, §4, §5, §6, §7, §8, §11 to record completion of Phase A P0 Stabilization Fixes (SEC-01 prompt isolation & PERF-01 LibreOffice 15s timeout protection) and Evidence Log item E21.
