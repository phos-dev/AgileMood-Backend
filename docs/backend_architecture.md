# Backend Architecture & APIs

> See `docs/platform_overview.md` for domain model & business rules.

## Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.115.8 |
| ORM | SQLAlchemy 2.0 |
| Validation | Pydantic 2.10.6 |
| Database | PostgreSQL (Railway, prod) / SQLite (local dev) |
| Auth | OAuth2 + JWT HS256, 4h expiry |
| Scheduler | APScheduler (AsyncIOScheduler) |
| Migrations | Alembic |
| HTTP client | httpx (async, for Slack bot API) |
| Python | 3.12 |

## Entry Point

```
app/main.py
```

Start: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

Interactive docs: `GET /docs` (Swagger), `GET /redoc`  
Health check: `GET /ping` → `{"message": "pong"}`

CORS allowed origins: `http://localhost:3000`, any `*.vercel.app`

### Auth callbacks

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/auth/teams/callback` | No | OAuth callback — saves `teams_tenant_id` to DB, redirects to frontend |
| POST | `/user/test/trigger-teams-reports` | No | Dev only — manually trigger weekly Teams report job |
| POST | `/user/test/trigger-teams-reminders` | No | Dev only — manually trigger weekly Teams reminder job |

## Auth Flow

1. Client `POST /user/login` with `username` (email) + `password` (form data)
2. Server validates credentials → returns `{ access_token, token_type: "bearer" }`
3. Token is JWT signed with `SECRET_KEY` (HS256), expires in 240 minutes
4. All protected endpoints use `Depends(get_current_active_user)` — extracts user from Bearer token
5. 401 on invalid token, 404 on disabled/missing user

Key functions in `app/routers/authentication.py`:
- `create_access_token(data: dict) → str`
- `authenticate_user(db, email, password) → UserInDB | False`
- `get_current_user(token) → UserInDB`  (dependency)
- `get_current_active_user(current_user) → UserInDB`  (checks `disabled` flag)

RBAC helpers in `app/core/auth_utils.py`:
- `ensure_is_team_manager(team, user)` → 403 if user is not the team's manager
- `ensure_is_team_member_or_manager(team, user)` → 403 if user has no relation to team

## API Endpoints

### User (`/user`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| POST | `/user/login` | No | Any | Login, returns JWT |
| POST | `/user/` | No | Any | Register new user |
| GET | `/user/logged` | Yes | Any | Current user + team_id |
| GET | `/user/{user_id}` | No | Any | Get user by ID |
| GET | `/user/?email=...` | No | Any | Get user by email |
| PUT | `/user/` | Yes | Any | Update current user |
| DELETE | `/user/{user_id}` | No | Any | Delete user |
| PUT | `/users/{user_id}/teams-user-id` | Yes | Manager | Set manual AAD Object ID for a member |
| DELETE | `/users/{user_id}/teams-user-id` | Yes | Manager | Clear manual AAD Object ID override |

### Emotions (`/emotions`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| POST | `/emotions/` | Yes | Manager | Create emotion for team |
| GET | `/emotions/` | Yes | Any | List emotions for current user's teams |
| GET | `/emotions/{emotion_id}` | Yes | Manager | Get emotion + all records (reports) |
| PUT | `/emotions/{emotion_id}` | Yes | Manager | Update emotion |
| DELETE | `/emotions/{emotion_id}` | Yes | Manager | Delete emotion |

### Emotion Records (`/emotion_record`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| POST | `/emotion_record/` | Yes | Any | Submit a record (`is_anonymous` optional) |
| GET | `/emotion_record/` | Yes | Any | All records for current user |
| GET | `/emotion_record/{emotion_name}` | Yes | Any | Records for current user by emotion name |
| GET | `/emotion_record/id/{record_id}` | Yes | Any | Single record with emotion details |

### Teams (`/teams`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| POST | `/teams/` | Yes | Manager | Create team |
| GET | `/teams/` | Yes | Manager | List manager's teams |
| GET | `/teams/{team_id}` | Yes | Member/Manager | Get team details + emotions |
| PUT | `/teams/{team_id}` | Yes | Manager | Update team |
| DELETE | `/teams/{team_id}` | Yes | Manager | Delete team |
| POST | `/teams/{team_id}?user_email=...` | Yes | Manager | Add member |
| DELETE | `/teams/{team_id}/member?user_email=...` | Yes | Manager | Remove member |
| PUT | `/teams/{team_id}/slack-bot-token` | Yes | Manager | Set Slack bot token |
| DELETE | `/teams/{team_id}/slack-bot-token` | Yes | Manager | Remove Slack bot token |
| GET | `/teams/{team_id}/emotions` | Yes | Member/Manager | List team's emotions |
| GET | `/teams/{team_id}/teams-connect` | Yes | Manager | Start Microsoft Teams OAuth consent flow |
| DELETE | `/teams/{team_id}/teams-credentials` | Yes | Manager | Disconnect Teams (removes stored tenant ID) |

### Feedback (`/feedback`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| POST | `/feedback/` | Yes | Manager | Send feedback on an emotion record |
| GET | `/feedback/` | Yes | Any | Get feedbacks received by current user |
| GET | `/feedback/emotion-record/{id}` | Yes | Owner/Manager | Feedbacks for a specific record |

### Reports (`/reports`) — Manager only, all support `?start_date=&end_date=`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/reports/emoji-distribution/{team_id}` | Emotion frequency distribution |
| GET | `/reports/average-intensity/{team_id}` | Avg intensity per emotion |
| GET | `/reports/user_emotion_analysis/{team_id}/{user_id}` | Per-user emotion breakdown |
| GET | `/reports/anonymous_records_emotion_analysis/{team_id}` | Anonymous submissions analysis |

