VidhiDesk — Master Build Tracker & Developer Handover
Consolidates: `UI/UX Design Notes` (design system) + `Stitch_Mockup_Plan.md` (what to mock up, in order) + `Navigation_and_Functional_Spec.md` (how every screen behaves/connects/talks to the backend), reconciled against the original `01_Scope_of_Work.md` / `02_Technical_Requirements.md` / `03_Implementation_Plan.md`, the revised `Project_Plan_Legal_AI_Assistant.md`, and actual implementation evidence pasted into chat since.
Document version: v13 — 5 August 2026 (updated with mandatory Visual Design Review phase in Google Stitch UI Governance)
Status: Living tracker — update the Status column, and its evidence tag, as work lands.
---
0. How to use this document
Read §0.1 (evidence tagging system) first — every status claim in this document is tagged, and the tag changes what you're allowed to trust it for.
Read §0.2 (Google Stitch UI Governance) — mandatory 6-step lifecycle including Visual Design Review before implementation.
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
0.2 Google Stitch UI Governance
Google Stitch is the single authoritative source for all UI/UX design across VidhiDesk (Contracts, Litigation, RERA, Consulting, Administration). Implementation must never become the source of UI design.

Every UI screen must pass through this mandatory 6-step lifecycle before code is written:
1. **Step 1: Architecture Design:** Define business workflow, user journey, information architecture, and required components (No UI implementation).
2. **Step 2: Google Stitch Verification:** Audit whether an appropriate Google Stitch design already exists. Provide module, screen name, Stitch project ID, screen name/ID, availability status, confidence %, screenshot evidence link, gap analysis, and recommendation. A screen must NOT be marked "Verified Existing" or "Verified Partial" unless screenshot evidence has been reviewed.
3. **Step 2.5: Visual Design Review:** Open the actual Google Stitch screen. Conduct a visual inspection covering: Full-size screenshot, UX review, Missing elements, Incorrect elements, Design inconsistencies, Mobile considerations, Accessibility observations, Business workflow coverage, and Final Recommendation (`Approved without changes`, `Minor Stitch refinement required`, `Major redesign required`).
4. **Step 3: Design Generation & Refinement:** If a screen is Partial or requires refinement, produce an updated Google Stitch prompt, generate/refine the screen in Stitch, and re-review.
5. **Step 4: Design Approval:** Obtain explicit user signoff on the generated/verified Stitch design. Approved Stitch designs become the UI source of truth.
6. **Step 5: Implementation:** Only after approval, build React/Next.js components, wire backend APIs, connect business logic, and integrate AI services.

**Mandatory UI Tracker Lifecycle States:**
- `Verified Existing (Screenshot attached)`
- `Verified Partial (Screenshot attached)`
- `Visual Design Review Completed`
- `Newly Generated in Stitch`
- `Approved for Implementation`
- `Implemented`

