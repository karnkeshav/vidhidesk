> **Title:** ADR-004 — Mandatory PII Masking Before External LLM Calls
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../10_Architecture/AI_Architecture.md`](../../10_Architecture/AI_Architecture.md), [`../../00_Product/Product_Constitution.md`](../../00_Product/Product_Constitution.md) §9

---

# ADR-004: Mandatory PII Masking Before External LLM Calls

## Status
Accepted from project foundation; hardened in Sprint 2 (Build Tracker Evidence E12).

## Context
Because there is no local model option (see [ADR-003](ADR-003-multi-provider-llm-failover.md)), every prompt necessarily leaves the advocate's environment and goes to a third-party cloud LLM provider. Client matters routinely contain privileged, identifying information — party names, addresses, phone numbers, government ID patterns — that cannot be sent to a third party without protection.

## Decision
A PII-masking layer in the LLM gateway is mandatory, not optional. Party names, addresses, phone numbers, and Aadhaar/PAN patterns are replaced with stable placeholders (`PARTY_A`, `ADDR_1`, ...) before any external LLM call, and restored only in the response as rendered to the advocate. The masking map is stored per-matter in Postgres (`pii_masks` table) and is never sent to the LLM. A statute-abbreviation allowlist exists so legitimate legal terms are not incorrectly masked.

## Alternatives Considered
Relying on provider no-training-on-data terms alone (mentioned as a supplementary posture in `90_Historical/Original_Project_Plan_Revised.md` §7) was considered insufficient on its own — masking removes the exposure at the source rather than trusting a third party's data-handling policy as the only safeguard.

## Consequences
- Every new LLM entry point must run input through the masker before calling `llm_gateway.generate()` — this is enforced as a standing requirement, not per-endpoint discretion (see [`../../20_Engineering/API_Standards.md`](../../20_Engineering/API_Standards.md)).
- Masking must be tested against real form field values, not just hand-constructed fixtures — a Sprint 2 bug (a "Fixed Fee" string value getting masked into a `PARTY_x` placeholder, breaking an unrelated conditional) was only caught by live E2E testing, not the unit suite (see [`../../20_Engineering/Lessons_Learned.md`](../../20_Engineering/Lessons_Learned.md)).
- Masking and citation verification are named together in project conventions as the two subsystems that "must never regress" — both carry dedicated regression test suites.

## Source
`CLAUDE.md` Decision 4 (Privacy); `90_Historical/Original_Technical_Requirements.md` §5 (Confidentiality NFR); `30_Implementation/Build_Tracker.md` Evidence E12.