## Database Schemas

All ORM models in `app/schemas/`. Pydantic models (request/response) in `app/models/`.

### User (`app/schemas/user_schema.py`)
```
id          int PK
name        str
email       str UNIQUE
disabled    bool default=False
hashed_password  str
role        str  ("manager" | "employee")
avatar      str | None
```

### Team (`app/schemas/team_schema.py`)
```
id                  int PK
name                str
manager_id          int FK→user.id
created_at          datetime
slack_bot_token     str | None
```
Junction: `user_teams(user_id FK→user.id, team_id FK→team.id)`

### Emotion (`app/schemas/emotion_record_schema.py`)
```
id          int PK
name        str
emoji       str | None
color       str | None
team_id     int FK→team.id CASCADE
is_negative bool
```

### EmotionRecord (`app/schemas/emotion_record_schema.py`)
```
id           int PK
user_id      int | None  FK→user.id  (null when anonymous)
emotion_id   int FK→emotion.id
intensity    int  (1–5)
notes        str | None
is_anonymous bool default=False
created_at   datetime
```

### Feedback (`app/schemas/feedback_schema.py`)
```
id                  int PK
message             str
emotion_record_id   int FK→emotion_record.id
manager_id          int FK→user.id
is_anonymous        bool default=False
created_at          datetime
```

## Slack Integration

Files: `app/services/slack_service.py`, `app/services/report_scheduler.py`

- Scheduler starts at app startup (lifespan) via `create_scheduler()` → `AsyncIOScheduler`
- Two jobs: weekly report (Mon 09:00 UTC, job ID `"weekly_slack_report"`) and weekly reminder (Fri 16:00 UTC, job ID `"weekly_slack_reminder"`)
- `send_weekly_reports()` iterates teams with `slack_bot_token`, resolves manager Slack ID, fetches 7-day reports, builds Block Kit blocks, DMs manager
- `send_weekly_reminders()` DMs each team member a check-in reminder; notifies manager of unreachable members
- `send_dm(token, slack_user_id, blocks) → bool` — async, never raises, returns False on failure
- Block Kit message contains: period, alert level, emotion distribution, avg intensity, anonymous summary
- Privacy: no per-user data in any Slack message

## Microsoft Teams Integration

Files: `app/services/teams_service.py`, `app/services/report_scheduler.py`

- Two scheduler jobs run alongside the Slack jobs: weekly report (Mon 09:00 UTC, job ID `"weekly_teams_report"`) and weekly reminder (Fri 16:00 UTC, job ID `"weekly_teams_reminder"`)
- Teams without a `teams_tenant_id` are silently skipped each run
- `send_dm(bot_token, tenant_id, teams_user_id, card) → bool` — async, never raises, returns False on any failure
- DM delivery skips `POST /v3/conversations` (causes pairwise ID errors); instead installs the bot via Graph API and posts directly to the personal chat ID
- Adaptive Card content mirrors Slack Block Kit messages: alert level, emotion distribution, avg intensity, anonymous summary — no per-user data
- `resolve_teams_user(tenant_id, user) → str | None` — tries Graph API email lookup, falls back to `user.teams_user_id` manual override, returns None if unresolvable

### DB additions (Teams)

```
Team.teams_tenant_id     str | None   — AAD tenant ID stored after admin consent
User.teams_user_id       str | None   — manual AAD Object ID override
```

See `docs/teams-integration.md` for full Azure setup and common error reference.

## Constants Reference (`app/utils/constants.py`)

```python
SECRET_KEY = "..."       # JWT signing key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 240

class Role:
    MANAGER = "manager"
    EMPLOYEE = "employee"

class Errors:   # HTTPException instances — raise directly
    INACTIVE_USER, EMAIL_ALREADY_EXISTS, INVALID_PARAMS
    NO_PERMISSION, INCORRECT_CREDENTIALS, CREDENTIALS_EXCEPTION, NOT_FOUND

class Messages:  # dict responses
    USER_DELETE, EMOTION_DELETE, MEMBER_ADDED_TO_TEAM
    MEMBER_REMOVED_FROM_TEAM, FEEDBACK_SENT
```
