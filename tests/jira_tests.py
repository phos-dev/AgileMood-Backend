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


# ---- connect ----

def test_manager_can_connect_jira():
    import datetime
    updated = MagicMock(
        id=1, manager_id=1,
        created_at=datetime.datetime.now(),
        teams_tenant_id=None,
        jira_cloud_id="cloud-abc",
    )
    updated.name = "Team A"
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.jira_router.team_crud.update_jira_credentials", return_value=updated):
        resp = client.post(
            "/integrations/jira/connect?team_id=1",
            json={"jira_token": "tok", "jira_cloud_id": "cloud-abc"},
            headers={"Authorization": f"Bearer {_manager_token()}"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "jira_token" not in data
    assert data["jira_cloud_id"] == "cloud-abc"


def test_employee_cannot_connect_jira():
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team):
        resp = client.post(
            "/integrations/jira/connect?team_id=1",
            json={"jira_token": "tok", "jira_cloud_id": "cloud-abc"},
            headers={"Authorization": f"Bearer {_employee_token()}"},
        )
    assert resp.status_code == 403


def test_connect_team_not_found():
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=None):
        resp = client.post(
            "/integrations/jira/connect?team_id=999",
            json={"jira_token": "tok", "jira_cloud_id": "cloud"},
            headers={"Authorization": f"Bearer {_manager_token()}"},
        )
    assert resp.status_code == 404


# ---- disconnect ----

def test_manager_can_disconnect_jira():
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.jira_router.team_crud.update_jira_credentials") as mock_update:
        resp = client.delete(
            "/integrations/jira/disconnect?team_id=1",
            headers={"Authorization": f"Bearer {_manager_token()}"},
        )
    assert resp.status_code == 200
    mock_update.assert_called_once()
    call_args = mock_update.call_args[0]
    assert call_args[1] == 1       # team_id
    assert call_args[2] is None    # token cleared
    assert call_args[3] is None    # cloud_id cleared


def test_employee_cannot_disconnect_jira():
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team):
        resp = client.delete(
            "/integrations/jira/disconnect?team_id=1",
            headers={"Authorization": f"Bearer {_employee_token()}"},
        )
    assert resp.status_code == 403


# ---- webhook ----

_SPRINT_CLOSED = {
    "webhookEvent": "jira:sprint_closed",
    "sprint": {"id": 42, "name": "Sprint 3", "state": "closed"},
}


def test_webhook_triggers_on_sprint_closed():
    body = json.dumps(_SPRINT_CLOSED).encode()
    with patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.jira_router.send_sprint_end_reminder", new_callable=AsyncMock) as mock_fn:
        resp = client.post(
            "/webhooks/jira/sprint-end?team_id=1",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    assert "queued" in resp.json()["message"].lower()
    mock_fn.assert_called_once_with(1)


def test_webhook_ignores_other_events():
    body = json.dumps({"webhookEvent": "jira:issue_created", "issue": {"id": "10001"}}).encode()
    with patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team):
        resp = client.post(
            "/webhooks/jira/sprint-end?team_id=1",
            content=body,
            headers={"Content-Type": "application/json"},
        )
    assert resp.status_code == 200
    assert "ignored" in resp.json()["message"].lower()


def test_webhook_404_when_no_jira_token():
    no_token_data = MagicMock(id=1, manager_id=1, jira_token=None, jira_cloud_id=None)
    no_token_team = {**mock_team, "team_data": no_token_data}
    body = json.dumps(_SPRINT_CLOSED).encode()
    with patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=no_token_team):
        resp = client.post("/webhooks/jira/sprint-end?team_id=1", content=body)
    assert resp.status_code == 404


def test_webhook_404_team_not_found():
    body = json.dumps(_SPRINT_CLOSED).encode()
    with patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=None):
        resp = client.post("/webhooks/jira/sprint-end?team_id=999", content=body)
    assert resp.status_code == 404


def test_webhook_rejects_invalid_signature():
    body = json.dumps(_SPRINT_CLOSED).encode()
    with patch.dict("os.environ", {"JIRA_WEBHOOK_SECRET": "mysecret"}), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team):
        resp = client.post(
            "/webhooks/jira/sprint-end?team_id=1",
            content=body,
            headers={"X-Jira-Signature": "sha256=invalidsignature"},
        )
    assert resp.status_code == 401


def test_webhook_accepts_valid_signature():
    body = json.dumps(_SPRINT_CLOSED).encode()
    sig = _jira_sig("mysecret", body)
    with patch.dict("os.environ", {"JIRA_WEBHOOK_SECRET": "mysecret"}), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.jira_router.send_sprint_end_reminder", new_callable=AsyncMock):
        resp = client.post(
            "/webhooks/jira/sprint-end?team_id=1",
            content=body,
            headers={"X-Jira-Signature": sig},
        )
    assert resp.status_code == 200


def test_webhook_deduplicates_same_sprint_id():
    body = json.dumps(_SPRINT_CLOSED).encode()
    with patch.dict("app.routers.jira_router._SEEN_SPRINT_IDS", {"42": time.time()}), \
         patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.jira_router.send_sprint_end_reminder", new_callable=AsyncMock) as mock_fn:
        resp = client.post(
            "/webhooks/jira/sprint-end?team_id=1",
            content=body,
        )
    assert resp.status_code == 200
    assert "duplicate" in resp.json()["message"].lower()
    mock_fn.assert_not_called()
