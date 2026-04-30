# Teams Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Microsoft Teams integration delivering weekly mood reports (Mon 09:00 UTC) and check-in reminders (Fri 16:00 UTC) via proactive Bot Framework DMs — matching the existing Slack integration exactly.

**Architecture:** Graph API resolves users by email → AAD Object ID. Bot Framework Connector REST API sends Adaptive Card DMs. Credentials (app_id + app_secret + tenant_id) stored per team, app_secret encrypted with Fernet at rest. Existing slack_bot_token also encrypted for consistency. Token caching per job invocation. Jitter + 429 backoff on reminders.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, httpx (async), APScheduler, `cryptography` (Fernet), pytest, pytest-asyncio, unittest.mock

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `app/utils/encryption.py` | CREATE | `EncryptedString` TypeDecorator (Fernet) |
| `app/schemas/team_schema.py` | MODIFY | Change `slack_bot_token` → `EncryptedString`; add 3 Teams columns |
| `app/schemas/user_schema.py` | MODIFY | Add `teams_user_id` |
| `app/models/team_model.py` | MODIFY | Add `TeamsCredentialsUpdate`, update `TeamData` |
| `app/models/user_model.py` | MODIFY | Add `teams_user_id` to `UserInDB` and `UserInTeam` |
| `app/crud/team_crud.py` | MODIFY | Add `update_teams_credentials` |
| `app/crud/user_crud.py` | MODIFY | Add `update_teams_user_id` |
| `app/services/teams_service.py` | CREATE | Token helpers, user resolution, send_dm, card builders |
| `app/services/report_scheduler.py` | MODIFY | Add 2 Teams jobs to `create_scheduler` |
| `app/routers/team_router.py` | MODIFY | Add 2 Teams credential endpoints |
| `app/routers/user_router.py` | MODIFY | Add 4 Teams user ID endpoints + 2 test triggers |
| `migrations/versions/004_add_teams_credentials_to_team.py` | CREATE | DB columns for Teams on team table |
| `migrations/versions/005_add_teams_user_id_to_users.py` | CREATE | DB column for teams_user_id on user table |
| `teams-app-manifest.json` | CREATE | Azure Bot registration manifest |
| `docs/teams-integration.md` | CREATE | User guide (pt-BR) + dev reference (English) |
| `tests/teams_tests.py` | CREATE | ~55 tests mirroring slack_tests.py |

---

## Task 1: Update Design Doc

**Files:**
- Modify: `docs/superpowers/specs/2026-04-30-teams-integration-design.md`

- [ ] **Step 1: Append code review refinements section to the design doc**

Open `docs/superpowers/specs/2026-04-30-teams-integration-design.md` and append after the "Message Flow" section:

```markdown
---

## Code Review Refinements (2026-04-30)

1. **serviceUrl** — `smba.trafficmanager.net` hardcoded. GCC/regional tenants not supported in v1; document limitation.
2. **Token caching** — In-memory dict keyed by `app_id` per job invocation prevents redundant fetches when multiple teams share the same bot.
3. **Rate limiting** — `asyncio.sleep(random.uniform(0.1, 0.5))` between per-member DMs; `send_dm` handles 429 with `Retry-After` backoff up to 3 retries.
4. **Graph permissions** — `User.Read.All` (Application, admin consent required) instead of `User.ReadBasic.All` for reliability across all tenant policies.
5. **Credential encryption** — `EncryptedString` SQLAlchemy TypeDecorator (Fernet, key from `ENCRYPTION_KEY` env var) applied to `teams_app_secret` (new) and `slack_bot_token` (existing) for consistency.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/specs/2026-04-30-teams-integration-design.md
git commit -m "docs: update Teams design spec with code review refinements"
```

---

## Task 2: Encryption Utility

**Files:**
- Create: `app/utils/encryption.py`
- Create: `tests/test_encryption.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_encryption.py`:

```python
import os
import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch

TEST_KEY = Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def reset_fernet_singleton():
    import app.utils.encryption as enc
    enc._fernet = None
    yield
    enc._fernet = None


def test_encrypted_string_roundtrip():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import app.utils.encryption as enc
        col = enc.EncryptedString()
        original = "xoxb-super-secret-token"
        encrypted = col.process_bind_param(original, None)
        assert encrypted != original
        assert col.process_result_value(encrypted, None) == original


def test_encrypted_string_none_bind_passthrough():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import app.utils.encryption as enc
        col = enc.EncryptedString()
        assert col.process_bind_param(None, None) is None


def test_encrypted_string_none_result_passthrough():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import app.utils.encryption as enc
        col = enc.EncryptedString()
        assert col.process_result_value(None, None) is None


def test_encrypted_string_missing_key_raises():
    import app.utils.encryption as enc
    enc._fernet = None
    env = {k: v for k, v in os.environ.items() if k != "ENCRYPTION_KEY"}
    with patch.dict(os.environ, env, clear=True):
        col = enc.EncryptedString()
        with pytest.raises(ValueError, match="ENCRYPTION_KEY"):
            col.process_bind_param("some-value", None)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
cd /home/phos/Projects/tc/AgileMood-Backend && pytest tests/test_encryption.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `app.utils.encryption` does not exist yet.

- [ ] **Step 3: Implement `app/utils/encryption.py`**

```python
import os
from cryptography.fernet import Fernet
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = os.environ.get("ENCRYPTION_KEY")
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable is required")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _get_fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _get_fernet().decrypt(value.encode()).decode()
```

- [ ] **Step 4: Run to confirm PASS**

```bash
pytest tests/test_encryption.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/utils/encryption.py tests/test_encryption.py
git commit -m "feat: add EncryptedString TypeDecorator for secret columns at rest"
```

---

## Task 3: Schema Changes

**Files:**
- Modify: `app/schemas/team_schema.py`
- Modify: `app/schemas/user_schema.py`

- [ ] **Step 1: Update `app/schemas/team_schema.py`**

Change the import and `slack_bot_token` column, then add the 3 Teams columns:

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
import app.databases.postgres_database as db
from app.utils.constants import DataBase
from app.utils.encryption import EncryptedString
import datetime


user_teams = Table(
    "user_teams",
    db.Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id"), primary_key=True),
    Column("team_id", Integer, ForeignKey("team.id"), primary_key=True)
)


class Team(db.Base):
    __tablename__ = DataBase.TEAM_TABLE_NAME

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    manager_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    slack_bot_token = Column(EncryptedString, nullable=True)
    teams_app_id = Column(String, nullable=True)
    teams_app_secret = Column(EncryptedString, nullable=True)
    teams_tenant_id = Column(String, nullable=True)

    manager = relationship("User", back_populates="managed_teams")
    members = relationship("User", secondary="user_teams", back_populates="teams")
    emotions = relationship("Emotion", back_populates="team", cascade="all, delete")
```

- [ ] **Step 2: Update `app/schemas/user_schema.py`**

Add `teams_user_id` column:

```python
from sqlalchemy import Column, Integer, String, Boolean
import app.databases.postgres_database as db
from sqlalchemy.orm import relationship
from app.utils.constants import DataBase, Role


class User(db.Base):
    __tablename__ = DataBase.USER_TABLE_NAME

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    disabled = Column(Boolean, nullable=False, default=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default=Role.EMPLOYEE)
    avatar = Column(String, nullable=True)
    slack_user_id = Column(String, nullable=True)
    teams_user_id = Column(String, nullable=True)

    emotion_records = relationship("EmotionRecord", back_populates="user")
    managed_teams = relationship("Team", back_populates="manager")
    teams = relationship("Team", secondary="user_teams", back_populates="members")
```

- [ ] **Step 3: Verify schema tests still pass**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/slack_tests.py::test_team_schema_has_slack_bot_token_not_webhook \
       tests/slack_tests.py::test_user_schema_has_slack_user_id -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add app/schemas/team_schema.py app/schemas/user_schema.py
