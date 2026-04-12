# Design: Doc Standardization — Flat Merge into /docs/

**Date:** 2026-04-11  
**Status:** Approved  
**Audience:** AI agents (Claude)

## Problem

Documentation spread across 3 locations (`agent_docs/`, `docs/superpowers/`, root `CLAUDE.md`) with no cross-links, an outdated README, and `platform_overview.md` unreachable from CLAUDE.md. Redundant folder hierarchy created confusion about where to add new docs.

## Approach

Flat merge: move `agent_docs/*.md` → `docs/*.md`, delete `agent_docs/`, update CLAUDE.md path refs, add 3 cross-links. No content rewriting — structural changes only.

## Final Structure

```
/CLAUDE.md                              ← router (updated paths + platform_overview link)
/docs/
  backend_architecture.md              ← moved from agent_docs/
  code_conventions.md                  ← moved from agent_docs/
  frontend_state.md                    ← moved from agent_docs/
  platform_overview.md                 ← moved from agent_docs/
  running_tests.md                     ← moved from agent_docs/
  superpowers/
    specs/                             ← design docs (this file)
    plans/                             ← implementation plans
/agent_docs/                            ← deleted
```

## Progressive Disclosure Hierarchy

1. `CLAUDE.md` — entry point, routes by task type to specific doc
2. `docs/*.md` — focused technical guides, loaded on-demand per task
3. Cross-links within docs — guide agent to related doc when needed

## Cross-links Added

| File | Link added |
|------|-----------|
| `docs/backend_architecture.md` | → `docs/platform_overview.md` |
| `docs/frontend_state.md` | → `docs/backend_architecture.md` |
| `docs/code_conventions.md` | → `docs/backend_architecture.md` |
