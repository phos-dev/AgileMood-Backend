# Slack Integration

AgileMood sends weekly mood reports to Slack using **Incoming Webhooks** — no bot installation or OAuth approval required. Each team configures its own webhook URL, so teams on different Slack workspaces work independently.

---

## Team Manager Guide

### How It Works

- AgileMood posts a report to your chosen Slack channel every **Monday at 09:00 UTC**
- Reports include: alert level, emotion distribution, average intensity, and an anonymous summary
- No per-user data is ever included — reports contain team-level aggregates only
- Each team has its own webhook URL; different teams can point to different Slack workspaces

### Prerequisites

- You must have the **Manager** role for the team in AgileMood

### Step 1: Create an Incoming Webhook in Slack

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Give it a name (e.g., `AgileMood`) and select your Slack workspace → **Create App**
4. In the left sidebar, click **Incoming Webhooks**
5. Toggle **Activate Incoming Webhooks** to **On**
6. Click **Add New Webhook to Workspace**
7. Select the channel where reports should be posted → **Allow**
8. Copy the **Webhook URL** (starts with `https://hooks.slack.com/services/...`)

### Step 2: Register the Webhook in AgileMood

Send a `PUT` request as a team manager:

```
PUT /teams/{team_id}/slack-webhook
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "slack_webhook_url": "https://hooks.slack.com/services/..."
}
```

AgileMood will begin sending reports to that channel on the next scheduled run.

### Remove the Webhook

To stop receiving reports, send a `DELETE` request:

```
DELETE /teams/{team_id}/slack-webhook
Authorization: Bearer <your_token>
```

### FAQ

**Do I need to install a Slack bot?**  
No. Incoming Webhooks post to a channel without any bot installation or permissions approval flow.

**Can different teams use different Slack workspaces?**  
Yes. Each team stores its own webhook URL. There is no shared Slack configuration — each team is independent.

**What if my team has no mood data for the week?**  
AgileMood sends a "no data recorded" message rather than skipping the report entirely.

**Can I trigger a report manually?**  
Not currently. Reports are sent automatically each Monday at 09:00 UTC.

---

## Developer / Self-Hosting Guide

### Architecture Overview

- Each team has a `slack_webhook_url` column in the database (nullable `String`)
- No global Slack configuration; no Slack-related entries in `.env`
- The scheduler runs inside the FastAPI process — no separate worker needed
- Teams without a webhook URL are silently skipped each week

### Relevant Files

| File | Purpose |
|------|---------|
| `app/services/slack_service.py` | Block Kit message builders, async HTTP sender (`send_slack_report`) |
| `app/services/report_scheduler.py` | APScheduler job definition and team iteration logic |
| `app/routers/team_router.py` | `PUT`/`DELETE` webhook endpoints (manager-only, lines 149–189) |
| `app/crud/team_crud.py` | `update_slack_webhook()` and `get_all_teams()` |
| `migrations/versions/001_add_slack_webhook_url_to_team.py` | DB migration adding the `slack_webhook_url` column |

### Scheduler Details

- **Library:** APScheduler (`AsyncIOScheduler`)
- **Trigger:** every Monday at 09:00 UTC  
  `CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="UTC")`
- **Job ID:** `"weekly_slack_report"`
- **Misfire grace time:** 3600 seconds — if the app was down at trigger time, the job fires within 1 hour of coming back up
- **Lifecycle:** started and stopped in `app/main.py` via the FastAPI `lifespan` context manager

### Report Flow

1. `send_weekly_reports()` opens a DB session and fetches all teams
2. Teams with no `slack_webhook_url` are skipped
3. For each team, fetches 7-day reports: emoji distribution, average intensity, anonymous emotion analysis
4. If no data exists for the period, builds a fallback message via `build_no_data_blocks()`
5. Otherwise builds the full report via `build_weekly_report_blocks()`
6. POSTs to the webhook URL via `httpx` (async); logs the result; never raises

### Error Handling

- A failure for one team (network error, bad webhook URL, etc.) is caught and logged — it does not stop processing of other teams
- `send_slack_report(url, blocks)` returns `True` on success, `False` on any error

### Running the Tests

```bash
pytest tests/slack_tests.py
```

25 tests covering: webhook CRUD API, alert level classification, Block Kit message structure, HTTP failure scenarios (timeout, network error, non-200 response), and scheduler behavior (skip teams without webhooks, error isolation between teams).
