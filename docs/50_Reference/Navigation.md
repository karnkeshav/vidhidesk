> **Title:** Navigation
> **Version:** 1.0
> **Status:** Stub — source documents referenced elsewhere do not exist in this repository (see gap below)
> **Owner:** Keshav
> **Audience:** Engineers, designers
> **Last Updated:** 6 August 2026
> **Canonical Reference:** No — see gap
> **Supersedes:** N/A
> **Related Documents:** [`UI_UX_Guidelines.md`](UI_UX_Guidelines.md)

---

# Navigation

## Gap — referenced source documents do not exist

`30_Implementation/Build_Tracker.md` §1 cites two source documents by name and date: `Stitch_Mockup_Plan.md` ("screen-by-screen mockup list, sprint/session breakdown, priority order") and `Navigation_and_Functional_Spec.md` ("navigation map, link matrix, functional/validation spec per screen"), both dated 3 August 2026. Neither file exists anywhere in this repository.

Per the Build Tracker's own evidence-tagging methodology (§0.1): *"There is no live repository access. Anything built in a Claude Code session since the last paste is invisible here and must not be assumed."* This strongly suggests both documents existed only as content pasted into a chat session and were never committed as files.

This is a genuine documentation gap, not something this refactor can resolve by reconstructing the content — doing so would mean inventing a navigation map and functional spec from inference rather than extracting an approved one, which this refactor's own instructions rule out. The actual navigation structure that shipped is described in [`UI_UX_Guidelines.md`](UI_UX_Guidelines.md) ("Layout skeleton" section: global header, left navigation panel, module tiles) and is directly observable in `web/src/components/authed-shell.tsx`. If a full navigation map and functional spec are wanted, they should be authored fresh against the current live routes, not reconstructed from a citation to a missing file.
