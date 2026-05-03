import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# ---- API endpoint tests ----
from fastapi.testclient import TestClient
from app.main import app
from app.models.user_model import UserInDB
from app.utils.constants import Role
from app.routers.authentication import create_access_token

client = TestClient(app, follow_redirects=False)

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


def test_teams_connect_redirects_to_microsoft():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict), \
         patch.dict(os.environ, {"TEAMS_APP_ID": "my-app-id", "TEAMS_REDIRECT_URI": "https://example.com/callback"}):
        response = client.get(
            "/teams/1/teams-connect",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 307
    assert "login.microsoftonline.com" in response.headers["location"]
    assert "my-app-id" in response.headers["location"]


def test_teams_connect_manager_only():
    token = create_access_token({"sub": employee_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict):
        response = client.get(
            "/teams/1/teams-connect",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_teams_callback_stores_tenant_id():
    mock_team = MagicMock(id=1, teams_tenant_id="tenant-xyz")
    with patch("app.routers.auth_router.team_crud.update_teams_tenant_id", return_value=mock_team), \
         patch.dict(os.environ, {"FRONTEND_URL": "https://frontend.example.com"}):
        response = client.get("/auth/teams/callback?tenant=tenant-xyz&state=1")
    assert response.status_code == 307
    assert "teams_connected=true" in response.headers["location"]


def test_teams_disconnect_clears_tenant_id():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict), \
         patch("app.routers.team_router.team_crud.update_teams_tenant_id", return_value=MagicMock()):
        response = client.delete(
            "/teams/1/teams-credentials",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "disconnected" in response.json()["message"]


def test_teams_user_id_put_manager_only():
    token = create_access_token({"sub": employee_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user):
        response = client.put(
            "/user/2/teams-user-id",
            json={"teams_user_id": "aad-id-123"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_teams_user_id_delete():
    token = create_access_token({"sub": manager_user.email})
    mock_user_result = MagicMock()
    mock_user_result.id = 2
    mock_user_result.name = "Employee"
    mock_user_result.email = "employee@example.com"
    mock_user_result.role = "employee"
    mock_user_result.disabled = False
    mock_user_result.hashed_password = "x"
    mock_user_result.avatar = None
    mock_user_result.slack_user_id = None
    mock_user_result.teams_user_id = None
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.user_router.user_crud.get_user_by_id", return_value=employee_user), \
         patch("app.routers.user_router.user_crud.update_teams_user_id", return_value=mock_user_result):
        response = client.delete(
            "/user/2/teams-user-id",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "removed" in response.json()["message"]

# -- _classify_alert --
from app.services.teams_service import _classify_alert

def test_teams_classify_alert_critical():
    assert _classify_alert(51.0) == "critical"

def test_teams_classify_alert_warning():
    assert _classify_alert(35.0) == "warning"

def test_teams_classify_alert_note():
    assert _classify_alert(20.0) == "note"

def test_teams_classify_alert_ok():
    assert _classify_alert(10.0) == "ok"

# -- Card builders --
from app.services.teams_service import (
    build_weekly_report_card,
    build_no_data_card,
    build_reminder_card,
    build_unreachable_notification_card,
)
from app.models.reports_model import EmojiDistributionReport, EmojiDistribution

SAMPLE_EMOJI_REPORT = EmojiDistributionReport(
    emoji_distribution=[
        EmojiDistribution(emotion_name="Happy", frequency=10),
        EmojiDistribution(emotion_name="Stressed", frequency=4),
    ],
    negative_emotion_ratio=28.6,
    alert=None,
)
SAMPLE_INTENSITY_REPORT = {
    "average_intensity": [
        {"emotion_name": "Happy", "avg_intensity": 3.5},
    ],
    "negative_emotion_ratio": 28.6,
    "alert": None,
}
SAMPLE_ANON_REPORT = {
    "user_name": "Anonymous",
    "all_user_emotion_records": [{"emotion_name": "Anxious", "frequency": 2, "avg_intensity": 3.0}],
}

def test_build_weekly_report_card_has_body():
    card = build_weekly_report_card("Alpha", "2026-04-04", "2026-04-11",
                                    SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT)
    assert card["type"] == "AdaptiveCard"
    body = card["body"]
    all_text = " ".join(str(b) for b in body)
    assert "Alpha" in all_text

def test_build_weekly_report_card_has_privacy_footer():
    card = build_weekly_report_card("Alpha", "2026-04-04", "2026-04-11",
                                    SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT)
    all_text = str(card)
    assert "não contém dados individuais" in all_text

def test_build_weekly_report_card_shows_emotion_names():
    card = build_weekly_report_card("Alpha", "2026-04-04", "2026-04-11",
                                    SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT)
    assert "Happy" in str(card)
    assert "Stressed" in str(card)

def test_build_weekly_report_card_shows_alert_level():
    card = build_weekly_report_card("Alpha", "2026-04-04", "2026-04-11",
                                    SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT)
    # ratio=28.6 → "note" → Observação
    assert "Observação" in str(card)

def test_build_no_data_card_structure():
    card = build_no_data_card("Alpha", "2026-04-04", "2026-04-11")
    assert card["type"] == "AdaptiveCard"
    assert "Alpha" in str(card)
    assert "Nenhum registro" in str(card)

def test_build_reminder_card_has_message():
    card = build_reminder_card()
    assert card["type"] == "AdaptiveCard"
    assert "AgileMood" in str(card)

def test_build_unreachable_notification_card():
    card = build_unreachable_notification_card(["a@b.com", "c@d.com"])
    assert "a@b.com" in str(card)
    assert "c@d.com" in str(card)

def test_build_weekly_report_card_no_anonymous_data():
    empty_anon = {"user_name": "Anonymous", "all_user_emotion_records": []}
    card = build_weekly_report_card("Alpha", "2026-04-04", "2026-04-11",
                                    SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, empty_anon)
    assert "Nenhum registro anônimo" in str(card)

# -- Token helpers --
@pytest.mark.asyncio
async def test_get_graph_token_success():
    from app.services.teams_service import get_graph_token
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": "graph-token-123"}
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        token = await get_graph_token("tenant-123")
    assert token == "graph-token-123"

@pytest.mark.asyncio
async def test_get_graph_token_failure():
    import httpx
    from app.services.teams_service import get_graph_token
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("fail"))
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception):
            await get_graph_token("tenant-123")

@pytest.mark.asyncio
async def test_get_bot_token_success():
    from app.services.teams_service import get_bot_token
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": "bot-token-456"}
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        token = await get_bot_token()
    assert token == "bot-token-456"

@pytest.mark.asyncio
async def test_get_bot_token_failure():
    import httpx
    from app.services.teams_service import get_bot_token
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("fail"))
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception):
            await get_bot_token()

# -- resolve_teams_user --
@pytest.mark.asyncio
async def test_resolve_teams_user_by_email():
    from app.services.teams_service import resolve_teams_user
    mock_user = MagicMock(email="a@b.com", teams_user_id=None)
    graph_resp = MagicMock()
    graph_resp.json.return_value = {"id": "aad-object-id-123"}
    graph_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=MagicMock(json=MagicMock(return_value={"access_token": "g-tok"}), raise_for_status=MagicMock()))
    mock_client.get = AsyncMock(return_value=graph_resp)
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_teams_user("tenant-abc", mock_user)
    assert result == "aad-object-id-123"

@pytest.mark.asyncio
async def test_resolve_teams_user_fallback_to_override():
    from app.services.teams_service import resolve_teams_user
    mock_user = MagicMock(email="a@b.com", teams_user_id="manual-aad-id")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("graph fail"))
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_teams_user("tenant-abc", mock_user)
    assert result == "manual-aad-id"

@pytest.mark.asyncio
async def test_resolve_teams_user_unresolvable():
    from app.services.teams_service import resolve_teams_user
    mock_user = MagicMock(email="a@b.com", teams_user_id=None)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=Exception("graph fail"))
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_teams_user("tenant-abc", mock_user)
    assert result is None

