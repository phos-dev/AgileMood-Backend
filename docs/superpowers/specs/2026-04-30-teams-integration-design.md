# Teams Integration Design

**Date:** 2026-04-30
**Branch:** feature/add-teams-integration
**Status:** Approved

---

## Context

AgileMood already delivers weekly mood reports (Monday 09:00 UTC) and check-in reminders (Friday 16:00 UTC) via Slack DMs. This design replicates that integration for Microsoft Teams — same UX, same scheduler cadence, same privacy model — so teams using Teams can participate without behavioral differences.

**Approach:** Microsoft Graph API for user lookup + Bot Framework Connector REST API for proactive DMs. Avoids the high-privilege `Chat.ReadWrite.All` permission. Standard Microsoft pattern for bot-initiated messages.

---

## Architecture

Each AgileMood team stores its own Azure Bot credentials (app_id + app_secret + tenant_id). The bot uses those credentials to:

1. Obtain a Graph API token → look up user AAD Object IDs by email
2. Obtain a Bot Framework token → send proactive DMs via the Connector REST API

Fallback chain for user resolution mirrors Slack: email lookup → manual `teams_user_id` override → unreachable (manager notified).

---

## Database Changes

### Team schema (`app/schemas/team_schema.py`)
```python
teams_app_id     = Column(String, nullable=True)
teams_app_secret = Column(String, nullable=True)
teams_tenant_id  = Column(String, nullable=True)
```
Stored and cleared as a logical unit.

### User schema (`app/schemas/user_schema.py`)
```python
teams_user_id = Column(String, nullable=True)  # manual AAD Object ID override
```

### Migrations
- `migrations/versions/004_add_teams_credentials_to_team.py`
- `migrations/versions/005_add_teams_user_id_to_users.py`

---

## Pydantic Models

### `app/models/team_model.py`
```python
class TeamsCredentialsUpdate(BaseModel):
    teams_app_id: str
    teams_app_secret: str
    teams_tenant_id: str
```
`TeamData` gains `teams_app_id`, `teams_app_secret`, `teams_tenant_id` (all `Optional[str] = None`).

### `app/models/user_model.py`
`UserInDB` and `UserInTeam` gain `teams_user_id: Optional[str] = None`.

---

## API Endpoints

### Team credentials (`app/routers/team_router.py`)
| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| PUT | `/teams/{team_id}/teams-credentials` | Manager only | Store app_id + app_secret + tenant_id |
| DELETE | `/teams/{team_id}/teams-credentials` | Manager only | Clear all 3 fields |

### User ID override (`app/routers/user_router.py`)
| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| PUT | `/user/{user_id}/teams-user-id` | Manager role | Set manual AAD Object ID override |
| DELETE | `/user/{user_id}/teams-user-id` | Manager role | Clear override |
| POST | `/user/test/trigger-teams-reports` | — | Dev: fire report job immediately |
| POST | `/user/test/trigger-teams-reminders` | — | Dev: fire reminder job immediately |

RBAC: `ensure_is_team_manager` for team credentials; `current_user.role != Role.MANAGER` check for user ID endpoints (mirrors Slack).

---

## Service Layer (`app/services/teams_service.py`)

### Constants
```python
GRAPH_API_BASE           = "https://graph.microsoft.com/v1.0"
GRAPH_TOKEN_URL          = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
BOT_FRAMEWORK_TOKEN_URL  = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
BOT_FRAMEWORK_BASE       = "https://smba.trafficmanager.net/apis"
REQUEST_TIMEOUT          = 10  # seconds
```

### Functions

**`async get_graph_token(tenant_id, app_id, app_secret) → str`**
POST to `GRAPH_TOKEN_URL`, grant `client_credentials`, scope `https://graph.microsoft.com/.default`. Returns access token string.

**`async get_bot_token(app_id, app_secret) → str`**
POST to `BOT_FRAMEWORK_TOKEN_URL`, grant `client_credentials`, scope `https://api.botframework.com/.default`.

**`async resolve_teams_user(credentials, user) → str | None`**
1. Fetch Graph token
2. `GET /v1.0/users/{user.email}` → extract `id` (AAD Object ID)
3. On failure → fall back to `user.teams_user_id`
4. Neither → return None, caller adds to unreachable list
Never raises.

**`async send_dm(bot_token, tenant_id, teams_user_id, card) → bool`**
1. `POST /v3/conversations` with Teams channel data + AAD user ID → get `conversationId`
2. `POST /v3/conversations/{conversationId}/activities` with Adaptive Card attachment
Returns True on success, False on any failure. Never raises.

**Card builders (Adaptive Cards, Portuguese)**
- `build_weekly_report_card(team_name, start_date, end_date, emoji_report, intensity_report, anonymous_report) → dict`
  - Header: team name + period
  - Alert level: 🔴 crítico >50%, 🟡 aviso >30%, 🔵 nota >15%, 🟢 ok ≤15%
  - Emotion frequency distribution (top 10)
  - Negative emotion ratio (%)
  - Average intensity per emotion
  - Anonymous records summary
  - Privacy footer: "Este relatório não contém dados individuais. Todas as estatísticas são agregados do time."
