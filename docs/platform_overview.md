# AgileMood — Platform Overview & Business Rules

## What Is AgileMood?

AgileMood is an open-source tool for measuring and improving **psychological safety** and **emotional awareness** in agile software development teams. It collects periodic anonymous mood feedback from team members, computes metrics (including perception dispersion), and generates dashboards to help engineering leaders make data-driven interventions.

The core insight: teams perform better when members feel safe expressing how they actually feel. Traditional retrospectives capture this inconsistently. AgileMood makes it continuous, measurable, and private by default.

## Domain Entity Model

```
User (manager | employee)
  └─ manages ──────────────► Team ──► Emotion (team-scoped)
  └─ member of (N:N) ──────► Team
                                        │
                              EmotionRecord (submitted by employee)
                                        │
                              Feedback (sent by manager on a record)
```

## Core Business Rules

### Users & Roles
- Two roles: `manager` and `employee`
- A user can be a member of multiple teams
- A user can only have one role system-wide
- Managers are not team members — they manage the team from above

### Teams
- A team has exactly one manager (`manager_id`)
- Members are employees added by the manager
- Teams are the isolation boundary: data from one team is never visible to another

### Emotions
- Emotions are **team-scoped**: each team defines its own set (name, emoji, color, `is_negative` flag)
- Only the team manager can create, edit, or delete emotions
- Employees see only the emotions belonging to their own team

### Emotion Records
- Employees submit emotion records with: `emotion_id`, `intensity` (1–5), optional `notes`, optional `is_anonymous`
- When `is_anonymous=True`: `user_id` is set to `null` in the DB — the manager cannot trace it back to an individual
- Employees can only see their own records

### Feedback
- Managers send feedback in response to a specific `EmotionRecord`
- Only the manager of the team the emotion record belongs to can send feedback
- Feedback can also be `is_anonymous` (manager identity hidden from employee)
- `manager_knows_identity` flag on response: `True` only if the original record was NOT anonymous
- Employees see their own received feedbacks only

### Reports
- All report endpoints are **manager-only**
- Reports are always **team-level aggregates** — never per-user breakdowns
- This applies especially to Slack: no individual data ever leaves the system
- Available: emoji distribution, average intensity, per-user analysis (visible to manager only in-app), anonymous records analysis
- All report endpoints support optional `start_date` / `end_date` filters (ISO date format)

### Slack Integration
- Teams can optionally set a `slack_webhook_url` (manager only, via `PUT /teams/{id}/slack-webhook`)
- Weekly reports fire automatically every **Monday at 09:00 UTC** via APScheduler
- Only teams with a webhook URL configured receive reports
- Alert thresholds based on `negative_emotion_ratio`:
  - `> 50%` → critical (🔴)
  - `> 30%` → warning (🟡)
  - `> 15%` → note (🔵)
  - `≤ 15%` → ok (🟢)
- Slack messages include only team-level aggregates; no per-user data is ever sent externally

## Tech Choices Rationale

| Choice | Why |
|--------|-----|
| **FastAPI** | Async support, automatic OpenAPI docs (`/docs`, `/redoc`) |
| **SQLAlchemy 2.0 ORM** | Flexible DB backend (PostgreSQL prod, SQLite dev) |
| **Pydantic 2** | Strong request/response validation with ORM mode |
| **Anonymous records** | Psychological safety: people report honestly when not tracked |
| **JWT (no sessions)** | Stateless auth fits REST API + frontend-agnostic |
| **APScheduler** | Embedded scheduler avoids external cron dependency |
| **Block Kit (Slack)** | Rich formatted reports without a bot token — webhooks only |

## Key File Locations

| Area | Path |
|------|------|
| App entry | `app/main.py` |
| Auth | `app/routers/authentication.py` |
| RBAC helpers | `app/core/auth_utils.py` |
| Error/message constants | `app/utils/constants.py` |
| ORM schemas | `app/schemas/` |
| Pydantic models | `app/models/` |
| Business logic | `app/crud/` |
| Slack service | `app/services/slack_service.py` |
| Scheduler | `app/services/report_scheduler.py` |
| DB migrations | `migrations/versions/` |
