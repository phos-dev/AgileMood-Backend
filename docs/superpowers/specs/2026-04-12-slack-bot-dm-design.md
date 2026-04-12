# Slack Bot DM Integration — Design Spec

**Date:** 2026-04-12  
**Status:** Approved  
**Author:** Pedro

---

## Context

The original Slack integration used per-team Incoming Webhooks to send a weekly mood report to a Slack channel. This had two problems:

1. **Wrong audience:** The aggregated report (with alert levels and emotion distribution) is sensitive management data — it should reach the manager privately, not a shared channel visible to the whole team.
2. **No reminders:** There was no mechanism to prompt team members to submit their mood reports. Channel messages are easily ignored; DMs are not.

This spec replaces the webhook approach with a Slack bot using per-team bot tokens, enabling private DMs to both members (reminders) and managers (weekly reports).

---

## Goals

- Weekly mood report → DM to the team manager only (no shared channel)
- Weekly reminder → DM to each team member to submit their report
- Multi-workspace support (each team configures its own bot token)
- Graceful degradation when a member's Slack identity can't be resolved
- Maintain full anonymity: no per-user data in any Slack message

---

## Non-Goals

- OAuth callback flow per user (not needed for bot tokens)
- Frontend UI for Slack configuration (API only)
- Support for Microsoft Teams or other platforms (out of scope)

---

## Architecture

One Slack App is created per workspace using the provided `slack-app-manifest.yml`. The resulting bot token is stored per team in AgileMood, supporting multiple workspaces across teams.

```
AgileMood Scheduler
  ├── Friday 16:00 UTC — send_weekly_reminders()
  │     └── Per team with slack_bot_token:
  │           └── Per member → resolve Slack user → DM reminder
  └── Monday 09:00 UTC — send_weekly_reports()
        └── Per team with slack_bot_token:
              └── Resolve manager's Slack user → DM aggregated report
```

**Slack user resolution (for each AgileMood user):**
1. Call `users.lookupByEmail(user.email)` via Slack API
2. If not found → use `user.slack_user_id` (manual override) if set
3. If neither → add to `unreachable` list → notify manager

---

## Data Model Changes

### `Team` model
- **Remove:** `slack_webhook_url` (String, nullable)
- **Add:** `slack_bot_token` (String, nullable) — bot token for the team's Slack workspace

### `User` model
- **Add:** `slack_user_id` (String, nullable) — manual override for users whose AgileMood email differs from their Slack email

### Migrations
- `002_replace_slack_webhook_with_bot_token.py` — drops `slack_webhook_url`, adds `slack_bot_token` to `teams`
- `003_add_slack_user_id_to_users.py` — adds `slack_user_id` to `users`

---

## API Endpoints

### Remove
- `PUT /teams/{team_id}/slack-webhook`
- `DELETE /teams/{team_id}/slack-webhook`

### Add
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `PUT` | `/teams/{team_id}/slack-bot-token` | Manager | Set bot token for this team's workspace |
| `DELETE` | `/teams/{team_id}/slack-bot-token` | Manager | Remove Slack integration for this team |
| `PUT` | `/users/{user_id}/slack-user-id` | Manager | Set manual Slack user ID override |
| `DELETE` | `/users/{user_id}/slack-user-id` | Manager | Remove Slack user ID override |

---

## Scheduler Logic

### `send_weekly_reminders()` — Friday 16:00 UTC

```python
for team in teams_with_bot_token():
    unreachable = []
    for member in team.members:
        slack_id = resolve_slack_user(team.slack_bot_token, member)
        if slack_id:
            send_dm(team.slack_bot_token, slack_id, reminder_message())
        else:
            unreachable.append(member.email)
    if unreachable:
        manager_id = resolve_slack_user(team.slack_bot_token, team.manager)
        send_dm(team.slack_bot_token, manager_id, unreachable_message(unreachable))
```

**Reminder message content:**
> 👋 Olá! Lembra de registrar como você está se sentindo essa semana no AgileMood. Leva menos de 1 minuto.

Rules:
- No mention of how many others have submitted (avoids social pressure)
- No per-user data referenced
- Message is identical for all members (no personalization that could identify submission patterns)

### `send_weekly_reports()` — Monday 09:00 UTC

