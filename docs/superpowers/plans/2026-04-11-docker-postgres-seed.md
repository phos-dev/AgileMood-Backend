# Docker + PostgreSQL + Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `docker-compose up --build` workflow that spins up PostgreSQL, runs Alembic migrations, seeds dev data, and starts the FastAPI app — zero manual setup.

**Architecture:** A single `entrypoint.sh` handles the startup sequence (migrate → seed → uvicorn). Postgres readiness is handled by a compose healthcheck so the app never starts before the DB is ready. The seed script is idempotent (skips if users exist).

**Tech Stack:** Docker Compose v2, Python 3.12-slim, PostgreSQL 16, Alembic 1.14, SQLAlchemy 2.0, hashlib (sha256 — app's own password hashing), pytest

---

## File Map

| Status | File | Responsibility |
|--------|------|---------------|
| Modify | `migrations/env.py` | Read `DATABASE_URL` from env so `alembic upgrade head` works in Docker |
| Create | `migrations/versions/000_initial_schema.py` | Alembic migration creating all base tables |
| Modify | `migrations/versions/001_add_slack_webhook_url_to_team.py` | Update `down_revision` to `'000'` |
| Create | `.env.example` | Documents required env vars |
| Create | `Dockerfile` | Python 3.12-slim app image |
| Create | `docker-compose.yml` | `db` + `app` services with healthcheck |
| Create | `entrypoint.sh` | migrate → seed → uvicorn |
| Create | `scripts/__init__.py` | Makes scripts a package (empty) |
| Create | `scripts/seed.py` | Idempotent dev data seed |
| Create | `tests/test_seed.py` | Unit tests for seed idempotency and data correctness |

---

## Task 1: Fix Alembic env.py to read DATABASE_URL from environment

**Files:**
- Modify: `migrations/env.py`

The current `migrations/env.py` reads `sqlalchemy.url` from `alembic.ini` (value: `driver://user:pass@localhost/dbname`). In Docker, `DATABASE_URL` is set as an env var. Without this fix, `alembic upgrade head` will fail with a connection error.

- [ ] **Step 1: Open `migrations/env.py` and add DATABASE_URL override**

Replace the block after `config = context.config` with:

```python
from logging.config import fileConfig
import os

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

config = context.config

# Override sqlalchemy.url with DATABASE_URL env var if set
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from app.databases.postgres_database import Base
import app.schemas.team_schema  # noqa: F401
import app.schemas.user_schema  # noqa: F401
import app.schemas.emotion_record_schema  # noqa: F401
import app.schemas.feedback_schema  # noqa: F401
target_metadata = Base.metadata
```

Keep the rest of the file (`run_migrations_offline`, `run_migrations_online`, bottom two lines) unchanged.

- [ ] **Step 2: Verify Alembic can read the env var locally**

```bash
DATABASE_URL=sqlite:///./test_check.db alembic current
```

Expected: outputs `(no current revision)` or current head — no connection error. Then:

```bash
rm -f test_check.db
```

- [ ] **Step 3: Commit**

```bash
git add migrations/env.py
git commit -m "fix: read DATABASE_URL env var in alembic migrations"
```

---

## Task 2: Create initial Alembic migration (base schema)

**Files:**
- Create: `migrations/versions/000_initial_schema.py`

The current `001_` migration (`add_column slack_webhook_url`) has `down_revision = None`, meaning it thinks it's the root migration. But it calls `op.add_column('team', ...)` — that requires the `team` table to already exist. Adding `000_initial_schema.py` as the true root creates all base tables.

- [ ] **Step 1: Write the failing test to confirm migration chain order**

Create `tests/test_migrations.py`:

```python
"""Verify Alembic migration chain is intact."""
import subprocess
import sys


def test_migration_chain_has_initial_schema():
    """000_initial_schema must exist as a .py file in migrations/versions."""
    import os
    versions_dir = "migrations/versions"
    files = os.listdir(versions_dir)
    has_000 = any(f.startswith("000_") for f in files)
    assert has_000, "Missing 000_initial_schema migration"


def test_001_has_correct_down_revision():
    """001 migration must point to 000 as its parent."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migration_001",
        "migrations/versions/001_add_slack_webhook_url_to_team.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.down_revision == "000", (
        f"Expected down_revision='000', got {mod.down_revision!r}"
    )
```

- [ ] **Step 2: Run to confirm it fails**

```bash
pytest tests/test_migrations.py -v
```

Expected: FAIL — `Missing 000_initial_schema migration` and `Expected down_revision='000'`

- [ ] **Step 3: Create `migrations/versions/000_initial_schema.py`**

```python
"""initial schema

Revision ID: 000
Revises:
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa

revision = '000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('disabled', sa.Boolean(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('avatar', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_id'), 'user', ['id'], unique=False)
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=True)

    op.create_table(
        'team',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('manager_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['manager_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_team_id'), 'team', ['id'], unique=False)

    op.create_table(
        'user_teams',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'team_id'),
    )

    op.create_table(
        'emotion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('emoji', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('is_negative', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_emotion_id'), 'emotion', ['id'], unique=False)

    op.create_table(
        'emotion_record',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('emotion_id', sa.Integer(), nullable=False),
        sa.Column('intensity', sa.Integer(), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['emotion_id'], ['emotion.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_emotion_record_id'), 'emotion_record', ['id'], unique=False)

    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message', sa.String(), nullable=False),
        sa.Column('emotion_record_id', sa.Integer(), nullable=False),
        sa.Column('manager_id', sa.Integer(), nullable=False),
        sa.Column('is_anonymous', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['emotion_record_id'], ['emotion_record.id'], ),
        sa.ForeignKeyConstraint(['manager_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feedback_id'), 'feedback', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('feedback')
    op.drop_table('emotion_record')
    op.drop_table('emotion')
    op.drop_table('user_teams')
    op.drop_table('team')
    op.drop_table('user')
```

- [ ] **Step 4: Update `001_add_slack_webhook_url_to_team.py` — set `down_revision = '000'`**

Change line 12 from:
```python
down_revision = None
```
to:
```python
down_revision = '000'
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_migrations.py -v
```

Expected: PASS (both tests green)

- [ ] **Step 6: Smoke-test migration chain with SQLite**

```bash
DATABASE_URL=sqlite:///./test_migrate.db alembic upgrade head
DATABASE_URL=sqlite:///./test_migrate.db alembic current
rm -f test_migrate.db
```

Expected: `alembic current` prints `001 (head)`

- [ ] **Step 7: Commit**

```bash
git add migrations/versions/000_initial_schema.py \
        migrations/versions/001_add_slack_webhook_url_to_team.py \
        tests/test_migrations.py
git commit -m "feat: add initial schema alembic migration and fix 001 down_revision"
```

---

## Task 3: Create seed script with tests

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/seed.py`
- Create: `tests/test_seed.py`

Password hashing uses `hashlib.sha256` — the same function the app uses in `app/crud/user_crud.py:get_password_hash`.

- [ ] **Step 1: Write failing tests first**

Create `tests/test_seed.py`:

```python
"""Tests for the dev seed script."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.databases.postgres_database import Base


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def test_seed_creates_expected_users(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "user"')).scalar()
    assert result == 5


def test_seed_creates_expected_teams(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "team"')).scalar()
    assert result == 3


def test_seed_creates_emotion_records(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "emotion_record"')).scalar()
    assert result >= 30


def test_seed_creates_feedback(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "feedback"')).scalar()
    assert result >= 5


def test_seed_is_idempotent(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)
    run_seed(db_session)  # second call must be a no-op

    result = db_session.execute(text('SELECT COUNT(*) FROM "user"')).scalar()
    assert result == 5  # still 5, not 10


def test_manager_role_is_correct(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(
        text('SELECT role FROM "user" WHERE email = :email'),
        {"email": "manager@agilemood.dev"}
    ).scalar()
    assert result == "manager"


def test_member_role_is_correct(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(
        text('SELECT role FROM "user" WHERE email = :email'),
        {"email": "alice@agilemood.dev"}
    ).scalar()
    assert result == "employee"


def test_password_is_hashed(db_session):
    from scripts.seed import run_seed
    from hashlib import sha256
    run_seed(db_session)

    result = db_session.execute(
        text('SELECT hashed_password FROM "user" WHERE email = :email'),
        {"email": "manager@agilemood.dev"}
    ).scalar()
    expected = sha256("password123".encode("utf-8")).hexdigest()
    assert result == expected
```

- [ ] **Step 2: Run to confirm all fail**

```bash
pytest tests/test_seed.py -v
```

Expected: all FAIL with `ImportError: cannot import name 'run_seed' from 'scripts.seed'`

- [ ] **Step 3: Create `scripts/__init__.py`** (empty file)

```bash
touch scripts/__init__.py
```

- [ ] **Step 4: Create `scripts/seed.py`**

```python
"""Idempotent dev seed script for AgileMood.

Run via: python scripts/seed.py
Or automatically via entrypoint.sh on docker-compose up.
"""
from hashlib import sha256
import datetime

from sqlalchemy.orm import Session

from app.databases.postgres_database import SessionLocal
from app.schemas.user_schema import User
from app.schemas.team_schema import Team
from app.schemas.emotion_record_schema import Emotion, EmotionRecord
from app.schemas.feedback_schema import Feedback


def _hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


def run_seed(session: Session) -> None:
    """Insert dev seed data. No-op if users already exist."""
    if session.query(User).count() > 0:
        print("Seed skipped: data already exists.")
        return

    # --- Users ---
    manager = User(
        name="Alex Manager",
        email="manager@agilemood.dev",
        role="manager",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    alice = User(
        name="Alice Dev",
        email="alice@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    bob = User(
        name="Bob Dev",
        email="bob@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    carol = User(
        name="Carol Dev",
        email="carol@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    dave = User(
        name="Dave Dev",
        email="dave@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    session.add_all([manager, alice, bob, carol, dave])
    session.flush()  # get IDs before using in FKs

    # --- Teams ---
    backend_team = Team(
        name="Backend Team",
        manager_id=manager.id,
        members=[alice, bob],
    )
    frontend_team = Team(
        name="Frontend Team",
        manager_id=manager.id,
        members=[carol, dave],
    )
    platform_team = Team(
        name="Platform Team",
        manager_id=manager.id,
        members=[alice, carol],
    )
    session.add_all([backend_team, frontend_team, platform_team])
    session.flush()

    # --- Emotions (per team) ---
    def _make_emotions(team: Team):
        return [
            Emotion(name="Happy", emoji="😊", color="#FFD700", team_id=team.id, is_negative=False),
            Emotion(name="Anxious", emoji="😰", color="#FF6347", team_id=team.id, is_negative=True),
            Emotion(name="Focused", emoji="🎯", color="#4169E1", team_id=team.id, is_negative=False),
            Emotion(name="Frustrated", emoji="😤", color="#DC143C", team_id=team.id, is_negative=True),
        ]

    backend_emotions = _make_emotions(backend_team)
    frontend_emotions = _make_emotions(frontend_team)
    platform_emotions = _make_emotions(platform_team)
    session.add_all(backend_emotions + frontend_emotions + platform_emotions)
    session.flush()

    # --- Emotion Records (30+, spread over 30 days) ---
    now = datetime.datetime.utcnow()
    records = []

    # ~11 records per team = 33 total
    team_configs = [
        (backend_emotions, [alice, bob]),
        (frontend_emotions, [carol, dave]),
        (platform_emotions, [alice, carol]),
    ]

    day_offset = 0
    for emotions, members in team_configs:
        for i in range(11):
            user = members[i % len(members)]
            emotion = emotions[i % len(emotions)]
            is_anon = (i % 3 == 0)  # every 3rd record is anonymous
            records.append(EmotionRecord(
                user_id=None if is_anon else user.id,
                emotion_id=emotion.id,
                intensity=(i % 5) + 1,  # 1-5
                notes=f"Dev seed record {i}" if i % 2 == 0 else None,
                is_anonymous=is_anon,
                created_at=now - datetime.timedelta(days=day_offset % 30),
            ))
            day_offset += 1
    session.add_all(records)
    session.flush()

    # --- Feedback (5+) ---
    feedback_texts = [
        "Great sprint, team energy was high!",
        "Some blockers caused frustration mid-week.",
        "Communication improved noticeably this week.",
        "Deployment anxiety was palpable on Thursday.",
        "The team handled the incident really well.",
        "Would like more async updates to reduce meeting fatigue.",
    ]
    feedbacks = []
    for i, text in enumerate(feedback_texts):
        record = records[i]
        feedbacks.append(Feedback(
            message=text,
            emotion_record_id=record.id,
            manager_id=manager.id,
            is_anonymous=(i % 2 == 0),
            created_at=now - datetime.timedelta(days=i * 4),
        ))
    session.add_all(feedbacks)
    session.commit()
    print(f"Seed complete: 5 users, 3 teams, {len(records)} emotion records, {len(feedbacks)} feedback entries.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_seed.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/seed.py tests/test_seed.py
git commit -m "feat: add idempotent dev seed script with tests"
```

---

## Task 4: Create .env.example

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example`**

```
# Copy to .env for local non-Docker development
# Docker Compose sets these automatically

# PostgreSQL connection string
DATABASE_URL=postgresql://agilemood:agilemood@localhost:5432/agilemood

# JWT signing secret — CHANGE THIS in production
SECRET_KEY=dev-secret-key-change-in-prod
```

- [ ] **Step 2: Commit**

```bash
git add .env.example
git commit -m "chore: add .env.example with required env vars"
```

---

## Task 5: Create Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Verify image builds**

```bash
docker build -t agilemood-test .
```

Expected: `Successfully built <id>` — no errors.

Then clean up:

```bash
docker rmi agilemood-test
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile
git commit -m "feat: add Dockerfile for Python 3.12-slim app image"
```

---

## Task 6: Create entrypoint.sh

**Files:**
- Create: `entrypoint.sh`

- [ ] **Step 1: Create `entrypoint.sh`**

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

- [ ] **Step 2: Make it executable**

```bash
chmod +x entrypoint.sh
```

- [ ] **Step 3: Commit**

```bash
git add entrypoint.sh
git commit -m "feat: add entrypoint.sh for migrate-seed-start sequence"
```

---

## Task 7: Create docker-compose.yml

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create `docker-compose.yml`**

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

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose.yml with postgres and app services"
```

---

## Task 8: End-to-end verification

**No file changes — integration test only.**

- [ ] **Step 1: Build and start the stack**

```bash
docker-compose up --build
```

Watch logs. Expected sequence in app container:
```
Running Alembic migrations...
INFO  [alembic.runtime.migration] Running upgrade  -> 000, initial schema
INFO  [alembic.runtime.migration] Running upgrade 000 -> 001, add slack_webhook_url to team
Seeding database...
Seed complete: 5 users, 3 teams, 33 emotion records, 6 feedback entries.
Starting application...
INFO:     Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 2: Verify app responds**

In a new terminal:

```bash
curl -s http://localhost:8000/docs | head -5
```

Expected: HTML content (FastAPI Swagger UI)

- [ ] **Step 3: Verify login works with seed credentials**

```bash
curl -s -X POST http://localhost:8000/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=manager@agilemood.dev&password=password123"
```

Expected: JSON with `access_token` field.

- [ ] **Step 4: Verify idempotency — restart stack**

```bash
docker-compose down
docker-compose up
```

Watch logs. Expected:
```
Seed skipped: data already exists.
```

No duplicate data errors.

- [ ] **Step 5: Verify Alembic migration state**

```bash
docker-compose exec app alembic current
```

Expected: `001 (head)`

- [ ] **Step 6: Verify DB row counts**

```bash
docker-compose exec db psql -U agilemood -c 'SELECT COUNT(*) FROM "user";'
docker-compose exec db psql -U agilemood -c 'SELECT COUNT(*) FROM team;'
docker-compose exec db psql -U agilemood -c 'SELECT COUNT(*) FROM emotion_record;'
```

Expected: 5, 3, 33

- [ ] **Step 7: Run existing test suite (must still pass — tests use mocks, not Docker)**

```bash
pytest tests/ -v
```

Expected: all existing tests pass. New tests (`test_seed.py`, `test_migrations.py`) also pass.

- [ ] **Step 8: Tear down**

```bash
docker-compose down -v
```

The `-v` removes the named `postgres_data` volume (clean slate for next fresh start).

- [ ] **Step 9: Final commit**

```bash
git add .
git commit -m "chore: verify docker-compose e2e setup complete"
```
