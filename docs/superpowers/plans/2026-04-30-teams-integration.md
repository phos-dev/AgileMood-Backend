# Teams Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Microsoft Teams integration delivering weekly mood reports (Mon 09:00 UTC) and check-in reminders (Fri 16:00 UTC) via proactive Bot Framework DMs — matching the existing Slack integration exactly.

**Architecture:** SaaS model. Pedro registers one multi-tenant Azure App. Managers connect their org via OAuth admin consent flow — no credentials to copy. `tenant_id` stored per team. `TEAMS_APP_ID` / `TEAMS_APP_SECRET` come from env vars. Graph API resolves users by email → AAD Object ID. Bot Framework Connector REST API sends Adaptive Card DMs. Token caching per job invocation. Jitter + 429 backoff on reminders.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, httpx (async), APScheduler, pytest, pytest-asyncio, unittest.mock

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/schemas/team_schema.py` | MODIFY | Add `teams_tenant_id` column |
| `app/schemas/user_schema.py` | MODIFY | Add `teams_user_id` |
| `app/models/team_model.py` | MODIFY | Add `teams_tenant_id` to `TeamData` |
| `app/models/user_model.py` | MODIFY | Add `teams_user_id` to `UserInDB` and `UserInTeam` |
| `app/crud/team_crud.py` | MODIFY | Add `update_teams_tenant_id` |
| `app/crud/user_crud.py` | MODIFY | Add `update_teams_user_id` |
| `app/services/teams_service.py` | CREATE | Token helpers, user resolution, send_dm, card builders |
| `app/services/report_scheduler.py` | MODIFY | Add 2 Teams jobs to `create_scheduler` |
| `app/routers/team_router.py` | MODIFY | Add connect, callback, disconnect endpoints |
| `app/routers/user_router.py` | MODIFY | Add teams-user-id CRUD + 2 test triggers |
| `migrations/versions/004_add_teams_tenant_id_to_team.py` | CREATE | Add `teams_tenant_id` column to team table |
| `migrations/versions/005_add_teams_user_id_to_users.py` | CREATE | Add `teams_user_id` column to user table |
| `teams-app-manifest.json` | CREATE | Multi-tenant Azure Bot registration manifest |
| `docs/teams-integration.md` | CREATE | Manager guide (pt-BR) + dev reference (English) |
| `tests/teams_tests.py` | CREATE | ~50 tests mirroring slack_tests.py |

---

## Task 1: DB Schema + Migrations

**Files:**
- Modify: `app/schemas/team_schema.py`
- Modify: `app/schemas/user_schema.py`
- Create: `migrations/versions/004_add_teams_tenant_id_to_team.py`
- Create: `migrations/versions/005_add_teams_user_id_to_users.py`

- [ ] **Step 1: Add columns to schemas**

In `app/schemas/team_schema.py`, add after `slack_bot_token`:
```python
teams_tenant_id = Column(String, nullable=True)
```

In `app/schemas/user_schema.py`, add after `slack_user_id`:
```python
teams_user_id = Column(String, nullable=True)
```

- [ ] **Step 2: Create migration 004**

Create `migrations/versions/004_add_teams_tenant_id_to_team.py` — mirror structure of `003_add_slack_user_id_to_users.py`. Add nullable `teams_tenant_id` String column to `team` table.

- [ ] **Step 3: Create migration 005**

Create `migrations/versions/005_add_teams_user_id_to_users.py`. Add nullable `teams_user_id` String column to `user` table.

- [ ] **Step 4: Commit**
```bash
git add app/schemas/ migrations/
git commit -m "feat: add teams_tenant_id and teams_user_id DB columns"
```

---

## Task 2: Pydantic Models

**Files:**
- Modify: `app/models/team_model.py`
- Modify: `app/models/user_model.py`

- [ ] **Step 1: Update TeamData**

Add to `TeamData`:
```python
teams_tenant_id: Optional[str] = None
```

- [ ] **Step 2: Update user models**

Add to `UserInDB` and `UserInTeam`:
```python
teams_user_id: Optional[str] = None
```

- [ ] **Step 3: Commit**
```bash
git add app/models/
git commit -m "feat: add teams fields to Pydantic models"
```

---

## Task 3: CRUD

**Files:**
- Modify: `app/crud/team_crud.py`
- Modify: `app/crud/user_crud.py`

- [ ] **Step 1: Add update_teams_tenant_id**

In `app/crud/team_crud.py`, add (mirrors `update_slack_bot_token`):
```python
def update_teams_tenant_id(db: Session, team_id: int, tenant_id: str | None) -> Team | None:
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        return None
    team.teams_tenant_id = tenant_id
    db.commit()
    db.refresh(team)
    return team
```

- [ ] **Step 2: Add update_teams_user_id**

In `app/crud/user_crud.py`, add (mirrors `update_slack_user_id`):
```python
def update_teams_user_id(db: Session, user_id: int, teams_user_id: str | None) -> User | None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.teams_user_id = teams_user_id
    db.commit()
    db.refresh(user)
    return user
