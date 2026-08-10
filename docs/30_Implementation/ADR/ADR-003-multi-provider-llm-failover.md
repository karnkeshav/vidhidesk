> **Title:** ADR-003 — Multi-Provider LLM Failover Strategy
> **Version:** 1.0
> **Status:** Accepted
> **Owner:** Keshav
> **Audience:** Architects, engineers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** Yes
> **Related Documents:** [`../../10_Architecture/AI_Architecture.md`](../../10_Architecture/AI_Architecture.md), [`ADR-009-freeware-zero-cost-constraint.md`](ADR-009-freeware-zero-cost-constraint.md)

---

# ADR-003: Multi-Provider LLM Failover Strategy

## Status
Accepted. Originally specified as Gemini → Groq → Ollama; revised in production to drop Ollama in favor of SambaNova and Cerebras.

## Context
The project runs entirely on free-tier infrastructure with no dedicated LLM budget, and single-user volume made free-tier rate limits an acceptable but real constraint. The original plan additionally assumed a local Ollama instance could serve as a final fallback for cost and confidentiality reasons.

## Decision
The LLM Gateway (`api/app/services/llm_gateway.py`) routes every generation request through a fixed provider order on rate-limit or error: **Gemini 2.5 Flash → Groq (Llama-3.3-70B) → SambaNova → Cerebras**. No local Ollama — the infrastructure the tool actually runs on does not support hosting a local model. Within each provider tier, an ordered pool of pinned model versions is tried before escalating to the next provider (4 Gemini models, 5 Groq, 1 SambaNova, 3 Cerebras, per Build Tracker E24), with per-model transient retry and position logging.

## Alternatives Considered
Local Ollama as the final fallback (per the original Technical Requirements Document) — dropped because the actual hosting environment (Render free tier) cannot run a local model; SambaNova and Cerebras free tiers substitute as the deeper fallback layer instead.

## Consequences
- Every prompt sent to any of the four providers must be PII-masked first (see [ADR-004](ADR-004-mandatory-pii-masking.md)) — there is no local, trusted-environment option to fall back to for sensitive matters.
- Provider outages or policy changes degrade gracefully (next provider in chain) rather than failing the request outright.
- The gateway is the single interface (`generate(prompt, task_type)`) every module calls — no module talks to a provider SDK directly.

## Source
`CLAUDE.md` Decision 3; `90_Historical/Original_Technical_Requirements.md` §3.1 (original design, including the now-dropped Ollama fallback); `30_Implementation/Build_Tracker.md` Evidence E24 ("LLM Gateway Intra-Provider Model Pool Failover").
