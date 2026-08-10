> **Title:** UI/UX Guidelines
> **Version:** 1.0
> **Status:** Active — Canonical for design
> **Owner:** Keshav
> **Audience:** Designers, frontend engineers, future AI agents touching UI
> **Last Updated:** 3 August 2026
> **Canonical Reference:** Yes, for visual/design-system decisions
> **Supersedes:** N/A
> **Related Documents:** [`50_Reference/Stitch_Guidelines.md`](Stitch_Guidelines.md), [`00_Product/Product_Constitution.md`](../00_Product/Product_Constitution.md) (§7 UX Principles)

---

VidhiDesk — UI/UX Design Notes
A working document capturing the design conversation for VidhiDesk. This is intended as the reference Claude Code and any future designer should read before touching visual work. Update as decisions land.
---
Who this is for
The primary user is Nitesh — a senior practising Indian advocate. Not a Gen Z user of consumer apps. Not a legal-tech power user. A professional whose day is split between chambers, court appearances, and client meetings.
His current AI tool references are Claude and ChatGPT. He uses them for daily work. This matters because he already appreciates the visual language of considered AI interfaces: clean, restrained, content-first, no unnecessary decoration. The design bar isn't "look like Bloomberg Law" — it's "feel as calm and considered as Claude, but for a lawyer."
He is not comparing this tool to legal SaaS. He is comparing it to how AI tools feel to work in. That reframes the entire design brief.
---
Design values
Three principles that apply to every screen:
Quiet authority. The tool looks like it was built by people who understand law, not people who understand engagement metrics. No enthusiasm. No exclamation marks. No motivational messaging.
Precision. Every element earns its place. Nothing decorative. Nothing "designed to look nice." If it doesn't serve the work, it isn't there.
Discretion. This is a tool for client-privileged work. It shouldn't feel exuberant. A senior advocate handles life-changing decisions for clients — the tool that helps him do that should feel proportionate.
---
Explicit "do not do" list
Common patterns that would break the design frame:
Colorful, gradient-heavy dashboards
Motivational stats or gamification ("You've drafted 47 documents this month!")
Stock photography of lawyers, courtrooms, gavels
Cartoon or friendly icons with rounded corners and "smiley-face" vibes
Emojis anywhere
Chattiness in copy ("Let's get started!" "You've got this!")
Announcements, news banners, blog links, testimonials
Onboarding tutorials that persist past the first week
Notification bells (this isn't Twitter)
Verified-badge flourishes, shield-with-checkmark iconography
Animation for anything other than functional state changes (save spinner, page transition)
Vibrant anything
---
Color palette
Six colors, used with discipline, consistent from login screen through every subsequent page.
Role	Color	Hex	Rationale
Primary background	Warm ivory / bone white	`#FBF9F5`	Law-book paper feel. Restful for long reading. Not harsh `#FFFFFF`.
Primary text	Warm charcoal	`#1A1A1A`	Softer than pure black. Print-quality.
Primary accent	Deep navy	`#1E2A4A`	Legal reference books, professional badges, formal stationery. Restrained but authoritative.
Critical action / error	Muted burgundy / oxblood	`#7A2A2A`	Delete, error states, warnings. Never used for anything else.
Success / verified	Muted forest green	`#3D5A3D`	Reviewed clauses, verified citations. Used sparingly.
Secondary text / borders	Neutral warm gray	Text `#6B6B6B`, borders `#E5E3DE`	Dividers, secondary labels, muted UI chrome.
No gradients. No shadows beyond very soft ones (`0 2px 8px rgba(0,0,0,0.04)`). No hover effects that dramatically change color — subtle darkening only.
---
Typography
Two typefaces, no more.
Long-form legal content (clauses, drafts, statute quotes): IBM Plex Serif.
Renders beautifully on screen and in printed .docx
Book-like feel appropriate for legal reading
Free from Google Fonts
UI text (buttons, navigation, form labels, headings, dashboards): IBM Plex Sans.
Native pairing with Plex Serif
Free, open-source, professional
Inter as fallback if Plex Sans is unavailable
Sizing (conservative — advocates read a lot; their eyes matter):
Body: 15-16px
UI labels: 14px
H1 / page titles: 24px
H2 / section titles: 20px
Line height: 1.6-1.7 for long-form text; 1.4 for UI
---
Iconography
Do use:
Scales of Justice — used once, at the top of the app, as a subtle mark alongside the wordmark. Not repeated on every page.
Small monoline icons for status and navigation: document icon for drafts, checkmark for reviewed, gavel for litigation, house for RERA, briefcase for consulting.
Consistent visual language: 1.5px stroke, single color (neutral gray or navy), simple line style throughout.
Reference for style: Financial Times app icons, Wall Street Journal app icons, Notion's icon set. Considered, monoline, purposeful.
Do not use:
Colorful or multi-color icons
Filled icons that look childish
Any icon that says "we're trying to be legaltech" (shields with checkmarks, "verified" flourishes)
---
Layout skeleton (applies to every page)
Global header (thin, always present, ~56px tall)
Left: Small Scales of Justice mark + "VidhiDesk" wordmark. Never changes.
Center (or slightly right): Primary module navigation — Contracts | Litigation | RERA | Consulting. Current module underlined subtly with the navy accent.
Right: User's name or initials avatar with dropdown menu (Settings, Sign Out).
Nothing else in the header. No search bar (search lives inside modules that need it). No notification bell. No help icon (put help in the user dropdown).
Global footer (minimal, always present)
A single muted-text line at the bottom of every page:
> VidhiDesk · AI-generated drafts for advocate review. Not legal advice.
Small links to Privacy and Support if desired. This is the permanent disclaimer surface — Nitesh sees it every screen. Legal safety by design.
Left navigation panel (persistent on desktop, drawer on mobile)
Four modules listed vertically with their icons
Under each module: the user's most recent 3-5 matters, clickable
Below that: a "New matter" button — always accessible
Center content
Varies by page. This is where the work happens. Never cluttered.
Right panel (optional, contextual)
Only appears when there's genuinely useful sidebar content: state-law notes on the intake form, retrieval results for a Litigation query, etc.
Empty by default.
---
Specific screens — design intent
Login screen
The first impression every day. Restraint here sets the tone for the whole product.
Elements, in order, center-aligned:
Scales of Justice mark
"VidhiDesk" wordmark (letter V styled with a subtle serif — a small nod to legal tradition)
Tagline: "For the practising advocate."
Email field
Password field
Sign In button (deep navy)
Nothing else. No "Try VidhiDesk free!" banner. No feature list. No testimonials. No blog links. No "By signing in you agree to..." fine print (put that elsewhere).
Dashboard (post-login home)
Three horizontal bands:
Top band — quick status. Single line in the page header: "Good morning, Nitesh. 3 drafts pending your review. 2 matters last touched more than a week ago. Nothing due today."
This gives him the "what am I walking into" answer at a glance.
Middle band — four modules. Restrained cards. Each card contains:
Module name (Contracts / Litigation / RERA / Consulting)
One-line description ("Draft, amend, and review contracts across 10 templates")
Count of his own work in that module ("14 matters, 3 pending review")
"Continue where you left off" mini-list: last 2-3 matters in that module, shown as one line each, clickable
This lets him jump straight back to work without navigating.
Bottom band — recent activity. A chronological feed:
> *You created 'NDA — Acme deal' 2 days ago.*
> *You reviewed 4 clauses in Service Agreement template on Tuesday.*
> *Draft v2 generated on Ramesh consulting matter — yesterday.*
Boring in the best way. Purposeful. Reassures a senior lawyer that the tool remembers everything he's done.
Matter creation — flip the flow
Current pattern (to be removed): Modal asks for Title before he sees anything.
New pattern:
He clicks a module or a specific template directly (no upfront modal).
He starts the intake form.
As he fills in party names, the matter title auto-generates in the header:
Initially: "NDA — [being drafted]"
After party names: "NDA — Ramesh Kumar / Acme (03 Aug)"
He can click the title at any time to rename.
When he submits, the matter is saved with the inferred title.
Zero mandatory upfront ceremony. Just work.
Intake form (Service Agreement is the hardest — ~20 fields)
Design principle: schema-declared field groups rendered as collapsible sections. Only one section expanded at a time. Never a 20-field scroll marathon.
Groups for Service Agreement (illustrative):
Parties (Party A, Party B details)
Scope of Work (purpose, deliverables list)
Commercials (fee structure, payment terms)
Service Levels (SLA conditionals)
Legal (IP ownership, term, termination, arbitration, governing law)
State-selector on the right side, driving a state-law-notes panel that updates as the state changes.
Draft view
After generation:
Title in the header (matter name)
Two primary buttons: Download .docx (primary, navy) and Download .pdf (secondary, outlined). PDF button shows "Generating PDF…" and disables during generation.
Draft rendered in a proper formatted layout — not a monospace code block. IBM Plex Serif, generous line height, paragraph spacing that mirrors legal document conventions.
"Amend this draft" chat pane below the preview, with a clear input field. Placeholder examples: "reduce lock-in to 12 months," "change arbitration seat to Delhi."
Version history sidebar: v1, v2, v3, ... — clickable to view older versions.
Clause review screen (`/admin/templates/nda` etc.)
This is where Nitesh spends the most time when doing his real review work. Deserves the most care.
Design principles:
Clause text rendered like a printed page, not a code editor. IBM Plex Serif. Generous margins.
Progress indicator without a garish progress bar. Small text: "5 of 12 reviewed."
Ordered clause list on the left with subtle status indicators (unreviewed / kept / redrafted / deleted).
Center panel shows the selected clause's current text with three actions:
Keep (one click, no confirmation)
Redraft (opens inline editor with the current text, plus a required note field)
Delete (requires a reason, confirmation dialog)
Compare source vs current — if he's redrafted, a small "compare with original" toggle shows the diff cleanly.
"Keep all boilerplate" button at the top (already built).
Margin space for personal notes — a discreet notes field per clause that's private to the reviewer.
Print/export review notes option — if he wants to think about clauses offline.
On mobile, the clause review is rethought entirely (see mobile section below).
---
Mobile design
Nitesh will use his phone. Indian advocates read case files in taxis, review drafts between court appearances, take client calls and pull up matters mid-conversation. Mobile is not an afterthought.
Core mobile principles:
Same six colors. Same typography. Don't design a "mobile theme" separately.
Bottom navigation on mobile. Four icons at the bottom for the four modules. Thumb-reachable. This matches Notion, ChatGPT, Claude patterns on mobile.
Left drawer for matters list. Slides in from left; taps outside close it.
Intake forms use collapsible groups aggressively. Only current group expanded. Others collapsed with a summary line ("Parties — Party A: Ramesh Kumar, Party B: Acme").
Drafts render as proper formatted text on mobile. Serif, generous line-height. Not a monospace block that requires horizontal scroll.
Clause review screen rethought:
Full-screen clause view
Bottom bar: prev / current-position / next arrows
Top-right icon opens a slide-up drawer showing the full clause index for jumping around
Actions (Keep / Redraft / Delete) as a bottom sheet
---
Small "advocate touches" — warmth without childishness
Details a senior advocate will notice and appreciate:
Scales of Justice logo rendered as a considered monoline mark. Not clip-art.
Wordmark — "VidhiDesk" with a subtle serif on the V, nod to legal tradition.
Occasional Latin phrases where they fit naturally, as tooltips or context labels:
"Ex nunc — take effect immediately" on `effective_date` field hover
"In personam" on the party-details section
Never forced, never overdone
Indian legal date format: "3 August 2026" — never "08/03/2026" or "Aug 3, 2026." The Indian bar uses "3 August 2026." Small detail, large signal.
State names in full in formal contexts ("Uttar Pradesh," not "UP"). "UP" acceptable only in dense tables where space is constrained.
These are not decorative flourishes. They are competence signals — the kind of details only someone who understands the profession would think to include.
---
Copy tone
Every piece of UI text should reflect the design values.
Use:
"Draft" (not "let's create")
"Matter" (not "project" or "case file")
"Client" (not "customer" or "user")
"Brief" (not "quick guide")
"Review" (not "check")
"Sign in" (not "log in" — sign in is more formal)
Formal but not cold. Third person or neutral phrasing where possible.
Avoid:
First-name-basis chattiness
"Let's" anything
"You've got this!" style empty states
Exclamation marks
Contractions in formal copy (spell out "do not" instead of "don't" for legal-adjacent messaging)
---
Consistency requirements
The single most important discipline: the visual language must be identical across every screen.
Same six colors, in the same roles, on every screen
Same header and footer on every screen (unless a screen deliberately hides them for full-focus work)
Same typography scale
Same button styles (primary navy, secondary outlined, destructive burgundy)
Same form field styles
Same icon set
Same spacing scale (4px, 8px, 16px, 24px, 32px, 48px — no arbitrary values)
Nitesh should never wonder "where am I?" A senior lawyer doesn't want to relearn navigation between modules. The visual continuity is what makes the tool feel like a single considered product, not a collection of pages.
---
Design implementation approach — decision framework
There are three viable ambition levels:
Option 1 — Tastefully professional. ~2-3 Claude Code sessions.
Change colors, typography, spacing, icons. Make it responsive. Rely on Claude Code's aesthetic judgment plus this document.
Option 2 — Systematic design pass. ~1 week Claude Code + designer input.
Comprehensive rethink. Expensive; risks overreach.
Option 3 — Design-led, Stitch-mediated pass. 4-5 sessions across 2-3 weeks.
Use Google Stitch (free) to generate mockups first, get Nitesh's reaction on the mockups, then Claude Code implements against approved visual targets. Best balance of quality, cost, and confidence.
Currently favored: Option 3.
If pursuing Option 3, the six priority mockups to generate in Stitch
Login screen
Dashboard (desktop)
Dashboard (mobile)
Contracts template picker (`/contracts`)
Intake form for Service Agreement (~20 fields)
Clause review admin screen
Stitch prompt template
For each screen, use a base prompt like:
> *"[Screen name] for VidhiDesk, an AI legal drafting tool for senior Indian advocates. Design values: quiet authority, professional restraint, considered typography. Color palette: warm ivory background (#FBF9F5), warm charcoal text (#1A1A1A), deep navy primary accent (#1E2A4A), muted burgundy for critical actions (#7A2A2A), muted forest green for verified states (#3D5A3D), neutral warm gray for secondary (#6B6B6B, #E5E3DE). Typography: IBM Plex Serif for long-form legal content, IBM Plex Sans for UI. Layout: generous whitespace, no gradients, no decorative animation, minimal use of iconography (small monoline icons only). Reference: feels like Claude's calmness meets a barrister's chambers. Explicitly not: cheerful, colorful, gamified, or startup-flavored."*
Then add screen-specific details per mockup.
---
Open decisions
Things worth deciding before design implementation starts:
Ambition level (Option 1 vs 2 vs 3) — see above. Currently leaning Option 3.
Phasing — do design pass now (before Sprint 2 templates 6-10) or after (Sprint 3)?
Leaning: do design pass now. Nitesh is already using the tool on scaffolding UI; better first impression matters more than more templates on scaffolding.
Nitesh's involvement — is he responsive enough to give mockup feedback within a few days? If not, Option 3 stalls and we fall back to Option 1.
Deployment cadence — one big design PR that Nitesh sees over a weekend, or incremental changes rolled out screen by screen?
---
Reference points to study
Rather than prescribing specific competitor products, these are the aesthetic references worth internalizing:
For restraint and content-first design:
Claude (Anthropic)
Notion workspace look
Financial Times digital
Apple's iBooks
For professional gravity:
Bloomberg Terminal (icon language, information density)
Wall Street Journal app
LexisNexis Advance (functional gravitas, if not aesthetic pinnacle)
What NOT to reference:
Most Indian legaltech (colorful tiles, gradients, gamification)
Silicon Valley consumer SaaS (too colorful, too chatty)
BigLaw US firm websites (too corporate, too formal-cold)
---
Summary in one paragraph
VidhiDesk should feel like walking into a quiet, well-lit chambers with law books on the shelves and a Waterman pen on the desk. The tool serves the work; the work is what the user sees. Colors are ivory and navy, typography is IBM Plex Serif and Sans, iconography is monoline and restrained. Every screen looks like it belongs in the same product. Mobile and desktop are variants of one design language, not two designs. Small legal-professional touches — scales of justice mark, Indian date convention, occasional Latin — signal competence. Nothing is decorative. Everything is considered.
---
Document version: v1 — 3 August 2026
Owner: Keshav
Reviewed by: pending — should be reviewed with Nitesh before implementation begins
