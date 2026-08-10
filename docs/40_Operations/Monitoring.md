> **Title:** Monitoring
> **Version:** 1.0
> **Status:** Designed only — not confirmed built
> **Owner:** Keshav
> **Audience:** Engineers, operations
> **Last Updated:** 6 August 2026
> **Canonical Reference:** No — nothing to be canonical about yet; this records intent and the gap
> **Supersedes:** N/A
> **Related Documents:** [`../10_Architecture/Runtime_Architecture.md`](../10_Architecture/Runtime_Architecture.md), [`Deployment.md`](Deployment.md)

---

# Monitoring

## Designed intent (from the original Technical Requirements Document)

`90_Historical/Original_Technical_Requirements.md` §2 names **Sentry free tier / plain logging** as the intended monitoring approach. No subsequent document in this repository confirms this was implemented, and `30_Implementation/Build_Tracker.md` does not list monitoring/observability among its confirmed-built cross-cutting subsystems (§6).

## Gap

There is no confirmed error-tracking, uptime-monitoring, or LLM-quota-monitoring implementation as of this refactor, despite the Technical Requirements' explicit call to "log every API call with cost/quota impact" for the Indian Kanoon integration (per `CLAUDE.md`). This is a real gap, not a documentation-drift gap — it should be scoped as build work, not written into this document as if it exists.
