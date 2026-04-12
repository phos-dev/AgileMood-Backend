# Docker + PostgreSQL + Seed Setup — Design Spec

**Date:** 2026-04-11
**Status:** Approved

---

## Context

AgileMood Backend has no containerized dev environment. Developers run the app locally against SQLite, which diverges from the PostgreSQL target in production. This spec adds a Docker Compose setup so any developer can `docker-compose up` and get a fully initialized PostgreSQL database with realistic dev seed data — no manual setup required.

---

## Approach: Entrypoint Script

Single entrypoint shell script handles the full startup sequence: wait for Postgres (via compose healthcheck), run Alembic migrations, run idempotent seed, then start uvicorn.

---

## Files

### New files

| File | Purpose |
|------|---------|
| `Dockerfile` | Python 3.12-slim image for the FastAPI app |
| `docker-compose.yml` | Defines `db` (postgres:16) and `app` services |
| `entrypoint.sh` | Startup sequence: migrate → seed → uvicorn |
| `scripts/seed.py` | Idempotent dev data seed script |
| `.env.example` | Documents all required environment variables |

### Existing files touched

| File | Change |
|------|--------|
| `migrations/versions/000_initial_schema.py` | New: initial Alembic migration for base tables (currently created via `create_all()`) |
| `alembic.ini` | Verify `sqlalchemy.url` reads from env (already handled in `migrations/env.py`) |

---

## docker-compose.yml

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: agilemood
      POSTGRES_PASSWORD: agilemood
      POSTGRES_DB: agilemood
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agilemood"]
      interval: 5s
      timeout: 5s
      retries: 10

  app:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://agilemood:agilemood@db:5432/agilemood
      SECRET_KEY: dev-secret-key-change-in-prod
    ports:
      - "8000:8000"
    entrypoint: ["./entrypoint.sh"]

volumes:
  postgres_data:
```

---

## Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## entrypoint.sh

```bash
#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Seeding database..."
python scripts/seed.py

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Notes:
- `set -e` — exits on any failure; container restarts let compose retry
- `exec` — replaces shell process so uvicorn receives signals correctly
- Postgres readiness is guaranteed by `depends_on: service_healthy` before this runs

---

## Initial Alembic Migration (000_initial_schema.py)

Current state: base tables are created via `metadata.create_all()` in `app/main.py`. Alembic only has one migration (`001_add_slack_webhook_url_to_team.py`), which assumes tables already exist.

Fix: add `migrations/versions/000_initial_schema.py` that creates all base tables (`user`, `team`, `user_teams`, `emotion`, `emotion_record`, `feedback`). The `001_` migration's `down_revision` is updated to point to `000_`.

The `create_all()` call in `main.py` remains — it's a no-op when tables exist and harmless for SQLite local dev.

---

## Seed Data (scripts/seed.py)

**Idempotency:** checks `SELECT COUNT(*) FROM "user"` — exits early if > 0.

**Uses SQLAlchemy session** directly (imports `SessionLocal` from `app/databases/postgres_database.py`).

**Passwords:** hashed with `passlib` (same as app) — all dev accounts use password `password123`.

### Data created

**Users (5)**

| Email | Role | Name |
|-------|------|------|
| manager@agilemood.dev | manager | Alex Manager |
| alice@agilemood.dev | member | Alice Dev |
| bob@agilemood.dev | member | Bob Dev |
| carol@agilemood.dev | member | Carol Dev |
| dave@agilemood.dev | member | Dave Dev |

**Teams (3)**

| Name | Manager | Members |
|------|---------|---------|
| Backend Team | Alex | Alice, Bob |
| Frontend Team | Alex | Carol, Dave |
| Platform Team | Alex | Alice, Carol |

**Emotion Records (30+)**

- Spread over last 30 days (datetime.utcnow() - timedelta(days=N))
- Mix of anonymous (user_id=None) and named records
- Emotion scores 1–5 across all defined emotions in the `emotion` table
- ~10 records per team

**Feedback (5+)**

- Linked to teams
- Mix of positive and constructive text
- Spread across last 30 days

---

## .env.example

```env
DATABASE_URL=postgresql://agilemood:agilemood@db:5432/agilemood
SECRET_KEY=your-secret-key-here
```

---

## Verification

```bash
# Start everything
docker-compose up --build

# Check app is running
curl http://localhost:8000/health

# Check seed data via login
curl -X POST http://localhost:8000/token \
  -d "username=manager@agilemood.dev&password=password123"

# Inspect DB directly
docker-compose exec db psql -U agilemood -c "SELECT COUNT(*) FROM \"user\";"

# Run existing test suite (mocked, no DB needed)
pytest tests/ -v
```

Alembic migration check:
```bash
docker-compose exec app alembic current
# Should show: 001_add_slack_webhook_url_to_team (head)
```
