# Design: Slack Integration Documentation

**Date:** 2026-04-12  
**Author:** Pedro  
**Status:** Approved

---

## Problem

AgileMood has a fully working Slack integration (Incoming Webhooks, weekly scheduled reports), but no standalone documentation exists. The only references are brief mentions in `docs/platform_overview.md` (lines 58–67) and `docs/backend_architecture.md` (lines 171–180, 94–95). Two distinct audiences need guidance and cannot find it in one place.

---

## Audiences

| Audience | Goal |
|----------|------|
| **Team Manager** (non-technical) | Connect their team's Slack channel to AgileMood |
| **Developer / Self-hoster** | Understand the architecture and deploy/maintain the integration |

---

## Decisions

| Question | Decision | Reason |
|----------|----------|--------|
| Bot or webhook? | Incoming Webhook only | Current impl uses webhooks; no bot token needed |
| One doc or two? | Single file, two sections | Easier to link, one place to maintain |
| Scope | Current implementation only | No promises about future features |
| Location | `docs/slack-integration.md` | Alongside existing docs |
| Format | GitHub-flavored markdown | Docs live in GitHub repo |
| Global Slack config? | None needed | Per-team webhook URL in DB; no `.env` entries |
| Multi-workspace? | Supported by design | Each team stores its own URL |

---

## Document Structure

### Section 1: Team Manager Guide

- How It Works (Incoming Webhooks, no bot, per-team URL)
- Prerequisites (Manager role)
- Step 1: Create Incoming Webhook in Slack (8 steps via api.slack.com/apps)
- Step 2: Register webhook in AgileMood (`PUT /teams/{id}/slack-webhook`)
- What Happens Next (Monday 09:00 UTC, report contents, privacy guarantee)
- Remove Webhook (`DELETE /teams/{id}/slack-webhook`)
- FAQ (bot needed? multi-workspace? no-data behavior?)

### Section 2: Developer / Self-Hosting Guide

- Architecture Overview (per-team DB field, no global config)
- Relevant Files (5 files with descriptions)
- Scheduler Details (APScheduler, CronTrigger, misfire grace time, lifespan)
- Report Flow (6-step pipeline)
- Error Handling (per-team isolation, `send_slack_report` return value)
- Running Tests (`pytest tests/slack_tests.py`, 23 tests)

---

## Source of Truth (verified against codebase)

- API endpoints: `app/routers/team_router.py` lines 149–189
- Scheduler config: `app/services/report_scheduler.py`
- Block Kit builders: `app/services/slack_service.py`
- DB field: `app/schemas/team_schema.py` (`slack_webhook_url`, nullable String)
- Tests: `tests/slack_tests.py` (23 tests)
