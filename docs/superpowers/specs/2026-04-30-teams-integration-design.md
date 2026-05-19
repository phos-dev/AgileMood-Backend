# Teams Integration Design

**Date:** 2026-04-30  
**Updated:** 2026-05-03  
**Branch:** feature/add-teams-integration  
**Status:** Approved

---

## Context

AgileMood already delivers weekly mood reports (Monday 09:00 UTC) and check-in reminders (Friday 16:00 UTC) via Slack DMs. This design replicates that integration for Microsoft Teams — same UX, same scheduler cadence, same privacy model — so teams using Teams can participate without behavioral differences.

**Deployment model:** AgileMood is SaaS. Pedro registers **one** multi-tenant Azure App. Managers connect their organization via a simple OAuth admin consent flow — no Azure knowledge, no credentials to copy.

**Approach:** Microsoft admin consent OAuth → capture `tenant_id`. Microsoft Graph API for user lookup (email → AAD Object ID). Bot Framework Connector REST API for proactive DMs. AgileMood's own `TEAMS_APP_ID` / `TEAMS_APP_SECRET` env vars used for all token requests — never stored per team.

---

## Setup (Pedro does once)

1. **Azure Portal → App registrations → New registration**
   - Name: "AgileMood"
   - Supported account types: `AzureADMultipleOrgs` (multi-tenant)
   - Redirect URI: `https://your-domain/auth/teams/callback`
2. **API permissions → Add:**
   - `User.Read.All` (Microsoft Graph, Application, requires admin consent)
3. **Certificates & secrets → New client secret** → copy value
4. **Azure Bot resource → Create**
   - Use the same App ID from step 1
   - Enable Microsoft Teams channel
5. **Set env vars on backend:**
   ```
   TEAMS_APP_ID=<application client id>
   TEAMS_APP_SECRET=<client secret>
   TEAMS_REDIRECT_URI=https://your-domain/auth/teams/callback
   ```

---

## Manager flow (each customer org)

1. Go to team settings in AgileMood
2. Click **"Connect with Teams"**
3. Sign in with Microsoft admin account
4. Approve permissions ("AgileMood wants to read user profiles in your organization")
5. Redirected back — connected
6. Optionally: set manual Teams User ID overrides for members whose emails differ from AAD

Zero Azure knowledge required.

---

## Architecture

```
Manager clicks "Connect with Teams"
    ↓
GET /teams/{team_id}/teams-connect
    ↓
Backend builds admin consent URL → redirects manager to Microsoft
    ↓
https://login.microsoftonline.com/common/adminconsent
    ?client_id={TEAMS_APP_ID}
    &redirect_uri={TEAMS_REDIRECT_URI}
    &state={team_id}
    ↓
Admin approves
    ↓
GET /auth/teams/callback?tenant={tenant_id}&state={team_id}
    ↓
Backend stores tenant_id for team → redirects to frontend /?teams_connected=true
    ↓
APScheduler triggers Monday 09:00 UTC
    ↓
send_weekly_teams_reports()
    ↓
For each team with tenant_id:
    ├─ get_graph_token(tenant_id)          ← uses TEAMS_APP_ID + TEAMS_APP_SECRET
    ├─ resolve_teams_user() → AAD Object ID
    ├─ reports_crud.get_emoji_distribution_report() → report data
    ├─ build_weekly_report_card() → Adaptive Card dict
    ├─ get_bot_token()                     ← uses TEAMS_APP_ID + TEAMS_APP_SECRET
    └─ send_dm() → POST /v3/conversations → POST /v3/conversations/{id}/activities
                ↓
        Manager receives Teams DM with weekly report
```

---

## Database Changes

### Team schema (`app/schemas/team_schema.py`)
```python
teams_tenant_id = Column(String, nullable=True)
```
Single field. No credentials stored per team.

### User schema (`app/schemas/user_schema.py`)
```python
teams_user_id = Column(String, nullable=True)  # manual AAD Object ID override
```

### Migrations
- `migrations/versions/004_add_teams_tenant_id_to_team.py`
- `migrations/versions/005_add_teams_user_id_to_users.py`

---

## Pydantic Models

### `app/models/team_model.py`
`TeamData` gains `teams_tenant_id: Optional[str] = None`.  
No `TeamsCredentialsUpdate` model needed — tenant_id arrives via OAuth callback, not PUT body.

### `app/models/user_model.py`
`UserInDB` and `UserInTeam` gain `teams_user_id: Optional[str] = None`.

---

## API Endpoints

### Connect / disconnect (`app/routers/team_router.py`)
| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| GET | `/teams/{team_id}/teams-connect` | Manager only | Build admin consent URL, redirect to Microsoft |
| GET | `/auth/teams/callback` | — (Microsoft callback) | Receive `tenant` + `state`, store `teams_tenant_id`, redirect to frontend |
| DELETE | `/teams/{team_id}/teams-credentials` | Manager only | Clear `teams_tenant_id` (disconnect) |

### User ID override (`app/routers/user_router.py`)
| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| PUT | `/user/{user_id}/teams-user-id` | Manager role | Set manual AAD Object ID override |
| DELETE | `/user/{user_id}/teams-user-id` | Manager role | Clear override |
| POST | `/user/test/trigger-teams-reports` | — | Dev: fire report job immediately |
| POST | `/user/test/trigger-teams-reminders` | — | Dev: fire reminder job immediately |