- `build_no_data_card(team_name, start_date, end_date) → dict`
- `build_reminder_card() → dict`
- `build_unreachable_notification_card(unreachable_emails: list[str]) → dict`

**`_classify_alert(ratio: float) → str`**
Identical to Slack: `critical` >50%, `warning` >30%, `note` >15%, `ok` ≤15%.

**Error handling:** All async functions catch exceptions, log with `logger`, return None/False. Timeouts set to 10s via httpx.

---

## CRUD

### `app/crud/team_crud.py`
```python
def update_teams_credentials(
    db: Session,
    team_id: int,
    app_id: str | None,
    app_secret: str | None,
    tenant_id: str | None,
) -> Team | None
```
Sets or clears all 3 fields atomically. Mirrors `update_slack_bot_token`.

### `app/crud/user_crud.py`
```python
def update_teams_user_id(db: Session, user_id: int, teams_user_id: str | None) -> User | None
```
Mirrors `update_slack_user_id`.

---

## Scheduler (`app/services/report_scheduler.py`)

Two new async jobs registered in `create_scheduler()`:

```python
# Monday 09:00 UTC — weekly report to manager
scheduler.add_job(
    send_weekly_teams_reports,
    CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=pytz.UTC),
    id="weekly_teams_report",
    misfire_grace_time=3600,
)

# Friday 16:00 UTC — reminder to all members
scheduler.add_job(
    send_weekly_teams_reminders,
    CronTrigger(day_of_week="fri", hour=16, minute=0, timezone=pytz.UTC),
    id="weekly_teams_reminder",
    misfire_grace_time=3600,
)
```

**`send_weekly_teams_reports()`:** For each team — skip if credentials missing, resolve manager AAD ID, fetch 7-day reports from `reports_crud`, build card, send DM. Per-team exception isolation.

**`send_weekly_teams_reminders()`:** For each team — skip if credentials missing, build reminder card, send to each member, collect unreachable list, notify manager if any unreachable. Per-team exception isolation.

---

## Tests (`tests/teams_tests.py`)

Mirrors `slack_tests.py` structure (~50 tests total):

| Category | Count |
|----------|-------|
| Alert classification | 4 |
| Adaptive Card builders (structure, pt-BR content, privacy footer) | 8 |
| Schema verification | 3 |
| CRUD operations | 4 |
| Token fetching (Graph + Bot Framework) | 4 |
| DM sending (success, API error, timeout, network error) | 4 |
| User resolution (email, fallback, unresolvable, Graph error) | 4 |
| API endpoints (manager sets/removes, employee blocked, user ID CRUD) | 8 |
| Scheduler jobs (skip no-creds, report, reminder, unreachable, error isolation, no-data) | 6 |
| Integration tests (end-to-end with mocked external APIs) | 4 |

Tools: `pytest`, `pytest-asyncio`, `unittest.mock` (`patch`, `MagicMock`, `AsyncMock`), FastAPI `TestClient`.

---

## Supporting Files

### `teams-app-manifest.json`
Azure Bot registration manifest for one-click setup. Required permissions:
- `User.ReadBasic.All` (Graph — email lookup)
- Bot Framework channel permissions (proactive DMs)

### `docs/teams-integration.md`

**Structure:**
- Guia do Usuário (pt-BR) — setup steps for managers, how to register an Azure Bot, where to find app_id/app_secret/tenant_id, how to set manual user ID overrides
- Developer Reference (English) — architecture, auth flows, environment setup, running tests, extending card builders

---

## Message Flow

```
Manager configures Teams credentials
    ↓
PUT /teams/{id}/teams-credentials (app_id, app_secret, tenant_id)
    ↓
team_crud.update_teams_credentials() → stored in DB
    ↓
APScheduler triggers Monday 09:00 UTC
    ↓
send_weekly_teams_reports()
    ↓
For each team with credentials:
    ├─ get_graph_token(tenant_id, app_id, app_secret)
    ├─ resolve_teams_user() → GET /v1.0/users/{email} → AAD Object ID
    ├─ reports_crud.get_emoji_distribution_report() → report data
    ├─ build_weekly_report_card() → Adaptive Card dict
    ├─ get_bot_token(app_id, app_secret)
    └─ send_dm() → POST /v3/conversations → POST /v3/conversations/{id}/activities
                ↓
        Manager receives Teams DM with weekly report
```

---

## Verification

```bash
# Unit + integration tests
pytest tests/teams_tests.py -v

# Linter (see docs/code_conventions.md)

# Manual smoke test
# 1. PUT /teams/{id}/teams-credentials with real or mocked credentials
# 2. POST /user/test/trigger-teams-reports → check logs for DM attempt
# 3. POST /user/test/trigger-teams-reminders → check logs for DM attempt
```