```

- [ ] **Step 3: Commit**
```bash
git add app/crud/
git commit -m "feat: add Teams CRUD helpers"
```

---

## Task 4: Teams Service

**Files:**
- Create: `app/services/teams_service.py`

Mirror structure of `app/services/slack_service.py`.

- [ ] **Step 1: Write the failing tests first (TDD)**

Create `tests/teams_tests.py` with test stubs for:
- `test_classify_alert_*` (4 tests)
- `test_build_*_card` (8 tests — structure, pt-BR content, privacy footer)
- `test_get_graph_token_success`, `test_get_graph_token_failure`
- `test_get_bot_token_success`, `test_get_bot_token_failure`
- `test_resolve_teams_user_email`, `test_resolve_teams_user_fallback`, `test_resolve_teams_user_unresolvable`, `test_resolve_teams_user_graph_error`
- `test_send_dm_success`, `test_send_dm_api_error`, `test_send_dm_timeout`, `test_send_dm_network_error`

- [ ] **Step 2: Implement teams_service.py**

```python
import os
import logging
import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE          = "https://graph.microsoft.com/v1.0"
GRAPH_TOKEN_URL         = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
BOT_FRAMEWORK_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
BOT_FRAMEWORK_BASE      = "https://smba.trafficmanager.net/apis"
REQUEST_TIMEOUT         = 10
```

**`get_graph_token(tenant_id)`** — POST client_credentials to Graph token URL using `TEAMS_APP_ID` + `TEAMS_APP_SECRET` env vars. Returns access token string. Raises on failure.

**`get_bot_token()`** — POST client_credentials to Bot Framework token URL using same env vars. Returns access token string. Raises on failure.

**`resolve_teams_user(tenant_id, user)`** — Graph token → GET `/v1.0/users/{user.email}` → return `id`. On failure fall back to `user.teams_user_id`. Neither → return None.

**`send_dm(bot_token, tenant_id, teams_user_id, card)`** — POST `/v3/conversations`, then POST `/v3/conversations/{id}/activities`. Returns True/False.

**Card builders** — 4 functions returning Adaptive Card dicts. Portuguese text. Privacy footer in all report cards.

**`_classify_alert(ratio)`** — `critical`/`warning`/`note`/`ok` thresholds identical to Slack.

- [ ] **Step 3: Run tests — all should pass**
```bash
pytest tests/teams_tests.py -k "service" -v
```

- [ ] **Step 4: Commit**
```bash
git add app/services/teams_service.py tests/teams_tests.py
git commit -m "feat: add Teams service with token helpers, user resolution, DM sending, card builders"
```

---

## Task 5: API Endpoints

**Files:**
- Modify: `app/routers/team_router.py`
- Modify: `app/routers/user_router.py`

- [ ] **Step 1: Add Teams endpoints to team_router.py**

```python
import os
from fastapi.responses import RedirectResponse