No screen may move directly from "Designed" to "Implemented".
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
`LITIGATION_ARCHITECTURE.md`	3 Aug 2026	Sprint 3.5 Litigation Module architecture, database schemas, RAG pipeline, IK integration, screen specs	📐 Authoritative for Sprint 3.5 Litigation execution [E23]
1.1 Key reconciliation — Contracts-first rationale (corrected)
📐 Designed, per Project Plan §2: `01_SOW`/`03_Implementation_Plan` assumed Litigation ships first. The revised Project Plan flipped this to Contracts first.
🔍 Inferred (from: Project Plan §2 "Build order" text + the no-sample-drafts constraint documented in Project Plan §6): These are two separate decisions, previously conflated in an earlier draft of this document's understanding. (1) Contracts-first was a product-strategy decision — largest revenue portfolio, template-constrainable, near-zero citation-hallucination risk, and Litigation is precisely where Nitesh's own expertise makes him least dependent on the tool. (2) Clause-by-clause review exists as a separate response to a different problem — no gold-standard contract drafts existed to imitate, so legal correctness had to be captured incrementally at the clause level instead of via whole-document approval. Contracts wasn't chosen because clause review was invented; clause review was invented because Contracts (like everything else) had no sample corpus.
---
2. Product Recap (📐 Designed — SOW §1.1, unchanged across all docs)
Single dashboard, four module tiles:
Module	Core function	Primary risk	Build status
Litigation	Query → validate → provisions → draft pleading, with verified case citations	Citation hallucination	📐 Designed in full [E23] — cause list & calendar live [E19], Sprint 3.5 workspace architecture documented in `LITIGATION_ARCHITECTURE.md`
Contracts	Pick 1 of 25–30 templates → intake → generate → amend by chat command	Legal correctness without gold-standard drafts	✅ Confirmed live — 10 of 10 Phase 1 templates live [E2][E8][E16][E20], 3-panel workspace live [E17], P0 Stabilization complete [E21][E22], canonical template_key normalization live [E25], Matter-Centric Loading Model live [E26], PROFILE-01 advocate profile isolation live [E27]
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
Phase 1 — Contracts MVP	8–10 wks	Sprint 2 + Sprint 3	✅ Confirmed COMPLETE [E2][E3][E8][E16][E17][E20][E21][E22][E24][E25][E26][E27] — 10 of 10 Phase 1 templates live, workspace 100% complete, all P0 backend & frontend stabilization complete, template key normalization complete [E25], Matter-centric loading model complete [E26], PROFILE-01 complete [E27]
Phase 2 — Litigation + citation engine	6–8 wks	Sprint 3.5 (Litigation Pleading & Case Law Workbench)	📐 Architecture designed [E23] (`docs/LITIGATION_ARCHITECTURE.md`), pending user implementation signoff
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
Sprint 2 — Contracts Module Completion — ✅ Confirmed 100% built for UI & all 10 Phase 1 templates [E16][E17][E20][E21][E22][E24][E25][E26][E27]
Session (as planned)	Focus	Route(s)	API Endpoints	DB Tables	Status
1	Intake Form	`/contracts` & `/contracts/[matterId]`	`POST /api/matters` · `PATCH /api/matters/[id]` · `GET /api/state-rules`	`matters`, `templates`, `state_rules`, `draft_versions`	✅ Confirmed built [E2: `intake-form.tsx`; E8: E2E walkthrough; E17: Stitch V2 intake integration; E26: Matter-centric loading model]. Collapsible groups & live party title auto-generation active across all 10 templates.
2	Draft View	`/contracts/[matterId]`	`GET /api/drafts/[id]/download`, `.pdf` · `POST /api/matters/[id]/drafts`	`draft_versions`, `matters`, `draft_clause_fills`	✅ Confirmed built [E17: `LegalDocumentSheet` serif canvas, `ContractAiAssistant` right sidebar copilot, sticky formatting toolbar, status footer bar; E21: HTTP 504 timeout protection; E22: mobile AI slide-over sheet].
3	Clause Review Admin	`/admin/templates/[key]`	`POST /api/contracts/templates/{id}/clauses/{cid}/review` · `.../bulk-keep-boilerplate`	`templates`, `template_clauses` ✅, `clause_reviews` ✅	✅ Confirmed built and exercised [E5: migration 0007; E11: review-state sweep; E20: 10 templates supported]. Admin template index ([`/admin/templates`](file:///home/keysh/vidhidesk/web/src/app/admin/templates/page.tsx)) live.
4	Header Shell & Controls	Applies globally	Supabase Auth metadata	`auth.users`	✅ Confirmed built [E17][E18][E27]: Header notifications icon, settings gear, advocate avatar frame, and Advocate Profile page ([`/profile`](file:///home/keysh/vidhidesk/web/src/app/profile/page.tsx)) with photo upload, Supabase user_metadata server-first loading [E27], onboarding profile alert banner, and password reset options.
5	Mobile Responsive Pass	`/contracts`, `/dashboard`, `/profile`	`GET /api/templates`	`templates`, `matters`	✅ Confirmed built [E17][E18][E22]: Mobile bottom nav bar (`Home`, `Documents`, `Research / Drafts`, `Calendar`), left drawer navigation, responsive document sheet layout, and mobile floating AI assistant trigger button & slide-over sheet.
Templates actually shipped (✅ Confirmed [E2][E9][E16][E20][E25], 10 of 10 Phase 1 templates live in production):
1. NDA — 12 clauses (`nda`)
2. Service Agreement — 11 clauses (`service-agreement`) [E25]
3. Consultancy — 10 clauses (`consultancy`)
4. MoU — 9 clauses (`mou`)
5. Employment — 12 clauses (`employment`)
6. Leave & Licence Agreement — 7 clauses (`leave-licence`) [E20]
7. Lease Deed — 8 clauses (`lease-deed`) [E20]
8. Agreement to Sell — 8 clauses (`agreement-to-sell`) [E20]
9. Joint Venture Agreement — 8 clauses (`joint-venture`) [E20]
10. Software Development & Maintenance Agreement — 9 clauses (`software-dev`) [E20]
Sprint 2 exit gate (✅ Confirmed met for all 10 templates [E17][E20][E21][E22][E24][E25][E26][E27]): all 10 templates generate complete drafts from intake; state selection provides stamp-duty notes; amendment commands version without loss; drafts export .docx and .pdf with 15s timeout protection; all 10 templates render cleanly on Contracts Workspace grid; profile page isolates advocate data per user without hardcoded defaults [E27].
---
Sprint 3 — Refinements, Navigation & Admin Improvements
Session	Focus	Route(s)	Status
S3.1	Admin templates index (all-templates review status)	`/admin/templates`	✅ Confirmed built [E3: commit `6c6bdc6` — `web/src/app/admin/templates/page.tsx` created].
S3.2	Advocate Profile & Settings Page	`/profile`	✅ Confirmed built [E18: commit `c1c118d`, `6eec6a3`; E27: PROFILE-01 removed demo strings, server-first user_metadata persistence, onboarding banner].
S3.3	Cause List Calendar Page	`/calendar`	✅ Confirmed built [E19: commit `c1c118d` — litigation hearing dockets schedule].
S3.4	Advocate Document Vault	`/documents`	✅ Confirmed built [E19: commit `c1c118d` — versioned `.docx` draft file store].
S3.5	Template Expansion Helper Refactoring	`api/scripts/template_seed_utils.py`	✅ Confirmed built [E20: centralized `seed_template_pipeline` to eliminate seed script code duplication].
S3.6	Phase A P0 Backend Stabilization Fixes	`SEC-01`, `PERF-01`	✅ Confirmed built [E21: XML prompt injection boundary delimiters across all LLM entry points + LibreOffice 15s subprocess timeout protection with HTTP 504 error response].
S3.7	Phase 1 Frontend P0 Stabilization Fixes	`MOB-01`, `UX-01`, `UX-02`	✅ Confirmed built [E22: Mobile AI Assistant floating trigger & slide-over sheet + real template category filter checkboxes with combined search & empty state + Lex Scripta error recovery card with retry button].
S3.8	Sprint 3.5 Litigation Architecture Design	`docs/LITIGATION_ARCHITECTURE.md`	📐 Designed in full [E23: complete 15-section architecture specification, database additions, RAG pipeline, IK integration, security model, and component reuse breakdown].
S3.9	LLM Gateway Intra-Provider Model Pool Failover	`api/app/services/llm_gateway.py`	✅ Confirmed built [E24: intra-provider model pools with pinned versions; Gemini 4 models, Groq 5 models, SambaNova 1 model, Cerebras 3 models; per-model transient retry + position logging].
S3.10	Canonical Template Key Normalization	`service-agreement`	✅ Confirmed built [E25: standardized all 10 templates to kebab-case across DB, seed scripts, schemas, frontend filter, migration 0009, and regression tests].
S3.11	Matter-Centric Loading Model Release	`/contracts/{matterId}`	✅ Confirmed built [E26: added template_id column to matters table (migration 0009/0010), updated MatterCreate/Out schemas, standardized get_template for UUID & slug lookup, clean matter-centric routing without requiring ?template=].
S3.12	PROFILE-01 Advocate Profile Isolation Release	`/profile`	✅ Confirmed built [E27: removed hardcoded advocate demo values, server-first user_metadata loading, onboarding alert banner for incomplete profiles, regression tests].
S3.13	Cross-template shared-clause detection banner	`/admin/templates/[key]` (enhancement)	📐 Requested in Batch 4.5 message [E13], not confirmed built
S3.14	Content-hash mismatch warning (clause changed since review)	`/admin/templates/[key]` (enhancement)	⚠ Gap remains — not built as far as evidence shows
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
LLM Gateway (Gemini → Groq → SambaNova → Cerebras)	✅ Confirmed built, Sprint 0 [E1: commit `28e6e85`], 4-tier provider failover, intra-provider model pools [E24], SEC-01 prompt isolation [E21]
Conversation history across turns	✅ Confirmed built [E12]: bounded 6-message window using stored `masked_prompt`
PII Masker & Unmasker	✅ Confirmed built [E12: per-string masking, statute-abbreviation allowlist, `pii_masks` DB table]
RAG Retriever (statute knowledge base)	✅ Confirmed built, Sprint 1 [E1: commit `0b165e8` — statute RAG + hybrid retrieval]; 📐 Extended for Litigation [E23]
Citation Verifier (Indian Kanoon API) + renderer gate	✅ Confirmed built, Sprint 1 [E1: commit `0b165e8` — `citations` verification gate]; 📐 Extended for Litigation [E23]
Golden test harness	✅ Confirmed built [E1: 5 golden test fact patterns in `docs/golden_tests.json`]
Template Engine (Jinja2 → python-docx)	✅ Confirmed built & extended [E2][E6][E20][E25]: `applicable_condition` JSONB (migration 0008), clause renumbering, `an_or_a` grammar filter, 10 templates supported with kebab-case key normalization [E25]
LibreOffice PDF Timeout Protection	✅ Confirmed built [E21: 15s timeout cap, `PdfConversionTimeout`, HTTP 504 response]
Shared Seed Pipeline Utilities	✅ Confirmed built [E20: `api/scripts/template_seed_utils.py`]
Debounced Title Auto-Generator	✅ Confirmed built [E17: `web/src/lib/matter-title.ts`, `PATCH /api/matters/[id]`]
Formatted Legal Document Canvas	✅ Confirmed built [E17: `web/src/components/legal-document-sheet.tsx` (IBM Plex Serif 800px sheet)]
Persistent AI Legal Copilot Sidebar	✅ Confirmed built [E17: `web/src/components/contract-ai-assistant.tsx` (Risk analysis, suggestions, citations); E22: mobile slide-over sheet]
Template Category Checkbox Filter & Search	✅ Confirmed built [E22: `web/src/app/contracts/page.tsx`; E25: normalized key matching rendering 10/10 templates]
Matter-Centric Loading Model & Clean Routing	✅ Confirmed built [E26: stored template_id on matters table, clean `/contracts/{matterId}` URLs, robust UUID/slug lookup]
Advocate Profile Data Isolation (PROFILE-01)	✅ Confirmed built [E27: server-first user_metadata loading, onboarding alert banner, removed hardcoded advocate demo values]
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
Phase A P0 Backend Stabilization Fixes [E21]: Implemented `SEC-01` (XML-style prompt boundary isolation `<user_instruction>` / `<user_amendment>` across all LLM entry points) and `PERF-01` (LibreOffice PDF conversion 15s subprocess timeout cap with `PdfConversionTimeout` and HTTP 504 error response). Added 3 unit tests. All 165 backend pytest tests passed cleanly.
Phase 1 Frontend P0 Stabilization Fixes [E22]: Implemented `MOB-01` (Mobile AI Assistant floating trigger button & slide-over sheet), `UX-01` (Template category filter checkboxes with real filtering, combined search, and structured empty state), and `UX-02` (Lex Scripta structured error recovery cards with actionable retry buttons). Verified `npm run lint` (0 errors) and `npm run build` (13/13 static routes).
Sprint 3.5 Litigation Architecture Design [E23]: Delivered `docs/LITIGATION_ARCHITECTURE.md` comprehensive architecture specification for Sprint 3.5 Litigation Pleading & Case Law Workbench.
LLM Gateway Intra-Provider Model Pool Failover [E24]: Refactored `api/app/services/llm_gateway.py` to try an ordered pool of pinned models within each provider tier before escalating to the next provider. Configured 4 Gemini models, 5 Groq models, 1 SambaNova model, and 3 Cerebras models. All 169 backend pytest tests passed cleanly.
Canonical Template Key Normalization [E25]: Standardized all template keys to kebab-case (`service-agreement`). Created migration `0009_normalize_template_keys.sql`, updated Supabase database, seed script, JSON schema, and frontend category filter logic (`web/src/app/contracts/page.tsx`). Added 2 backend regression tests. All 10/10 templates render cleanly on Contracts Workspace grid.
Matter-Centric Loading Model Release [E26]: Implemented permanent template association on matters table (`0010_add_template_id_to_matters.sql`), clean `/contracts/{matterId}` URLs, standardized `get_template()` for UUID & slug lookup, and updated all frontend navigation links. Added regression tests. 173/173 backend pytest tests and 13/13 frontend static pages passed.
PROFILE-01 Advocate Profile Isolation Release [E27]: Removed all hardcoded advocate demo values (`Adv. Nitesh Sharma`, `D/1042/2018`, etc.), implemented server-first loading from Supabase Auth `user_metadata`, added a friendly onboarding alert banner for incomplete profiles, and updated `AuthedShell` header avatar synchronization. Added regression tests. 174/174 backend pytest tests and 13/13 frontend static pages passed.
Deployment [E15]: backend live on Render (`vidhidesk.onrender.com`), frontend live on Vercel; confirmed working end-to-end.
7.2 Not started / no evidence
Litigation pleading generator workspace implementation (architecture designed [E23]), RERA filing wizard, Consulting advisory brief generator.
---
8. Flagged Gaps
8.1 ⚠ Litigation pleading generator pending implementation — Architecture designed [E23]
Cause List Calendar page ([`/calendar`](file:///home/keysh/vidhidesk/web/src/app/calendar/page.tsx)) and RAG retrieval backend exist. Full pleading workspace architecture is specified in `docs/LITIGATION_ARCHITECTURE.md` [E23], awaiting user signoff before code implementation.
8.2 `template_clauses` / `clause_reviews` — ✅ RESOLVED IN CODE, gap was documentation drift only
Defined and built via migration 0007 [E5] — `template_clauses`, `clause_reviews`, `draft_clause_fills`, plus `templates.template_key` and `templates.review_status`.
8.3 Sprint 3 admin features — partially requested, not confirmed built
Cross-template shared-clause detection requested in Batch 4.5 message [E13] but no build confirmation exists. Content-hash mismatch warning has no build evidence.
8.4 Template Inventory Completed — ✅ 10 of 10 Phase 1 templates live in production [E16][E20][E25]
All 10 Phase 1 templates seeded, normalized, and verified (`nda`, `service-agreement`, `consultancy`, `mou`, `employment`, `leave-licence`, `lease-deed`, `agreement-to-sell`, `joint-venture`, `software-dev`).
8.5 Technical Debt & Stabilization — ✅ ALL ISSUES RESOLVED [E21][E22][E24][E25][E26][E27]
Backend `SEC-01`, `PERF-01`, LLM Gateway intra-provider model pool failover [E24], canonical template key normalization [E25], Matter-Centric Loading Model [E26], and PROFILE-01 advocate profile isolation [E27] are fully implemented and verified.
---
9. Open Decisions
Nitesh's design involvement: 📐 confirmed zero involvement in UI decisions; his review is legal-content only.
Litigation sequencing proposal: Execute Sprint 3.5 for Litigation Pleading & Case Law Workbench following the specification in `docs/LITIGATION_ARCHITECTURE.md` [E23].
---
10. Handover Instructions
Read in this order: this tracker (§0.1 first) → source docs (§1) → `docs/LITIGATION_ARCHITECTURE.md` (§15) → the current codebase directly.
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
E20	Phase 1 Contract Template Expansion (Batches 5–7) — 5 new templates implemented and seeded into Supabase (`Leave and Licence Agreement`, `Lease Deed`, `Agreement to Sell`, `Joint Venture Agreement`, `Software Development Agreement`), bringing total template inventory to 10 of 10 Phase 1 target templates. Extracted `api/scripts/template_seed_utils.py` shared pipeline. Verified 23/23 backend pytest cases passed cleanly.	Pasted 3 Aug 2026
E21	Phase A P0 Backend Stabilization Release — Implemented `SEC-01` (XML-style prompt boundary isolation `<user_instruction>` / `<user_amendment>` across all LLM entry points) and `PERF-01` (LibreOffice PDF conversion 15s subprocess timeout cap with `PdfConversionTimeout` and HTTP 504 error response). Added 3 unit tests. Verified 165/165 backend pytest tests passed cleanly.	Pasted 3 Aug 2026
E22	Phase 1 Frontend P0 Stabilization Release — Implemented `MOB-01` (Mobile AI Assistant floating trigger button & slide-over sheet), `UX-01` (Template category filter checkboxes with real filtering, combined search, and structured empty state), and `UX-02` (Lex Scripta structured error recovery cards with actionable retry buttons). Verified `npm run lint` (0 errors) and `npm run build` (13/13 static routes).	Pasted 3 Aug 2026
E23	Sprint 3.5 Litigation Architecture Specification — Authored `docs/LITIGATION_ARCHITECTURE.md` comprehensive architecture document covering 15 structural domains, database additions, RAG pipeline, Indian Kanoon API integration, security model, and component reuse analysis.	Pasted 3 Aug 2026
E24	LLM Gateway Intra-Provider Model Pool Failover Release — Refactored `api/app/services/llm_gateway.py` to support intra-provider model pools with pinned versions across Gemini (4 models), Groq (5 models), SambaNova (1 model), and Cerebras (3 models). Removed unused `rate_limited` attribute. Added 4 unit tests. Verified 169/169 backend pytest tests passed cleanly.	Pasted 3 Aug 2026
E25	Canonical Template Key Normalization Release — Standardized all 10 contract templates to kebab-case template keys (`service-agreement`). Created migration `0009_normalize_template_keys.sql`, updated Supabase database, seed script, JSON schema, and frontend category filter logic (`web/src/app/contracts/page.tsx`). Added 2 backend regression tests. All 10/10 templates render cleanly on Contracts Workspace grid.	Pasted 3 Aug 2026
E26	Matter-Centric Loading Model Release — Added `template_id` column to `matters` table (`0010_add_template_id_to_matters.sql`), updated `MatterCreate`/`MatterOut` schemas, standardized `get_template()` for UUID & slug lookup, and updated all frontend navigation links (`/contracts/{matterId}`). Added regression tests. 173/173 backend pytest tests and 13/13 frontend static pages passed.	Pasted 3 Aug 2026
E27	PROFILE-01 Advocate Profile Isolation Release — Removed all hardcoded advocate demo values (`Adv. Nitesh Sharma`, `D/1042/2018`, etc.), implemented server-first loading from Supabase Auth `user_metadata`, added a friendly onboarding alert banner for incomplete profiles, and updated `AuthedShell` header avatar synchronization. Added regression tests. 174/174 backend pytest tests and 13/13 frontend static pages passed.	Pasted 3 Aug 2026
---
Document version: v11 — 3 August 2026
Owner: Keshav
Change from v10: updated §2, §4, §5, §6, §7, §8, §11 to record completion of PROFILE-01 Advocate Profile Isolation release and Evidence Log item E27.
