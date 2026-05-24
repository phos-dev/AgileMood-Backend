import base64
import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.user_model import UserInDB
from app.routers.authentication import create_access_token
from app.utils.constants import Role

client = TestClient(app)

manager_user = UserInDB(
    id=1, name="Manager", email="manager@example.com",
    disabled=False, role=Role.MANAGER, hashed_password="x"
)
employee_user = UserInDB(
    id=2, name="Employee", email="employee@example.com",
    disabled=False, role=Role.EMPLOYEE, hashed_password="x"
)

_mock_team_data = MagicMock(id=1, manager_id=1, slack_bot_token="xoxb-test", trello_token="trello-tok")
_mock_team_data.name = "Test Team"
_mock_team_no_trello = MagicMock(id=1, manager_id=1, slack_bot_token=None, trello_token=None)
_mock_team_no_trello.name = "No Trello Team"

mock_team = {
    "team_data": _mock_team_data,
    "members": [],
    "emotions_reports": [],
    "manager": MagicMock(id=1, email="manager@example.com"),
}
mock_team_no_trello = {
    "team_data": _mock_team_no_trello,
    "members": [],
    "emotions_reports": [],
    "manager": MagicMock(id=1, email="manager@example.com"),
}

_updated_team = MagicMock(id=1, manager_id=1, slack_bot_token=None, teams_tenant_id=None, trello_token="trello-tok")
_updated_team.name = "Test Team"


# --- POST /integrations/trello/connect ---

def test_manager_can_connect_trello():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.team_crud.update_trello_token", return_value=_updated_team):
        response = client.post(
            "/integrations/trello/connect?team_id=1",
            json={"trello_token": "trello-tok"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "trello_token" not in response.json()  # tokens excluded from response


def test_employee_cannot_connect_trello():
    token = create_access_token({"sub": employee_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team):
        response = client.post(
            "/integrations/trello/connect?team_id=1",
            json={"trello_token": "trello-tok"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_connect_team_not_found():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=None):
        response = client.post(
            "/integrations/trello/connect?team_id=99",
            json={"trello_token": "trello-tok"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404


# --- DELETE /integrations/trello/disconnect ---

def test_manager_can_disconnect_trello():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.team_crud.update_trello_token", return_value=MagicMock(trello_token=None)):
        response = client.delete(
            "/integrations/trello/disconnect?team_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "removed" in response.json()["message"]


def test_employee_cannot_disconnect_trello():
    token = create_access_token({"sub": employee_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team):
        response = client.delete(
            "/integrations/trello/disconnect?team_id=1",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


# --- POST /webhooks/trello/sprint-end ---

def test_webhook_head_returns_200():
    response = client.head("/webhooks/trello/sprint-end?team_id=1")
    assert response.status_code == 200


_SPRINT_END_CARD_MOVED = {
    "action": {
        "type": "updateCard",
        "data": {
            "card": {"name": "Sprint 3 - Fim"},
            "listBefore": {"id": "list-a", "name": "Em andamento"},
            "listAfter":  {"id": "list-b", "name": "Pronto"},
        },
    }
}


def test_webhook_triggers_on_sprint_end_card():
    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.send_sprint_end_reminder", new_callable=AsyncMock) as mock_reminder:
        response = client.post("/webhooks/trello/sprint-end?team_id=1", json=_SPRINT_END_CARD_MOVED)
    assert response.status_code == 200
    assert "triggered" in response.json()["message"]
    mock_reminder.assert_called_once()


def test_webhook_ignores_non_updatecard_event():
    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.send_sprint_end_reminder", new_callable=AsyncMock) as mock_reminder:
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=1",
            json={"action": {"type": "commentCard"}},
        )
    assert response.status_code == 200
    assert response.json()["message"] == "Event ignored."
    mock_reminder.assert_not_called()


def test_webhook_ignores_regular_card_move():
    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.send_sprint_end_reminder", new_callable=AsyncMock) as mock_reminder:
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=1",
            json={"action": {"type": "updateCard", "data": {
                "card": {"name": "Fix login bug"},
                "listBefore": {"id": "list-a", "name": "To Do"},
                "listAfter":  {"id": "list-b", "name": "Done"},
            }}},
        )
    assert response.status_code == 200
    assert response.json()["message"] == "Event ignored."
    mock_reminder.assert_not_called()


def test_webhook_ignores_non_move_update():
    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.send_sprint_end_reminder", new_callable=AsyncMock) as mock_reminder:
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=1",
            json={"action": {"type": "updateCard", "data": {"card": {"name": "Sprint 1 - Fim"}}}},
        )
    assert response.status_code == 200
    assert response.json()["message"] == "Event ignored."
    mock_reminder.assert_not_called()


def test_webhook_404_when_no_trello_token():
    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team_no_trello):
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=1",
            json={"action": {"type": "updateCard"}},
        )
    assert response.status_code == 404


def test_webhook_404_team_not_found():
    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=None):
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=99",
            json={},
        )
    assert response.status_code == 404


def _make_trello_sig(secret: str, body: bytes, callback_url: str) -> str:
    digest = hmac.new(secret.encode(), body + callback_url.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def test_webhook_rejects_invalid_signature():
    """Webhook must return 401 when TRELLO_API_SECRET is set and signature is wrong."""
    with patch.dict("os.environ", {"TRELLO_API_SECRET": "test-secret"}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team):
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=1",
            json={"action": {"type": "updateCard"}},
            headers={"x-trello-webhook": "invalid-sig"},
        )
    assert response.status_code == 401


def test_webhook_accepts_valid_signature():
    """Webhook must succeed when TRELLO_API_SECRET is set and signature is correct."""
    secret = "test-secret"
    body = b'{"action": {"type": "updateCard"}}'
    # TestClient builds URL without query string in the url object used for sig
    # Use the same callback_url format as the handler (str(request.url))
    callback_url = "http://testserver/webhooks/trello/sprint-end?team_id=1"
    sig = _make_trello_sig(secret, body, callback_url)

    with patch.dict("os.environ", {"TRELLO_API_SECRET": secret}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.send_sprint_end_reminder", new_callable=AsyncMock):
        response = client.post(
            "/webhooks/trello/sprint-end?team_id=1",
            content=body,
            headers={
                "Content-Type": "application/json",
                "x-trello-webhook": sig,
            },
        )
    assert response.status_code == 200


def test_webhook_deduplicates_same_action_id():
    """Trello sends the same webhook from multiple servers; second delivery must be ignored."""
    payload = {
        "action": {
            "id": "abc123uniqueactionid",
            "type": "updateCard",
            "data": {
                "card": {"name": "Sprint fim"},
                "listBefore": {"id": "list1"},
                "listAfter": {"id": "list2"},
            },
        }
    }

    with patch.dict("os.environ", {"TRELLO_API_SECRET": ""}), \
         patch("app.routers.trello_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.trello_router.send_sprint_end_reminder", new_callable=AsyncMock), \
         patch("app.routers.trello_router._SEEN_ACTION_IDS", new={}):
        r1 = client.post("/webhooks/trello/sprint-end?team_id=1", json=payload)
        r2 = client.post("/webhooks/trello/sprint-end?team_id=1", json=payload)

    assert r1.status_code == 200
    assert r1.json()["message"] == "Sprint-end reminder triggered."
    assert r2.status_code == 200
    assert r2.json()["message"] == "Duplicate event ignored."