@pytest.mark.asyncio
async def test_resolve_teams_user_graph_error():
    from app.services.teams_service import resolve_teams_user
    mock_user = MagicMock(email="a@b.com", teams_user_id=None)
    graph_resp = MagicMock()
    graph_resp.raise_for_status = MagicMock(side_effect=Exception("404"))
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=MagicMock(json=MagicMock(return_value={"access_token": "g-tok"}), raise_for_status=MagicMock()))
    mock_client.get = AsyncMock(return_value=graph_resp)
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id", "TEAMS_APP_SECRET": "app-secret"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await resolve_teams_user("tenant-abc", mock_user)
    assert result is None

# -- send_dm --
@pytest.mark.asyncio
async def test_send_dm_success():
    from app.services.teams_service import send_dm
    conv_resp = MagicMock()
    conv_resp.json.return_value = {"id": "conv-id-123"}
    conv_resp.raise_for_status = MagicMock()
    act_resp = MagicMock()
    act_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=[conv_resp, act_resp])
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_dm("bot-token", "tenant-id", "aad-user-id", {"type": "AdaptiveCard"})
    assert result is True

@pytest.mark.asyncio
async def test_send_dm_api_error():
    from app.services.teams_service import send_dm
    conv_resp = MagicMock()
    conv_resp.raise_for_status = MagicMock(side_effect=Exception("403 Forbidden"))
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=conv_resp)
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_dm("bot-token", "tenant-id", "aad-user-id", {"type": "AdaptiveCard"})
    assert result is False

@pytest.mark.asyncio
async def test_send_dm_timeout():
    import httpx
    from app.services.teams_service import send_dm
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_dm("bot-token", "tenant-id", "aad-user-id", {"type": "AdaptiveCard"})
    assert result is False

@pytest.mark.asyncio
async def test_send_dm_network_error():
    import httpx
    from app.services.teams_service import send_dm
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("network error"))
    with patch.dict(os.environ, {"TEAMS_APP_ID": "app-id"}), \
         patch("app.services.teams_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_dm("bot-token", "tenant-id", "aad-user-id", {"type": "AdaptiveCard"})
    assert result is False