git commit -m "feat: add Teams credential columns and encrypt slack_bot_token at schema level"
```

---

## Task 4: Migrations

**Files:**
- Create: `migrations/versions/004_add_teams_credentials_to_team.py`
- Create: `migrations/versions/005_add_teams_user_id_to_users.py`

- [ ] **Step 1: Create `migrations/versions/004_add_teams_credentials_to_team.py`**

```python
"""Add Teams credentials to team table

Revision ID: 004
Revises: 003
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('team', sa.Column('teams_app_id', sa.String(), nullable=True))
    op.add_column('team', sa.Column('teams_app_secret', sa.String(), nullable=True))
    op.add_column('team', sa.Column('teams_tenant_id', sa.String(), nullable=True))
    # Note: slack_bot_token re-encryption is a manual step — existing tokens must be
    # re-saved via PUT /teams/{id}/slack-bot-token after setting ENCRYPTION_KEY.


def downgrade() -> None:
    op.drop_column('team', 'teams_tenant_id')
    op.drop_column('team', 'teams_app_secret')
    op.drop_column('team', 'teams_app_id')
```

- [ ] **Step 2: Create `migrations/versions/005_add_teams_user_id_to_users.py`**

```python
"""Add teams_user_id to user table

Revision ID: 005
Revises: 004
Create Date: 2026-04-30
"""
from alembic import op
import sqlalchemy as sa

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user', sa.Column('teams_user_id', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'teams_user_id')
```

- [ ] **Step 3: Commit**

```bash
git add migrations/versions/004_add_teams_credentials_to_team.py \
        migrations/versions/005_add_teams_user_id_to_users.py
git commit -m "feat: add migrations for Teams credentials and user ID columns"
```

---

## Task 5: Pydantic Models

**Files:**
- Modify: `app/models/team_model.py`
- Modify: `app/models/user_model.py`

- [ ] **Step 1: Write the failing tests (add to `tests/teams_tests.py` — create the file)**

```python
# tests/teams_tests.py
import os
import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient

from app.models.user_model import UserInDB
from app.utils.constants import Role
from app.routers.authentication import create_access_token

TEST_KEY = Fernet.generate_key().decode()

# ---------------------------------------------------------------------------
# Pydantic model verification
# ---------------------------------------------------------------------------

def test_team_schema_has_teams_credentials():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.schemas.team_schema import Team as TeamSchema
        assert hasattr(TeamSchema, "teams_app_id")
        assert hasattr(TeamSchema, "teams_app_secret")
        assert hasattr(TeamSchema, "teams_tenant_id")


def test_user_schema_has_teams_user_id():
    from app.schemas.user_schema import User as UserSchema
    assert hasattr(UserSchema, "teams_user_id")


def test_team_pydantic_model_has_teams_credentials():
    from app.models.team_model import TeamData, TeamsCredentialsUpdate
    td = TeamData(id=1, name="A", teams_app_id="app-id", teams_app_secret="secret", teams_tenant_id="tenant")
    assert td.teams_app_id == "app-id"
    creds = TeamsCredentialsUpdate(teams_app_id="id", teams_app_secret="sec", teams_tenant_id="ten")
    assert creds.teams_tenant_id == "ten"


def test_user_pydantic_model_has_teams_user_id():
    from app.models.user_model import UserInTeam
    u = UserInTeam(name="A", email="a@b.com", teams_user_id="aad-object-id-123")
    assert u.teams_user_id == "aad-object-id-123"
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$TEST_KEY pytest tests/teams_tests.py -v -k "pydantic or schema"
```

Expected: `ImportError` on `TeamsCredentialsUpdate` — not defined yet.

- [ ] **Step 3: Update `app/models/team_model.py`**

```python
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.user_model import UserInTeam
from app.models.emotion_record_model import EmotionRecordInTeam
from app.models.emotion_model import EmotionInDb
from typing import List, Optional


class Team(BaseModel):
    name: str

    class Config:
        from_attributes = True


class TeamData(Team):
    id: int
    manager_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    slack_bot_token: Optional[str] = None
    teams_app_id: Optional[str] = None
    teams_app_secret: Optional[str] = None
    teams_tenant_id: Optional[str] = None

    class Config:
        from_attributes = True


class SlackBotTokenUpdate(BaseModel):
    slack_bot_token: str


class TeamsCredentialsUpdate(BaseModel):
    teams_app_id: str
    teams_app_secret: str
    teams_tenant_id: str


class TeamResponse(BaseModel):
    team_data: TeamData
    members: List[UserInTeam]
    emotions_reports: List[EmotionRecordInTeam]
    emotions: List[EmotionInDb]
    manager: UserInTeam


class AllTeamsResponse(BaseModel):
    teams: List[TeamData]
```

- [ ] **Step 4: Update `app/models/user_model.py`**

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional


class User(BaseModel):
    name: str
    email: str
    disabled: bool | None = False
    role: Literal["manager", "employee"] = Field(default="employee", description="User role in the organization")
    avatar: str | None = None


class UserCreate(User):
    password: str


class UserInDB(User):
    id: int | None = None
    hashed_password: str
    slack_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None


class UserInTeam(BaseModel):
    name: str
    email: str
    team_id: int | None = None
    role: Literal["manager", "employee"] = Field(default="employee", description="User role in the organization")
    avatar: str | None = None
    slack_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None
```

- [ ] **Step 5: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "pydantic or schema"
```

Expected: 4 passed.

- [ ] **Step 6: Confirm existing Slack model tests still pass**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/slack_tests.py -v -k "pydantic or schema"
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add app/models/team_model.py app/models/user_model.py tests/teams_tests.py
git commit -m "feat: add TeamsCredentialsUpdate model and teams_user_id to user models"
```

---

## Task 6: CRUD Functions

**Files:**
- Modify: `app/crud/team_crud.py`
- Modify: `app/crud/user_crud.py`

- [ ] **Step 1: Write failing CRUD tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_update_teams_credentials_sets_values():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.crud.team_crud import update_teams_credentials
        db = MagicMock()
        mock_team = MagicMock(id=1)
        db.query.return_value.filter.return_value.first.return_value = mock_team
        result = update_teams_credentials(db, 1, "app-id", "app-secret", "tenant-id")
        assert mock_team.teams_app_id == "app-id"
        assert mock_team.teams_app_secret == "app-secret"
        assert mock_team.teams_tenant_id == "tenant-id"
        assert result == mock_team


def test_update_teams_credentials_clears_values():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.crud.team_crud import update_teams_credentials
        db = MagicMock()
        mock_team = MagicMock(id=1)
        db.query.return_value.filter.return_value.first.return_value = mock_team
        result = update_teams_credentials(db, 1, None, None, None)
        assert mock_team.teams_app_id is None
        assert mock_team.teams_app_secret is None
        assert mock_team.teams_tenant_id is None


def test_update_teams_credentials_team_not_found():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.crud.team_crud import update_teams_credentials
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = update_teams_credentials(db, 999, "id", "sec", "ten")
        assert result is None


def test_update_teams_user_id_sets_value():
    from app.crud.user_crud import update_teams_user_id
    db = MagicMock()
    mock_user = MagicMock(id=2)
    db.query.return_value.filter.return_value.first.return_value = mock_user
    result = update_teams_user_id(db, 2, "aad-object-id-abc")
    assert mock_user.teams_user_id == "aad-object-id-abc"
    assert result == mock_user


def test_update_teams_user_id_user_not_found():
    from app.crud.user_crud import update_teams_user_id
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    result = update_teams_user_id(db, 999, "aad-id")
    assert result is None
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "crud or credentials or teams_user_id"
```

Expected: `ImportError` — `update_teams_credentials` not defined.

- [ ] **Step 3: Add `update_teams_credentials` to `app/crud/team_crud.py`**

Add at the end of the file (after `update_slack_bot_token`):

```python
def update_teams_credentials(
    db: Session,
    team_id: int,
    app_id: str | None,
    app_secret: str | None,
    tenant_id: str | None,
):
    db_team = db.query(Team).filter(Team.id == team_id).first()
    if db_team is None:
        logger.error(f"Team with ID {team_id} not found.")
        return None
    db_team.teams_app_id = app_id
    db_team.teams_app_secret = app_secret
    db_team.teams_tenant_id = tenant_id
    db.commit()
    db.refresh(db_team)
    logger.debug(f"Teams credentials updated for team {team_id}.")
    return db_team
```

- [ ] **Step 4: Add `update_teams_user_id` to `app/crud/user_crud.py`**

Add at the end of the file (after `update_slack_user_id`):

```python
def update_teams_user_id(db: Session, user_id: int, teams_user_id: str | None):
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if db_user is None:
        logger.error(f"User with ID {user_id} not found.")
        return None
    db_user.teams_user_id = teams_user_id
    db.commit()
    db.refresh(db_user)
    logger.debug(f"Teams user ID updated for user {user_id}.")
    return db_user
```

- [ ] **Step 5: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "crud or credentials or teams_user_id"
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add app/crud/team_crud.py app/crud/user_crud.py tests/teams_tests.py
git commit -m "feat: add update_teams_credentials and update_teams_user_id CRUD functions"
```

---

## Task 7: Teams Service — Token Helpers

**Files:**
- Create: `app/services/teams_service.py`

- [ ] **Step 1: Write failing token tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# teams_service: token helpers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_graph_token_success():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import get_graph_token
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "graph-token-abc"}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(return_value=mock_response)
            token = await get_graph_token("tenant-id", "app-id", "app-secret")
        assert token == "graph-token-abc"


@pytest.mark.asyncio
async def test_get_graph_token_raises_on_http_error():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import httpx
        from app.services.teams_service import get_graph_token
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(status_code=401)
            ))
            with pytest.raises(httpx.HTTPStatusError):
                await get_graph_token("tenant-id", "app-id", "bad-secret")


@pytest.mark.asyncio
async def test_get_bot_token_success():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import get_bot_token
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "bot-token-xyz"}
        mock_response.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(return_value=mock_response)
            token = await get_bot_token("app-id", "app-secret")
        assert token == "bot-token-xyz"


@pytest.mark.asyncio
async def test_get_bot_token_raises_on_http_error():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import httpx
        from app.services.teams_service import get_bot_token
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(status_code=401)
            ))
            with pytest.raises(httpx.HTTPStatusError):
                await get_bot_token("app-id", "bad-secret")
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "token"
```

Expected: `ImportError` — `app.services.teams_service` does not exist.

- [ ] **Step 3: Create `app/services/teams_service.py` with token helpers**

```python
import asyncio
import random

import httpx

from app.utils.logger import logger

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
BOT_FRAMEWORK_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
BOT_FRAMEWORK_BASE = "https://smba.trafficmanager.net/apis"  # global; GCC/regional tenants unsupported in v1
REQUEST_TIMEOUT = 10.0
MAX_RETRIES = 3

ALERT_EMOJI_MAP = {
    "critical": "🔴",
    "warning": "🟡",
    "note": "🔵",
    "ok": "🟢",
}


def _classify_alert(negative_ratio: float) -> str:
    if negative_ratio > 50:
        return "critical"
    if negative_ratio > 30:
        return "warning"
    if negative_ratio > 15:
        return "note"
    return "ok"


async def get_graph_token(tenant_id: str, app_id: str, app_secret: str) -> str:
    url = GRAPH_TOKEN_URL.format(tenant_id=tenant_id)
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(url, data={
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_secret,
            "scope": "https://graph.microsoft.com/.default",
        })
        resp.raise_for_status()
        return resp.json()["access_token"]


async def get_bot_token(app_id: str, app_secret: str) -> str:
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.post(BOT_FRAMEWORK_TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_secret,
            "scope": "https://api.botframework.com/.default",
        })
        resp.raise_for_status()
        return resp.json()["access_token"]
```

- [ ] **Step 4: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "token"
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/teams_service.py tests/teams_tests.py
git commit -m "feat: add Teams service with Graph and Bot Framework token helpers"
```

---

## Task 8: Teams Service — User Resolution

**Files:**
- Modify: `app/services/teams_service.py`

- [ ] **Step 1: Write failing user resolution tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# teams_service: resolve_teams_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_teams_user_by_email():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import resolve_teams_user
        user = MagicMock(email="dev@example.com", teams_user_id=None)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "aad-object-id-123"}
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=mock_response)
            result = await resolve_teams_user("graph-token", user)
        assert result == "aad-object-id-123"


@pytest.mark.asyncio
async def test_resolve_teams_user_falls_back_to_override():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import resolve_teams_user
        user = MagicMock(email="dev@example.com", teams_user_id="manual-aad-id")
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=mock_response)
            result = await resolve_teams_user("graph-token", user)
        assert result == "manual-aad-id"


@pytest.mark.asyncio
async def test_resolve_teams_user_returns_none_when_unresolvable():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import resolve_teams_user
        user = MagicMock(email="nobody@example.com", teams_user_id=None)
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(return_value=mock_response)
            result = await resolve_teams_user("graph-token", user)
        assert result is None


@pytest.mark.asyncio
async def test_resolve_teams_user_handles_network_error_and_falls_back():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import httpx
        from app.services.teams_service import resolve_teams_user
        user = MagicMock(email="dev@example.com", teams_user_id="fallback-aad-id")
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.get = AsyncMock(side_effect=httpx.RequestError("timeout"))
            result = await resolve_teams_user("graph-token", user)
        assert result == "fallback-aad-id"
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "resolve"
```

Expected: `ImportError` — `resolve_teams_user` not defined.

- [ ] **Step 3: Add `resolve_teams_user` to `app/services/teams_service.py`**

Append after `get_bot_token`:

```python
async def resolve_teams_user(graph_token: str, user) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/users/{user.email}",
                headers={"Authorization": f"Bearer {graph_token}"},
            )
            if resp.status_code == 200:
                return resp.json()["id"]
            logger.warning(f"Graph user lookup returned {resp.status_code} for {user.email}")
    except Exception as exc:
        logger.error(f"Graph user lookup request failed for {user.email}: {exc}")

    if getattr(user, "teams_user_id", None):
        logger.info(f"Falling back to manual teams_user_id for {user.email}")
        return user.teams_user_id

    logger.warning(f"Cannot resolve Teams user for {user.email}. No override set.")
    return None
```

- [ ] **Step 4: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "resolve"
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/teams_service.py tests/teams_tests.py
git commit -m "feat: add resolve_teams_user with email lookup and manual ID fallback"
```

---

## Task 9: Teams Service — send_dm

**Files:**
- Modify: `app/services/teams_service.py`

- [ ] **Step 1: Write failing send_dm tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# teams_service: send_dm
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_dm_success():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import send_dm
        conv_resp = MagicMock(status_code=200)
        conv_resp.json.return_value = {"id": "conv-id-123"}
        conv_resp.raise_for_status = MagicMock()
        activity_resp = MagicMock(status_code=200)
        activity_resp.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=[conv_resp, activity_resp])
            result = await send_dm("bot-token", "app-id", "tenant-id", "user-aad-id", {"type": "AdaptiveCard"})
        assert result is True


@pytest.mark.asyncio
async def test_send_dm_conversation_creation_fails():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import httpx
        from app.services.teams_service import send_dm
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=httpx.RequestError("network error"))
            result = await send_dm("bot-token", "app-id", "tenant-id", "user-aad-id", {})
        assert result is False


@pytest.mark.asyncio
async def test_send_dm_retries_on_429():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import send_dm
        conv_resp = MagicMock(status_code=200)
        conv_resp.json.return_value = {"id": "conv-id-123"}
        conv_resp.raise_for_status = MagicMock()
        rate_limited = MagicMock(status_code=429)
        rate_limited.headers = {"Retry-After": "0"}
        ok_resp = MagicMock(status_code=200)
        ok_resp.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=[conv_resp, rate_limited, ok_resp])
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await send_dm("bot-token", "app-id", "tenant-id", "user-aad-id", {})
        assert result is True


@pytest.mark.asyncio
async def test_send_dm_fails_after_max_retries():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import send_dm, MAX_RETRIES
        conv_resp = MagicMock(status_code=200)
        conv_resp.json.return_value = {"id": "conv-id-123"}
        conv_resp.raise_for_status = MagicMock()
        rate_limited = MagicMock(status_code=429)
        rate_limited.headers = {"Retry-After": "0"}
        responses = [conv_resp] + [rate_limited] * MAX_RETRIES
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=responses)
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await send_dm("bot-token", "app-id", "tenant-id", "user-aad-id", {})
        assert result is False


@pytest.mark.asyncio
async def test_send_dm_timeout_returns_false():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        import httpx
        from app.services.teams_service import send_dm
        conv_resp = MagicMock(status_code=200)
        conv_resp.json.return_value = {"id": "conv-id-123"}
        conv_resp.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value.__aenter__.return_value
            instance.post = AsyncMock(side_effect=[conv_resp, httpx.TimeoutException("timeout")])
            result = await send_dm("bot-token", "app-id", "tenant-id", "user-aad-id", {})
        assert result is False
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "send_dm"
```

Expected: `ImportError` — `send_dm` not defined.

- [ ] **Step 3: Add `send_dm` to `app/services/teams_service.py`**

Append after `resolve_teams_user`:

```python
async def send_dm(
    bot_token: str,
    app_id: str,
    tenant_id: str,
    teams_user_id: str,
    card: dict,
) -> bool:
    headers = {"Authorization": f"Bearer {bot_token}"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        try:
            conv_resp = await client.post(
                f"{BOT_FRAMEWORK_BASE}/v3/conversations",
                json={
                    "bot": {"id": app_id, "name": "AgileMood"},
                    "isGroup": False,
                    "members": [{"id": teams_user_id}],
                    "channelData": {"tenant": {"id": tenant_id}},
                },
                headers=headers,
            )
            conv_resp.raise_for_status()
            conversation_id = conv_resp.json()["id"]
        except Exception as exc:
            logger.error(f"Failed to create Teams conversation for user {teams_user_id}: {exc}")
            return False

        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(
                    f"{BOT_FRAMEWORK_BASE}/v3/conversations/{conversation_id}/activities",
                    json={
                        "type": "message",
                        "attachments": [{
                            "contentType": "application/vnd.microsoft.card.adaptive",
                            "content": card,
                        }],
                    },
                    headers=headers,
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 2))
                    logger.warning(
                        f"Teams API rate limited. Retrying in {retry_after}s "
                        f"(attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return True
            except httpx.TimeoutException:
                logger.error(f"Teams DM timeout for user {teams_user_id} (attempt {attempt + 1})")
                return False
            except httpx.HTTPStatusError as exc:
                logger.error(f"Teams DM HTTP error for user {teams_user_id}: {exc}")
                return False

    logger.error(f"Teams DM failed after {MAX_RETRIES} attempts for user {teams_user_id}")
    return False
```

- [ ] **Step 4: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "send_dm"
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/teams_service.py tests/teams_tests.py
git commit -m "feat: add send_dm to teams_service with 429 Retry-After backoff"
```

---

## Task 10: Teams Service — Card Builders

**Files:**
- Modify: `app/services/teams_service.py`

- [ ] **Step 1: Write failing card builder tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# teams_service: card builders + _classify_alert
# ---------------------------------------------------------------------------

from app.models.reports_model import EmojiDistributionReport, EmojiDistribution

SAMPLE_EMOJI_REPORT = EmojiDistributionReport(
    emoji_distribution=[
        EmojiDistribution(emotion_name="Feliz", frequency=10),
        EmojiDistribution(emotion_name="Estressado", frequency=4),
    ],
    negative_emotion_ratio=28.6,
    alert=None,
)

SAMPLE_INTENSITY_REPORT = {
    "average_intensity": [
        {"emotion_name": "Feliz", "avg_intensity": 3.5},
        {"emotion_name": "Estressado", "avg_intensity": 4.2},
    ],
    "negative_emotion_ratio": 28.6,
    "alert": None,
}

SAMPLE_ANON_REPORT = {
    "user_name": "Anônimo",
    "all_user_emotion_records": [
        {"emotion_name": "Ansioso", "frequency": 2, "avg_intensity": 3.0},
    ],
}


def test_teams_classify_alert_critical():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import _classify_alert
        assert _classify_alert(51.0) == "critical"


def test_teams_classify_alert_warning():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import _classify_alert
        assert _classify_alert(35.0) == "warning"


def test_teams_classify_alert_note():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import _classify_alert
        assert _classify_alert(20.0) == "note"


def test_teams_classify_alert_ok():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import _classify_alert
        assert _classify_alert(10.0) == "ok"


def test_build_weekly_report_card_has_team_name():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_weekly_report_card
        card = build_weekly_report_card(
            "Time Alpha", "2026-04-04", "2026-04-11",
            SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
        )
        assert card["type"] == "AdaptiveCard"
        all_text = str(card)
        assert "Time Alpha" in all_text


def test_build_weekly_report_card_has_privacy_footer():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_weekly_report_card
        card = build_weekly_report_card(
            "Time Alpha", "2026-04-04", "2026-04-11",
            SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
        )
        all_text = str(card)
        assert "não contém dados individuais" in all_text


def test_build_weekly_report_card_contains_emotion_names():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_weekly_report_card
        card = build_weekly_report_card(
            "Time Alpha", "2026-04-04", "2026-04-11",
            SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
        )
        all_text = str(card)
        assert "Feliz" in all_text
        assert "Estressado" in all_text


def test_build_no_data_card_has_team_name():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_no_data_card
        card = build_no_data_card("Time Beta", "2026-04-04", "2026-04-11")
        assert card["type"] == "AdaptiveCard"
        assert "Time Beta" in str(card)


def test_build_no_data_card_has_no_data_message():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_no_data_card
        card = build_no_data_card("Time Beta", "2026-04-04", "2026-04-11")
        assert "Nenhum registro" in str(card)


def test_build_reminder_card_contains_message():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_reminder_card
        card = build_reminder_card()
        assert card["type"] == "AdaptiveCard"
        assert len(str(card)) > 50


def test_build_unreachable_notification_card_lists_emails():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.teams_service import build_unreachable_notification_card
        card = build_unreachable_notification_card(["a@b.com", "c@d.com"])
        all_text = str(card)
        assert "a@b.com" in all_text
        assert "c@d.com" in all_text
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "card or classify"
```

Expected: `ImportError` — card builders not defined.

- [ ] **Step 3: Add card builders to `app/services/teams_service.py`**

Append after `send_dm`:

```python
def build_weekly_report_card(
    team_name: str,
    start_date: str,
    end_date: str,
    emoji_report,
    intensity_report,
    anonymous_report,
) -> dict:
    alert = _classify_alert(emoji_report.negative_emotion_ratio)
    alert_emoji = ALERT_EMOJI_MAP[alert]

    emotion_lines = "\n".join(
        f"• {item.emotion_name}: {item.frequency}x"
        for item in emoji_report.emoji_distribution[:10]
    ) or "Nenhuma emoção registrada."

    intensity_data = intensity_report.get("average_intensity") or []
    intensity_lines = "\n".join(
        f"• {row['emotion_name']}: {row['avg_intensity']:.1f}/5"
        for row in intensity_data
    ) or "Nenhuma intensidade registrada."

    anon_records = anonymous_report.get("all_user_emotion_records") or []
    anon_lines = "\n".join(
        f"• {r['emotion_name']}: {r['frequency']}x (intensidade {r['avg_intensity']:.1f})"
        for r in anon_records
    ) or "Nenhum registro anônimo."

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"{alert_emoji} Relatório Semanal — {team_name}",
                "weight": "Bolder",
                "size": "Large",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Período: {start_date} a {end_date}",
                "isSubtle": True,
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"Emoções negativas: {emoji_report.negative_emotion_ratio:.1f}%",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "**Distribuição de emoções (top 10):**",
                "wrap": True,
            },
            {"type": "TextBlock", "text": emotion_lines, "wrap": True},
            {
                "type": "TextBlock",
                "text": "**Intensidade média por emoção:**",
                "wrap": True,
            },
            {"type": "TextBlock", "text": intensity_lines, "wrap": True},
            {
                "type": "TextBlock",
                "text": "**Registros anônimos:**",
                "wrap": True,
            },
            {"type": "TextBlock", "text": anon_lines, "wrap": True},
            {
                "type": "TextBlock",
                "text": "_Este relatório não contém dados individuais. Todas as estatísticas são agregados do time._",
                "isSubtle": True,
                "wrap": True,
            },
        ],
    }


def build_no_data_card(team_name: str, start_date: str, end_date: str) -> dict:
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": f"📊 Relatório Semanal — {team_name}",
                "weight": "Bolder",
                "size": "Large",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": (
                    f"Nenhum registro de emoção encontrado no período "
                    f"{start_date} a {end_date}. "
                    "Incentive o time a registrar o humor!"
                ),
                "wrap": True,
            },
        ],
    }


def build_reminder_card() -> dict:
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "🧠 Lembrete Semanal — AgileMood",
                "weight": "Bolder",
                "size": "Large",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": (
                    "Não se esqueça de registrar seu humor desta semana! "
                    "Sua participação ajuda o time a manter um ambiente saudável e seguro."
                ),
                "wrap": True,
            },
        ],
    }


def build_unreachable_notification_card(unreachable_emails: list[str]) -> dict:
    email_list = "\n".join(f"• {email}" for email in unreachable_emails)
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "⚠️ Membros não alcançados pelo Teams",
                "weight": "Bolder",
                "size": "Large",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": (
                    "Os seguintes membros não puderam ser contatados via Teams. "
                    "Configure o ID do Teams manualmente em Configurações → Membros:"
                ),
                "wrap": True,
            },
            {"type": "TextBlock", "text": email_list, "wrap": True},
        ],
    }
```

- [ ] **Step 4: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "card or classify"
```

Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/teams_service.py tests/teams_tests.py
git commit -m "feat: add Adaptive Card builders to teams_service (Portuguese)"
```

---

## Task 11: API Endpoints

**Files:**
- Modify: `app/routers/team_router.py`
- Modify: `app/routers/user_router.py`

- [ ] **Step 1: Write failing API endpoint tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

manager_user = UserInDB(
    id=1, name="Manager", email="manager@example.com",
    disabled=False, role=Role.MANAGER, hashed_password="x",
)
employee_user = UserInDB(
    id=2, name="Employee", email="employee@example.com",
    disabled=False, role=Role.EMPLOYEE, hashed_password="x",
)
mock_team_dict = {
    "team_data": MagicMock(id=1, manager_id=1),
    "members": [],
    "emotions_reports": [],
}


def test_manager_can_set_teams_credentials():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})
        mock_team = MagicMock(
            id=1, manager_id=1, name="A",
            slack_bot_token=None, teams_app_id=None,
            teams_app_secret=None, teams_tenant_id=None,
            created_at=None,
        )
        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_team_by_id", return_value=mock_team_dict), \
             patch("app.crud.team_crud.update_teams_credentials", return_value=mock_team), \
             patch("app.core.auth_utils.ensure_is_team_manager"):
            resp = client.put(
                "/teams/1/teams-credentials",
                json={"teams_app_id": "app-id", "teams_app_secret": "secret", "teams_tenant_id": "tenant"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


def test_employee_cannot_set_teams_credentials():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": employee_user.email})
        with patch("app.routers.authentication.get_current_active_user", return_value=employee_user), \
             patch("app.crud.team_crud.get_team_by_id", return_value=mock_team_dict), \
             patch("app.core.auth_utils.ensure_is_team_manager", side_effect=Exception("NO_PERMISSION")):
            resp = client.put(
                "/teams/1/teams-credentials",
                json={"teams_app_id": "id", "teams_app_secret": "sec", "teams_tenant_id": "ten"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code != 200


def test_manager_can_remove_teams_credentials():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})
        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_team_by_id", return_value=mock_team_dict), \
             patch("app.crud.team_crud.update_teams_credentials", return_value=MagicMock()), \
             patch("app.core.auth_utils.ensure_is_team_manager"):
            resp = client.delete(
                "/teams/1/teams-credentials",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


def test_manager_can_set_teams_user_id():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})
        mock_user = MagicMock(
            id=2, name="Dev", email="dev@example.com",
            disabled=False, role=Role.EMPLOYEE, hashed_password="x",
            slack_user_id=None, teams_user_id="aad-123",
        )
        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.user_crud.get_user_by_id", return_value=mock_user), \
             patch("app.crud.user_crud.update_teams_user_id", return_value=mock_user):
            resp = client.put(
                "/user/2/teams-user-id",
                json={"teams_user_id": "aad-123"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


def test_employee_cannot_set_teams_user_id():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": employee_user.email})
        with patch("app.routers.authentication.get_current_active_user", return_value=employee_user):
            resp = client.put(
                "/user/2/teams-user-id",
                json={"teams_user_id": "aad-123"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403 or resp.status_code == 401


def test_manager_can_remove_teams_user_id():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})
        mock_user = MagicMock(id=2)
        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.user_crud.get_user_by_id", return_value=mock_user), \
             patch("app.crud.user_crud.update_teams_user_id", return_value=mock_user):
            resp = client.delete(
                "/user/2/teams-user-id",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


def test_set_teams_credentials_team_not_found():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})
        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_team_by_id", return_value=None):
            resp = client.put(
                "/teams/999/teams-credentials",
                json={"teams_app_id": "id", "teams_app_secret": "sec", "teams_tenant_id": "ten"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404


def test_set_teams_user_id_user_not_found():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})
        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.user_crud.get_user_by_id", return_value=None):
            resp = client.put(
                "/user/999/teams-user-id",
                json={"teams_user_id": "aad-123"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 404
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "credentials or teams_user_id" --ignore=tests/test_encryption.py
```

Expected: 404 on all endpoint tests — routes not registered yet.

- [ ] **Step 3: Add Teams credential endpoints to `app/routers/team_router.py`**

Add imports at top of file:
```python
from app.models.team_model import Team, TeamResponse, AllTeamsResponse, TeamData, SlackBotTokenUpdate, TeamsCredentialsUpdate
```

Then append at the end of the file:

```python
@router.put("/{team_id}/teams-credentials", response_model=TeamData)
def set_teams_credentials(
    team_id: int,
    creds: TeamsCredentialsUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND
    ensure_is_team_manager(team, current_user)
    updated = team_crud.update_teams_credentials(
        db, team_id, creds.teams_app_id, creds.teams_app_secret, creds.teams_tenant_id
    )
    if updated is None:
        raise Errors.INVALID_PARAMS
    return updated


@router.delete("/{team_id}/teams-credentials")
def remove_teams_credentials(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND
    ensure_is_team_manager(team, current_user)
    team_crud.update_teams_credentials(db, team_id, None, None, None)
    return {"message": f"Teams credentials removed for team {team_id}."}
```

- [ ] **Step 4: Add Teams user ID endpoints to `app/routers/user_router.py`**

Append at the end of the file:

```python
class TeamsUserIdUpdate(BaseModel):
    teams_user_id: str


@router.put("/{user_id}/teams-user-id", response_model=UserInDB)
def set_teams_user_id(
    user_id: int,
    teams_id_update: TeamsUserIdUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION
    target_user = user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise Errors.NOT_FOUND
    updated = user_crud.update_teams_user_id(db, user_id, teams_id_update.teams_user_id)
    if updated is None:
        raise Errors.INVALID_PARAMS
    return updated


@router.delete("/{user_id}/teams-user-id")
def remove_teams_user_id(
    user_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION
    target_user = user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise Errors.NOT_FOUND
    user_crud.update_teams_user_id(db, user_id, None)
    return {"message": f"Teams user ID removed for user {user_id}."}
```

Also add the two test trigger endpoints (append before the `TeamsUserIdUpdate` class):

```python
@router.post("/test/trigger-teams-reports")
async def trigger_teams_reports_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_weekly_teams_reports)
    return {"message": "Weekly Teams reports triggered in the background!"}


@router.post("/test/trigger-teams-reminders")
async def trigger_teams_reminders_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_weekly_teams_reminders)
    return {"message": "Weekly Teams reminders triggered in the background!"}
```

Add imports at the top of `user_router.py` (add alongside existing scheduler imports):
```python
from app.services.report_scheduler import send_weekly_reports, send_weekly_reminders, send_weekly_teams_reports, send_weekly_teams_reminders
```

- [ ] **Step 5: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "manager_can or employee_cannot or not_found or remove_teams"
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add app/routers/team_router.py app/routers/user_router.py tests/teams_tests.py
git commit -m "feat: add Teams credential and user ID endpoints"
```

---

## Task 12: Scheduler Jobs

**Files:**
- Modify: `app/services/report_scheduler.py`

- [ ] **Step 1: Write failing scheduler tests (append to `tests/teams_tests.py`)**

```python
# ---------------------------------------------------------------------------
# Scheduler: send_weekly_teams_reports + send_weekly_teams_reminders
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_skips_team_without_teams_credentials():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reports
        mock_team = MagicMock(id=1, name="A", teams_app_id=None, teams_app_secret=None, teams_tenant_id=None)
        with patch("app.crud.team_crud.get_all_teams", return_value=[mock_team]), \
             patch("app.services.report_scheduler.get_graph_token") as mock_graph_token:
            await send_weekly_teams_reports()
        mock_graph_token.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_sends_report_dm_to_manager():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reports
        from app.models.reports_model import EmojiDistributionReport, EmojiDistribution
        mock_team = MagicMock(
            id=1, name="A",
            teams_app_id="app-id", teams_app_secret="secret", teams_tenant_id="tenant",
            manager=MagicMock(email="manager@test.com", teams_user_id=None),
        )
        emoji_report = EmojiDistributionReport(
            emoji_distribution=[EmojiDistribution(emotion_name="Feliz", frequency=5)],
            negative_emotion_ratio=10.0, alert=None,
        )
        with patch("app.crud.team_crud.get_all_teams", return_value=[mock_team]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="graph-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="mgr-aad-id"), \
             patch("app.crud.reports_crud.get_emoji_distribution_report", return_value=emoji_report), \
             patch("app.crud.reports_crud.get_average_intensity_report", return_value={"average_intensity": [], "negative_emotion_ratio": 10.0, "alert": None}), \
             patch("app.crud.reports_crud.get_anonymous_emotion_analysis", return_value={"all_user_emotion_records": []}), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True) as mock_send:
            await send_weekly_teams_reports()
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_sends_no_data_message_when_empty():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reports
        from app.models.reports_model import EmojiDistributionReport
        mock_team = MagicMock(
            id=1, name="A",
            teams_app_id="app-id", teams_app_secret="sec", teams_tenant_id="ten",
            manager=MagicMock(email="mgr@test.com", teams_user_id=None),
        )
        empty_report = EmojiDistributionReport(emoji_distribution=[], negative_emotion_ratio=0.0, alert=None)
        with patch("app.crud.team_crud.get_all_teams", return_value=[mock_team]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="g-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="mgr-id"), \
             patch("app.crud.reports_crud.get_emoji_distribution_report", return_value=empty_report), \
             patch("app.crud.reports_crud.get_average_intensity_report", return_value={}), \
             patch("app.crud.reports_crud.get_anonymous_emotion_analysis", return_value={}), \
             patch("app.services.report_scheduler.build_no_data_card") as mock_no_data, \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True):
            await send_weekly_teams_reports()
        mock_no_data.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_report_continues_after_per_team_error():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reports
        team_ok = MagicMock(id=2, name="B", teams_app_id="id", teams_app_secret="sec", teams_tenant_id="ten")
        team_err = MagicMock(id=1, name="A", teams_app_id="id", teams_app_secret="sec", teams_tenant_id="ten")
        with patch("app.crud.team_crud.get_all_teams", return_value=[team_err, team_ok]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, side_effect=[Exception("fail"), "tok"]), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="mgr"), \
             patch("app.crud.reports_crud.get_emoji_distribution_report", return_value=MagicMock(emoji_distribution=[])), \
             patch("app.crud.reports_crud.get_average_intensity_report", return_value={}), \
             patch("app.crud.reports_crud.get_anonymous_emotion_analysis", return_value={}), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True) as mock_send:
            await send_weekly_teams_reports()
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_reminder_scheduler_sends_dm_to_members():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reminders
        member = MagicMock(email="member@test.com", teams_user_id=None)
        mock_team = MagicMock(
            id=1, name="A",
            teams_app_id="id", teams_app_secret="sec", teams_tenant_id="ten",
            members=[member],
            manager=MagicMock(email="mgr@test.com", teams_user_id=None),
        )
        with patch("app.crud.team_crud.get_all_teams", return_value=[mock_team]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="g-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="member-aad"), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True) as mock_send, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await send_weekly_teams_reminders()
        mock_send.assert_called()


@pytest.mark.asyncio
async def test_reminder_notifies_manager_of_unreachable_members():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reminders
        member = MagicMock(email="ghost@test.com", teams_user_id=None)
        mock_team = MagicMock(
            id=1, name="A",
            teams_app_id="id", teams_app_secret="sec", teams_tenant_id="ten",
            members=[member],
            manager=MagicMock(email="mgr@test.com", teams_user_id=None),
        )
        resolve_calls = [None, "mgr-aad-id"]
        with patch("app.crud.team_crud.get_all_teams", return_value=[mock_team]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="g-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, side_effect=resolve_calls), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True) as mock_send, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            await send_weekly_teams_reminders()
        assert mock_send.call_count == 1


@pytest.mark.asyncio
async def test_reminder_scheduler_jitter_sleep_called():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.services.report_scheduler import send_weekly_teams_reminders
        members = [MagicMock(email=f"m{i}@test.com", teams_user_id=None) for i in range(3)]
        mock_team = MagicMock(
            id=1, name="A",
            teams_app_id="id", teams_app_secret="sec", teams_tenant_id="ten",
            members=members,
            manager=MagicMock(email="mgr@test.com", teams_user_id=None),
        )
        with patch("app.crud.team_crud.get_all_teams", return_value=[mock_team]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="g-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="member-aad"), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True), \
             patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await send_weekly_teams_reminders()
        assert mock_sleep.call_count >= 3
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "scheduler"
```

Expected: `ImportError` — `send_weekly_teams_reports` not defined.

- [ ] **Step 3: Update `app/services/report_scheduler.py`**

Add imports at the top (after existing imports):

```python
from app.services.teams_service import (
    build_weekly_report_card,
    build_no_data_card,
    build_reminder_card,
    build_unreachable_notification_card,
    resolve_teams_user,
    get_graph_token,
    get_bot_token,
    send_dm as send_teams_dm,
)
import random
```

Append two new async functions before `create_scheduler`:

```python
async def send_weekly_teams_reports():
    db = SessionLocal()
    try:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        teams = team_crud.get_all_teams(db)
        logger.debug(f"Weekly Teams report job started. Processing {len(teams)} teams.")
        token_cache: dict[str, tuple[str, str]] = {}

        for team in teams:
            if not all([team.teams_app_id, team.teams_app_secret, team.teams_tenant_id]):
                logger.debug(f"Team {team.id} ({team.name!r}) has no Teams credentials. Skipping.")
                continue
            try:
                if team.teams_app_id not in token_cache:
                    graph_token = await get_graph_token(team.teams_tenant_id, team.teams_app_id, team.teams_app_secret)
                    bot_token = await get_bot_token(team.teams_app_id, team.teams_app_secret)
                    token_cache[team.teams_app_id] = (graph_token, bot_token)
                graph_token, bot_token = token_cache[team.teams_app_id]

                manager_id = await resolve_teams_user(graph_token, team.manager)
                if not manager_id:
                    logger.error(f"Cannot resolve Teams ID for manager of team {team.id}. Skipping report.")
                    continue

                emoji_report = reports_crud.get_emoji_distribution_report(db, team.id, start_str, end_str)
                intensity_report = reports_crud.get_average_intensity_report(db, team.id, start_str, end_str)
                anonymous_report = reports_crud.get_anonymous_emotion_analysis(db, team.id, start_str, end_str)

                if not emoji_report.emoji_distribution:
                    card = build_no_data_card(team.name, start_str, end_str)
                else:
                    card = build_weekly_report_card(
                        team_name=team.name,
                        start_date=start_str,
                        end_date=end_str,
                        emoji_report=emoji_report,
                        intensity_report=intensity_report,
                        anonymous_report=anonymous_report,
                    )

                success = await send_teams_dm(bot_token, team.teams_app_id, team.teams_tenant_id, manager_id, card)
                if success:
                    logger.debug(f"Teams report DM sent for team {team.id} ({team.name!r}).")
                else:
                    logger.warning(f"Teams report DM FAILED for team {team.id} ({team.name!r}).")
            except Exception as exc:
                logger.error(f"Error generating/sending Teams report for team {team.id}: {exc}", exc_info=True)
    finally:
        db.close()


async def send_weekly_teams_reminders():
    db = SessionLocal()
    try:
        teams = team_crud.get_all_teams(db)
        logger.debug(f"Weekly Teams reminder job started. Processing {len(teams)} teams.")
        token_cache: dict[str, tuple[str, str]] = {}

        for team in teams:
            if not all([team.teams_app_id, team.teams_app_secret, team.teams_tenant_id]):
                logger.debug(f"Team {team.id} ({team.name!r}) has no Teams credentials. Skipping.")
                continue
            try:
                if team.teams_app_id not in token_cache:
                    graph_token = await get_graph_token(team.teams_tenant_id, team.teams_app_id, team.teams_app_secret)
                    bot_token = await get_bot_token(team.teams_app_id, team.teams_app_secret)
                    token_cache[team.teams_app_id] = (graph_token, bot_token)
                graph_token, bot_token = token_cache[team.teams_app_id]

                reminder_card = build_reminder_card()
                unreachable = []

                for member in team.members:
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    member_id = await resolve_teams_user(graph_token, member)
                    if member_id:
                        success = await send_teams_dm(bot_token, team.teams_app_id, team.teams_tenant_id, member_id, reminder_card)
                        if not success:
                            logger.warning(f"Failed to send Teams reminder DM to {member.email}")
                    else:
                        unreachable.append(member.email)

                if unreachable:
                    manager_id = await resolve_teams_user(graph_token, team.manager)
                    if manager_id:
                        notif_card = build_unreachable_notification_card(unreachable)
                        await send_teams_dm(bot_token, team.teams_app_id, team.teams_tenant_id, manager_id, notif_card)
                    else:
                        logger.error(f"Manager of team {team.id} also unreachable via Teams. Cannot notify.")
            except Exception as exc:
                logger.error(f"Error sending Teams reminders for team {team.id}: {exc}", exc_info=True)
    finally:
        db.close()
```

Add the two new jobs inside `create_scheduler()` (after existing `scheduler.add_job` calls):

```python
    scheduler.add_job(
        send_weekly_teams_reports,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=pytz.UTC),
        id="weekly_teams_report",
        name="Weekly Teams Mood Report",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        send_weekly_teams_reminders,
        CronTrigger(day_of_week="fri", hour=16, minute=0, timezone=pytz.UTC),
        id="weekly_teams_reminder",
        name="Weekly Teams Mood Reminder",
        replace_existing=True,
        misfire_grace_time=3600,
    )
```

Also add `import asyncio` at the top of `report_scheduler.py` (after existing imports).

- [ ] **Step 4: Run to confirm PASS**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "scheduler"
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add app/services/report_scheduler.py tests/teams_tests.py
git commit -m "feat: add Teams weekly report and reminder scheduler jobs"
```

---

## Task 13: Integration Tests

**Files:**
- Modify: `tests/teams_tests.py`

- [ ] **Step 1: Write integration tests (append to `tests/teams_tests.py`)**

These tests wire the API → CRUD → scheduler flow end-to-end with mocked external HTTP calls.

```python
# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_integration_set_credentials_then_trigger_report():
    """Set credentials via API (in-memory DB), then trigger report and verify DM attempted."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        from app.models.reports_model import EmojiDistributionReport, EmojiDistribution
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})

        mock_team_obj = MagicMock(
            id=1, name="IntegrationTeam",
            teams_app_id="int-app-id", teams_app_secret="int-secret", teams_tenant_id="int-tenant",
            manager=MagicMock(email=manager_user.email, teams_user_id=None),
            members=[],
        )
        emoji_report = EmojiDistributionReport(
            emoji_distribution=[EmojiDistribution(emotion_name="Calmo", frequency=3)],
            negative_emotion_ratio=5.0, alert=None,
        )

        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_all_teams", return_value=[mock_team_obj]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="g-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="mgr-aad"), \
             patch("app.crud.reports_crud.get_emoji_distribution_report", return_value=emoji_report), \
             patch("app.crud.reports_crud.get_average_intensity_report", return_value={"average_intensity": [], "negative_emotion_ratio": 5.0, "alert": None}), \
             patch("app.crud.reports_crud.get_anonymous_emotion_analysis", return_value={"all_user_emotion_records": []}), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True) as mock_dm:
            resp = client.post(
                "/user/test/trigger-teams-reports",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            import asyncio
            await asyncio.sleep(0.05)

        mock_dm.assert_called_once()


@pytest.mark.asyncio
async def test_integration_trigger_reminders_sends_to_members():
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})

        member = MagicMock(email="member@integration.com", teams_user_id=None)
        mock_team_obj = MagicMock(
            id=1, name="IntegrationTeam",
            teams_app_id="int-app-id", teams_app_secret="int-sec", teams_tenant_id="int-ten",
            members=[member],
            manager=MagicMock(email=manager_user.email, teams_user_id=None),
        )

        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_all_teams", return_value=[mock_team_obj]), \
             patch("app.services.report_scheduler.get_graph_token", new_callable=AsyncMock, return_value="g-tok"), \
             patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="b-tok"), \
             patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="member-aad"), \
             patch("app.services.report_scheduler.send_teams_dm", new_callable=AsyncMock, return_value=True) as mock_dm, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            resp = client.post(
                "/user/test/trigger-teams-reminders",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200
            import asyncio
            await asyncio.sleep(0.05)

        assert mock_dm.called