@router.get("/{team_id}/teams-connect")
async def teams_connect(team_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    ensure_is_team_manager(current_user, team_id, db)
    app_id = os.environ["TEAMS_APP_ID"]
    redirect_uri = os.environ["TEAMS_REDIRECT_URI"]
    consent_url = (
        f"https://login.microsoftonline.com/common/adminconsent"
        f"?client_id={app_id}"
        f"&redirect_uri={redirect_uri}"
        f"&state={team_id}"
    )
    return RedirectResponse(consent_url)


@router.get("/teams-callback")   # mounted on app router, not team router
async def teams_callback(tenant: str, state: str, db=Depends(get_db)):
    team_id = int(state)
    team_crud.update_teams_tenant_id(db, team_id, tenant)
    frontend_url = os.environ.get("FRONTEND_URL", "/")
    return RedirectResponse(f"{frontend_url}?teams_connected=true")


@router.delete("/{team_id}/teams-credentials")
async def teams_disconnect(team_id: int, current_user=Depends(get_current_user), db=Depends(get_db)):
    ensure_is_team_manager(current_user, team_id, db)
    team_crud.update_teams_tenant_id(db, team_id, None)
    return {"detail": "Teams disconnected"}
```

Note: `/auth/teams/callback` should be a top-level route (not under `/teams`), registered in `main.py` or a separate `auth_router.py`.

- [ ] **Step 2: Add Teams user ID endpoints + test triggers to user_router.py**

Mirror existing Slack user ID endpoints. Add:
- `PUT /user/{user_id}/teams-user-id`
- `DELETE /user/{user_id}/teams-user-id`
- `POST /user/test/trigger-teams-reports`
- `POST /user/test/trigger-teams-reminders`

- [ ] **Step 3: Write endpoint tests**

Add to `tests/teams_tests.py`:
- `test_teams_connect_redirects_to_microsoft`
- `test_teams_connect_manager_only`
- `test_teams_callback_stores_tenant_id`
- `test_teams_disconnect_clears_tenant_id`
- `test_teams_user_id_put_manager_only`
- `test_teams_user_id_delete`
- `test_trigger_reports_dev_endpoint`
- `test_trigger_reminders_dev_endpoint`

- [ ] **Step 4: Run endpoint tests**
```bash
pytest tests/teams_tests.py -k "endpoint or connect or callback or disconnect" -v
```

- [ ] **Step 5: Commit**
```bash
git add app/routers/
git commit -m "feat: add Teams connect/callback/disconnect endpoints and user ID overrides"
```

---

## Task 6: Scheduler Jobs

**Files:**
- Modify: `app/services/report_scheduler.py`

- [ ] **Step 1: Write failing scheduler tests**

Add to `tests/teams_tests.py`:
- `test_scheduler_skips_team_without_tenant_id`
- `test_scheduler_sends_weekly_report`
- `test_scheduler_sends_no_data_card`
- `test_scheduler_sends_reminders`
- `test_scheduler_notifies_manager_of_unreachable`
- `test_scheduler_isolates_per_team_errors`

- [ ] **Step 2: Implement scheduler jobs**

Add to `report_scheduler.py`:

```python
async def send_weekly_teams_reports():
    # For each team with teams_tenant_id:
    #   get_graph_token(tenant_id)
    #   resolve_teams_user → manager AAD ID
    #   fetch 7-day report from reports_crud
    #   build_weekly_report_card or build_no_data_card
    #   get_bot_token()
    #   send_dm()
    # Per-team try/except

async def send_weekly_teams_reminders():
    # For each team with teams_tenant_id:
    #   get_bot_token() once per team
    #   build_reminder_card()
    #   For each member: resolve_teams_user → send_dm + jitter sleep
    #   Collect unreachable → notify manager
    # Per-team try/except
```

Register in `create_scheduler()`:
```python
scheduler.add_job(send_weekly_teams_reports, CronTrigger(day_of_week="mon", hour=9, timezone=pytz.UTC), id="weekly_teams_report", misfire_grace_time=3600)
scheduler.add_job(send_weekly_teams_reminders, CronTrigger(day_of_week="fri", hour=16, timezone=pytz.UTC), id="weekly_teams_reminder", misfire_grace_time=3600)
```

- [ ] **Step 3: Run scheduler tests**
```bash
pytest tests/teams_tests.py -k "scheduler" -v
```

- [ ] **Step 4: Commit**
```bash
git add app/services/report_scheduler.py
git commit -m "feat: add Teams weekly report and reminder scheduler jobs"
```

---

## Task 7: Integration Tests

**Files:**
- Modify: `tests/teams_tests.py`

- [ ] **Step 1: Write end-to-end integration tests**

Add 4 integration tests with full mocked external APIs (Graph API, Bot Framework):
- Full report flow (manager connect → scheduler fires → DM sent)
- Full reminder flow
- Unreachable member flow
- No-data report flow

- [ ] **Step 2: Run all tests**
```bash
pytest tests/teams_tests.py -v
```

- [ ] **Step 3: Commit**
```bash
git add tests/teams_tests.py
git commit -m "test: add Teams integration tests"
```

---

## Task 8: Supporting Files

**Files:**
- Create: `teams-app-manifest.json`
- Create: `docs/teams-integration.md`

- [ ] **Step 1: Create teams-app-manifest.json**

Multi-tenant manifest with:
- `"signInAudience": "AzureADMultipleOrgs"`
- `User.Read.All` Application permission
- Bot Framework channel

- [ ] **Step 2: Create docs/teams-integration.md**

Structure:
- **Guia do Usuário (pt-BR):** "Conectar com Teams" button, consent flow, optional user ID override
- **Developer Reference (English):** Azure one-time setup steps (Pedro), env vars, running tests, card builder extension guide

- [ ] **Step 3: Commit**
```bash
git add teams-app-manifest.json docs/teams-integration.md
git commit -m "docs: add Teams app manifest and integration guide"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run full test suite**
```bash
pytest tests/ -v
```

- [ ] **Step 2: Run linter**

See `docs/code_conventions.md` for linting commands.

- [ ] **Step 3: Manual smoke test**
1. Set env vars (`TEAMS_APP_ID`, `TEAMS_APP_SECRET`, `TEAMS_REDIRECT_URI`)
2. `GET /teams/{id}/teams-connect` → confirm redirect to `login.microsoftonline.com/common/adminconsent`
3. Complete consent flow → confirm `teams_tenant_id` stored in DB
4. `POST /user/test/trigger-teams-reports` → check logs for DM attempt
5. `POST /user/test/trigger-teams-reminders` → check logs for DM attempt

- [ ] **Step 4: Final commit + PR**
```bash
git add .
git commit -m "chore: Teams integration complete"
gh pr create --title "feat: add Microsoft Teams integration"
```

---

## Environment Variables Summary

| Variable | Where set | Description |
|----------|-----------|-------------|
| `TEAMS_APP_ID` | Server env | Azure App (client) ID — set by Pedro once |
| `TEAMS_APP_SECRET` | Server env | Azure App client secret — set by Pedro once |
| `TEAMS_REDIRECT_URI` | Server env | e.g. `https://your-domain/auth/teams/callback` |
| `FRONTEND_URL` | Server env | Frontend base URL for post-consent redirect |