Same logic as current scheduler, but:
- Uses `resolve_slack_user()` to find manager's Slack ID instead of webhook URL
- Sends via `chat.postMessage(channel=manager_slack_id)` instead of webhook POST

Report content unchanged: emotion distribution, alert level, negative ratio, anonymous analysis summary, privacy footer.

---

## `resolve_slack_user(token, user)` — Helper

```python
async def resolve_slack_user(token: str, user: User) -> str | None:
    # 1. Try Slack API lookup by email
    result = await slack_api_get("users.lookupByEmail", token, email=user.email)
    if result.ok:
        return result.user.id
    # 2. Fall back to manual override
    if user.slack_user_id:
        return user.slack_user_id
    # 3. Unresolvable
    log.warning(f"Cannot resolve Slack user for {user.email}")
    return None
```

---

## Error Handling

| Error | Behavior |
|-------|----------|
| Email not found in workspace | Try `slack_user_id` override; if none, add to unreachable list |
| Token missing `users:read.email` scope | Log critical error, skip entire team |
| Token invalid / revoked | Log error for that team, continue other teams |
| Slack API rate limit | Exponential backoff, max 3 retries |
| DM send failure | Log warning, continue to next member |
| Manager unresolvable | Log error, skip report for that team |

**Unreachable notification to manager:**
```
⚠️ 2 membros não receberam lembrete via Slack DM:
• pedro@empresa.com — email não encontrado no workspace
• ana@empresa.com — nenhum Slack ID configurado

Configure manualmente via: PUT /users/{id}/slack-user-id
```

---

## Slack App Manifest

A `slack-app-manifest.yml` file at the project root enables one-click bot creation:

```yaml
display_information:
  name: AgileMood
  description: Psychological safety tracker for agile teams
oauth_config:
  scopes:
    bot:
      - chat:write
      - users:read.email
      - im:write
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
```

Manager setup steps:
1. `api.slack.com/apps` → "Create New App" → "From a manifest"
2. Paste contents of `slack-app-manifest.yml`
3. Install to workspace
4. Copy "Bot User OAuth Token" (`xoxb-...`)
5. `PUT /teams/{team_id}/slack-bot-token` with the token

---

## Files to Modify

| File | Change |
|------|--------|
| `app/models/team.py` | Remove `slack_webhook_url`, add `slack_bot_token` |
| `app/models/user.py` | Add `slack_user_id` |
| `app/crud/team_crud.py` | Update webhook CRUD → bot token CRUD |
| `app/routers/team_router.py` | Replace webhook endpoints with bot token endpoints |
| `app/routers/user_router.py` | Add `slack-user-id` endpoints |
| `app/services/slack_service.py` | Replace `send_slack_report()` with `resolve_slack_user()` + `send_dm()` |
| `app/services/report_scheduler.py` | Add `send_weekly_reminders()`, update `send_weekly_reports()` |
| `app/databases/postgres_database.py` | Reflect model changes if needed |
| `migrations/versions/` | Add migrations 002 and 003 |
| `tests/slack_tests.py` | Update existing + add new tests |

## New Files
| File | Purpose |
|------|---------|
| `slack-app-manifest.yml` | One-click Slack app creation |
| `docs/slack-integration.md` | Update manager guide + developer guide |

---

## Anonymity Guarantees (Unchanged)

- Reminder DMs contain no mood data whatsoever
- Weekly report to manager contains only team-level aggregates
- No per-user breakdown in any Slack message
- Anonymous records: aggregated separately, never traceable to individual
- `is_anonymous=True` records: `user_id` stored as null in DB

---

## Verification

1. Create test Slack workspace, install bot via `slack-app-manifest.yml`
2. `PUT /teams/{id}/slack-bot-token` with valid token
3. Trigger `send_weekly_reminders()` manually (via test endpoint or direct call)
4. Confirm DM received by team member
5. Trigger `send_weekly_reports()` manually
6. Confirm DM received by manager with aggregated data only
7. Edge case: set member email to non-existent address → confirm manager receives unreachable notification
8. Edge case: revoke bot token → confirm error logged, other teams unaffected
9. Edge case: set `slack_user_id` override → confirm DM delivered despite email mismatch

---

## Known Limitations

- One AgileMood instance = one Slack workspace per team (multi-workspace via multiple team tokens)
- No support for Slack Enterprise Grid (shared channels across orgs)
- Bot must be installed by workspace admin; regular members cannot install