def test_integration_teams_credentials_roundtrip():
    """PUT credentials → verify fields stored → DELETE → verify cleared."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.main import app
        client = TestClient(app)
        token = create_access_token({"sub": manager_user.email})

        stored = {}

        def fake_update(db, team_id, app_id, app_secret, tenant_id):
            stored.update({"app_id": app_id, "app_secret": app_secret, "tenant_id": tenant_id})
            return MagicMock(id=1, name="A", teams_app_id=app_id, teams_app_secret=app_secret,
                             teams_tenant_id=tenant_id, slack_bot_token=None, created_at=None, manager_id=1)

        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_team_by_id", return_value=mock_team_dict), \
             patch("app.crud.team_crud.update_teams_credentials", side_effect=fake_update), \
             patch("app.core.auth_utils.ensure_is_team_manager"):
            resp = client.put(
                "/teams/1/teams-credentials",
                json={"teams_app_id": "my-app", "teams_app_secret": "my-secret", "teams_tenant_id": "my-tenant"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert stored["app_id"] == "my-app"
        assert stored["tenant_id"] == "my-tenant"

        with patch("app.routers.authentication.get_current_active_user", return_value=manager_user), \
             patch("app.crud.team_crud.get_team_by_id", return_value=mock_team_dict), \
             patch("app.crud.team_crud.update_teams_credentials", side_effect=fake_update), \
             patch("app.core.auth_utils.ensure_is_team_manager"):
            resp = client.delete(
                "/teams/1/teams-credentials",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert stored["app_id"] is None


def test_integration_encryption_applied_to_app_secret():
    """Verify EncryptedString is used on teams_app_secret column."""
    with patch.dict(os.environ, {"ENCRYPTION_KEY": TEST_KEY}):
        from app.schemas.team_schema import Team as TeamSchema
        from app.utils.encryption import EncryptedString
        col = TeamSchema.__table__.c["teams_app_secret"]
        assert isinstance(col.type, EncryptedString)
```

- [ ] **Step 2: Run integration tests**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v -k "integration"
```

Expected: 4 passed.

- [ ] **Step 3: Run full teams test suite**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py -v
```

Expected: ~55 passed, 0 failed.

- [ ] **Step 4: Commit**

```bash
git add tests/teams_tests.py
git commit -m "test: add integration tests for Teams credentials, scheduler, and encryption"
```

---

## Task 14: Supporting Files

**Files:**
- Create: `teams-app-manifest.json`
- Create: `docs/teams-integration.md`

- [ ] **Step 1: Create `teams-app-manifest.json`**

```json
{
  "$schema": "https://developer.microsoft.com/en-us/json-schemas/teams/v1.16/MicrosoftTeams.schema.json",
  "manifestVersion": "1.16",
  "version": "1.0.0",
  "id": "{{YOUR_BOT_APP_ID}}",
  "packageName": "com.agilemood.teamsbot",
  "developer": {
    "name": "AgileMood",
    "websiteUrl": "https://github.com/your-org/AgileMood",
    "privacyUrl": "https://github.com/your-org/AgileMood/privacy",
    "termsOfUseUrl": "https://github.com/your-org/AgileMood/terms"
  },
  "name": {
    "short": "AgileMood",
    "full": "AgileMood – Segurança Psicológica para Times Ágeis"
  },
  "description": {
    "short": "Rastreador de segurança psicológica para times ágeis.",
    "full": "Envia relatórios semanais de humor e lembretes via DM no Microsoft Teams."
  },
  "icons": {
    "color": "color.png",
    "outline": "outline.png"
  },
  "accentColor": "#0078D4",
  "bots": [
    {
      "botId": "{{YOUR_BOT_APP_ID}}",
      "scopes": ["personal"],
      "isNotificationOnly": true,
      "supportsCalling": false,
      "supportsVideo": false,
      "supportsFiles": false
    }
  ],
  "permissions": ["identity", "messageTeamMembers"],
  "validDomains": ["smba.trafficmanager.net"]
}
```

**Azure Bot registration required permissions (configured in Azure Portal → App Registration → API Permissions):**
- `User.Read.All` — Application — Admin consent required
- `offline_access` — Delegated (optional)

Bot Framework channel permissions are granted automatically when you enable the Microsoft Teams channel on the bot.

- [ ] **Step 2: Create `docs/teams-integration.md`**

```markdown
# Integração com Microsoft Teams

## Guia do Usuário

### Pré-requisitos

- Acesso à conta do **Microsoft Azure** com permissão para criar registros de aplicativos
- Papel de **gestor de time** no AgileMood

### Passo 1 — Criar o Registro do Aplicativo no Azure

1. Acesse [portal.azure.com](https://portal.azure.com) e faça login
2. Pesquise por **"Registros de aplicativos"** e clique em **Novo registro**
3. Preencha:
   - **Nome:** AgileMood
   - **Tipos de conta com suporte:** Contas somente neste diretório organizacional
4. Clique em **Registrar**
5. Anote o **ID do aplicativo (cliente)** — este é o seu `teams_app_id`
6. Anote o **ID do diretório (locatário)** — este é o seu `teams_tenant_id`

### Passo 2 — Criar um Segredo do Cliente

1. No registro do aplicativo, vá em **Certificados e segredos → Novo segredo do cliente**
2. Adicione uma descrição (ex: "AgileMood Bot") e defina o vencimento
3. Clique em **Adicionar** e copie o **Valor** imediatamente
4. Este valor é o seu `teams_app_secret` — ele não será exibido novamente

### Passo 3 — Criar o Recurso Azure Bot

1. Pesquise por **"Azure Bot"** e clique em **Criar**
2. Preencha:
   - **Identificador de bot:** AgileMood (único globalmente)
   - **Assinatura e Grupo de recursos:** conforme sua organização
   - **ID do aplicativo Microsoft:** use o ID criado no Passo 1
3. Clique em **Revisar + criar**
4. Após criar, vá em **Canais → Microsoft Teams** e ative o canal

### Passo 4 — Configurar Permissões da API

1. No registro do aplicativo (Passo 1), vá em **Permissões de API**
2. Clique em **Adicionar uma permissão → Microsoft Graph → Permissões de aplicativo**
3. Pesquise e selecione `User.Read.All`
4. Clique em **Conceder consentimento de administrador**

### Passo 5 — Configurar o AgileMood

Chame a API do AgileMood com as credenciais criadas:

```http
PUT /teams/{team_id}/teams-credentials
Authorization: Bearer <seu_token>
Content-Type: application/json

{
  "teams_app_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "teams_app_secret": "seu_segredo_aqui",
  "teams_tenant_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

### Passo 6 — Configurar IDs de Usuário (Opcional)

Se a resolução automática por e-mail falhar, configure o ID do Azure AD manualmente:

```http
PUT /user/{user_id}/teams-user-id
Authorization: Bearer <seu_token>
Content-Type: application/json

{
  "teams_user_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Para encontrar o ID do usuário no Azure AD:
1. Vá em **Azure AD → Usuários** no portal
2. Pesquise pelo e-mail do usuário
3. Copie o **ID do objeto**

### Cronograma de Mensagens

| Mensagem | Quando | Destinatário |
|----------|--------|-------------|
| Relatório semanal | Segunda-feira às 09:00 UTC | Gestor do time |
| Lembrete semanal | Sexta-feira às 16:00 UTC | Todos os membros |

### Privacidade

Os relatórios contêm apenas **agregados do time** — nenhum dado individual é compartilhado.

---

## Developer Reference

### Architecture

```
Manager configures credentials
    ↓
PUT /teams/{id}/teams-credentials
    ↓
team_crud.update_teams_credentials() → encrypted in DB
    ↓
APScheduler triggers Monday 09:00 UTC
    ↓
send_weekly_teams_reports()
    ├─ get_graph_token(tenant_id, app_id, app_secret)
    │   └─ POST login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
    ├─ get_bot_token(app_id, app_secret)
    │   └─ POST login.microsoftonline.com/botframework.com/oauth2/v2.0/token
    ├─ resolve_teams_user(graph_token, manager)
    │   └─ GET graph.microsoft.com/v1.0/users/{email} → AAD Object ID
    │   └─ fallback: user.teams_user_id
    ├─ reports_crud → report data
    ├─ build_weekly_report_card() → Adaptive Card dict
    └─ send_dm(bot_token, app_id, tenant_id, manager_aad_id, card)
        ├─ POST smba.trafficmanager.net/apis/v3/conversations
        └─ POST smba.trafficmanager.net/apis/v3/conversations/{id}/activities
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ENCRYPTION_KEY` | Yes | Fernet key for encrypting bot secrets at rest. Generate with: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Key Files

| File | Purpose |
|------|---------|
| `app/utils/encryption.py` | `EncryptedString` TypeDecorator — applied to `slack_bot_token` and `teams_app_secret` |
| `app/services/teams_service.py` | Token helpers, user resolution, DM sending, Adaptive Card builders |
| `app/services/report_scheduler.py` | APScheduler jobs — includes Teams jobs alongside Slack jobs |
| `app/crud/team_crud.py` | `update_teams_credentials()` |
| `app/crud/user_crud.py` | `update_teams_user_id()` |

### Running Tests

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py tests/test_encryption.py -v
```

### Known Limitations

- **Regional tenants (GCC, Government, Europe-specific):** The Bot Framework service URL `smba.trafficmanager.net` is hardcoded to the global Teams endpoint. Tenants in GCC or sovereign clouds may need a different service URL. This is a v1 limitation — contact your administrator to verify the correct service URL for your tenant.
- **ENCRYPTION_KEY rotation:** Rotating the Fernet key requires re-saving all bot credentials via the API after the key change, as old ciphertext cannot be decrypted with the new key.
```

- [ ] **Step 3: Commit**

```bash
git add teams-app-manifest.json docs/teams-integration.md
git commit -m "docs: add Teams app manifest and user/developer integration guide"
```

---

## Task 15: Final Verification

- [ ] **Step 1: Run the complete test suite**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
pytest tests/teams_tests.py tests/test_encryption.py tests/slack_tests.py -v
```

Expected: all pass, 0 failed.

- [ ] **Step 2: Run linter (follow `docs/code_conventions.md`)**

- [ ] **Step 3: Verify scheduler jobs registered**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
python3 -c "
from app.services.report_scheduler import create_scheduler
s = create_scheduler()
jobs = {j.id for j in s.get_jobs()}
assert 'weekly_teams_report' in jobs, 'Missing weekly_teams_report job'
assert 'weekly_teams_reminder' in jobs, 'Missing weekly_teams_reminder job'
assert 'weekly_slack_report' in jobs, 'Slack report job missing'
assert 'weekly_slack_reminder' in jobs, 'Slack reminder job missing'
print('All 4 scheduler jobs registered correctly.')
"
```

- [ ] **Step 4: Final commit (if any cleanup needed)**

```bash
git add -p  # stage any remaining files
git commit -m "chore: finalize Teams integration"
```
```