RBAC: `ensure_is_team_manager` for connect/disconnect. `current_user.role != Role.MANAGER` check for user ID endpoints (mirrors Slack).

---

## Service Layer (`app/services/teams_service.py`)

### Constants
```python
GRAPH_API_BASE          = "https://graph.microsoft.com/v1.0"
GRAPH_TOKEN_URL         = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
BOT_FRAMEWORK_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
BOT_FRAMEWORK_BASE      = "https://smba.trafficmanager.net/apis"
REQUEST_TIMEOUT         = 10  # seconds
```

Note: `smba.trafficmanager.net` is the global service URL. GCC/regional tenants not supported in v1.

### Functions

**`async get_graph_token(tenant_id: str) → str`**  
POST to `GRAPH_TOKEN_URL`, grant `client_credentials`, scope `https://graph.microsoft.com/.default`.  
Uses `TEAMS_APP_ID` and `TEAMS_APP_SECRET` from env.

**`async get_bot_token() → str`**  
POST to `BOT_FRAMEWORK_TOKEN_URL`, grant `client_credentials`, scope `https://api.botframework.com/.default`.  
Uses `TEAMS_APP_ID` and `TEAMS_APP_SECRET` from env.

**Token caching:** In-memory dict keyed by scope per job invocation to prevent redundant fetches.

**`async resolve_teams_user(tenant_id, user) → str | None`**
1. `get_graph_token(tenant_id)`
2. `GET /v1.0/users/{user.email}` → extract `id` (AAD Object ID)
3. On failure → fall back to `user.teams_user_id`
4. Neither → return None, caller adds to unreachable list  
Never raises.

**`async send_dm(bot_token, tenant_id, teams_user_id, card) → bool`**
1. `POST /v3/conversations` with Teams channel data + AAD user ID → get `conversationId`
2. `POST /v3/conversations/{conversationId}/activities` with Adaptive Card attachment  
Returns True on success, False on any failure. Never raises.

**Rate limiting:** `asyncio.sleep(random.uniform(0.1, 0.5))` between per-member DMs. `send_dm` handles 429 with `Retry-After` backoff, up to 3 retries.

**Card builders (Adaptive Cards, Portuguese)**
- `build_weekly_report_card(team_name, start_date, end_date, emoji_report, intensity_report, anonymous_report) → dict`
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
`critical` >50%, `warning` >30%, `note` >15%, `ok` ≤15%.

**Error handling:** All async functions catch exceptions, log with `logger`, return None/False. Timeouts set to 10s via httpx.

---

## CRUD

### `app/crud/team_crud.py`
```python
def update_teams_tenant_id(db: Session, team_id: int, tenant_id: str | None) -> Team | None
```
Sets or clears `teams_tenant_id`. Mirrors `update_slack_bot_token`.

### `app/crud/user_crud.py`
```python
def update_teams_user_id(db: Session, user_id: int, teams_user_id: str | None) -> User | None
```
Mirrors `update_slack_user_id`.

---

## Scheduler (`app/services/report_scheduler.py`)

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

**`send_weekly_teams_reports()`:** For each team — skip if `tenant_id` missing, resolve manager AAD ID, fetch 7-day reports, build card, send DM. Per-team exception isolation.

**`send_weekly_teams_reminders()`:** For each team — skip if `tenant_id` missing, build reminder card, send to each member with jitter, collect unreachable list, notify manager if any unreachable. Per-team exception isolation.

---

## Tests (`tests/teams_tests.py`)

Mirrors `slack_tests.py` structure (~50 tests total):

| Category | Count |
|----------|-------|
| Alert classification | 4 |
| Adaptive Card builders (structure, pt-BR content, privacy footer) | 8 |
| Schema verification | 3 |
| CRUD operations (`update_teams_tenant_id`, `update_teams_user_id`) | 4 |
| Token fetching — Graph uses env vars, Bot Framework uses env vars | 4 |
| DM sending (success, API error, timeout, network error) | 4 |
| User resolution (email, fallback, unresolvable, Graph error) | 4 |
| API endpoints (connect redirect, callback stores tenant_id, disconnect, user ID CRUD) | 8 |
| Scheduler jobs (skip no-tenant, report, reminder, unreachable, error isolation, no-data) | 6 |
| Integration tests (end-to-end with mocked external APIs) | 4 |

Tools: `pytest`, `pytest-asyncio`, `unittest.mock` (`patch`, `MagicMock`, `AsyncMock`), FastAPI `TestClient`.

---

## Supporting Files

### `teams-app-manifest.json`
Multi-tenant Azure Bot registration manifest:
- `"signInAudience": "AzureADMultipleOrgs"`
- `User.Read.All` (Application permission, admin consent required)
- Bot Framework channel permissions (proactive DMs)

### `docs/teams-integration.md`

**Structure:**
- Guia do Usuário (pt-BR) — manager clicks "Connect with Teams", approves once, optionally sets manual user ID overrides
- Developer Reference (English) — architecture, Azure setup (Pedro's one-time steps), env vars, running tests, extending card builders

---

## Verification

```bash
# Unit + integration tests
pytest tests/teams_tests.py -v

# Linter (see docs/code_conventions.md)

# Manual smoke test
# 1. GET /teams/{id}/teams-connect → confirm redirect to Microsoft consent URL
# 2. Complete consent flow → confirm teams_tenant_id stored in DB
# 3. POST /user/test/trigger-teams-reports → check logs for DM attempt
# 4. POST /user/test/trigger-teams-reminders → check logs for DM attempt
```
