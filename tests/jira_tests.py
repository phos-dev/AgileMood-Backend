"""Jira integration tests."""
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.user_model import UserInDB
from app.utils.constants import Role
from app.routers.authentication import create_access_token

client = TestClient(app)

# --- shared fixtures ---
manager_user = UserInDB(
    id=1, name="Manager", email="manager@example.com",
    disabled=False, role=Role.MANAGER, hashed_password="x",
)
employee_user = UserInDB(
    id=2, name="Employee", email="employee@example.com",
    disabled=False, role=Role.EMPLOYEE, hashed_password="x",
)

_mock_team_data = MagicMock(
    id=1, manager_id=1, jira_token="jira-tok", jira_cloud_id="cloud-abc"
)
mock_team = {
    "team_data": _mock_team_data,
    "members": [],
    "emotions_reports": [],
    "emotions": [],
    "manager": manager_user,
}


def _manager_token() -> str:
    return create_access_token({"sub": "manager@example.com"})


def _employee_token() -> str:
    return create_access_token({"sub": "employee@example.com"})


def _jira_sig(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return "sha256=" + digest.hex()


# --- CRUD smoke tests ---
def test_update_jira_credentials_sets_fields():
    from app.crud.team_crud import update_jira_credentials

    mock_db = MagicMock()
    fake_team = MagicMock(id=1)
    mock_db.query.return_value.filter.return_value.first.return_value = fake_team

    result = update_jira_credentials(mock_db, 1, "new-tok", "new-cloud")

    assert fake_team.jira_token == "new-tok"
    assert fake_team.jira_cloud_id == "new-cloud"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(fake_team)
    assert result == fake_team


def test_update_jira_credentials_returns_none_when_not_found():
    from app.crud.team_crud import update_jira_credentials

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    result = update_jira_credentials(mock_db, 999, "tok", "cloud")
    assert result is None
