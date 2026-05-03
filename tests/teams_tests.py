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

# ---- Scheduler tests ----
@pytest.mark.asyncio
async def test_teams_scheduler_skips_team_without_tenant_id():
    from app.services.report_scheduler import send_weekly_teams_reports
    team_no_tenant = MagicMock(id=1, name="NoTenant", teams_tenant_id=None, members=[], manager=MagicMock())
    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team_no_tenant]), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock) as mock_send:
        mock_session_cls.return_value.close = MagicMock()
        await send_weekly_teams_reports()
    mock_send.assert_not_called()

@pytest.mark.asyncio
async def test_teams_scheduler_sends_weekly_report():
    from app.services.report_scheduler import send_weekly_teams_reports
    from app.models.reports_model import EmojiDistributionReport, EmojiDistribution
    manager_mock = MagicMock(email="mgr@test.com", teams_user_id=None)
    team = MagicMock(id=1, name="Alpha", teams_tenant_id="tenant-xyz", manager=manager_mock, members=[])
    emoji_report = EmojiDistributionReport(
        emoji_distribution=[EmojiDistribution(emotion_name="Happy", frequency=5)],
        negative_emotion_ratio=10.0, alert=None,
    )
    intensity_report = {"average_intensity": []}
    anon_report = {"all_user_emotion_records": []}
    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team]), \
         patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="aad-mgr-id"), \
         patch("app.services.report_scheduler.reports_crud.get_emoji_distribution_report", return_value=emoji_report), \
         patch("app.services.report_scheduler.reports_crud.get_average_intensity_report", return_value=intensity_report), \
         patch("app.services.report_scheduler.reports_crud.get_anonymous_emotion_analysis", return_value=anon_report), \
         patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()
        await send_weekly_teams_reports()
    mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_teams_scheduler_sends_no_data_card():
    from app.services.report_scheduler import send_weekly_teams_reports
    from app.models.reports_model import EmojiDistributionReport
    manager_mock = MagicMock(email="mgr@test.com", teams_user_id=None)
    team = MagicMock(id=1, name="Alpha", teams_tenant_id="tenant-xyz", manager=manager_mock, members=[])
    empty_report = EmojiDistributionReport(emoji_distribution=[], negative_emotion_ratio=0.0, alert=None)
    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team]), \
         patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="aad-mgr-id"), \
         patch("app.services.report_scheduler.reports_crud.get_emoji_distribution_report", return_value=empty_report), \
         patch("app.services.report_scheduler.reports_crud.get_average_intensity_report", return_value={}), \
         patch("app.services.report_scheduler.reports_crud.get_anonymous_emotion_analysis", return_value={}), \
         patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()
        await send_weekly_teams_reports()
    mock_send.assert_called_once()
    # The card should contain "Nenhum registro"
    sent_card = mock_send.call_args[0][3]
    assert "Nenhum registro" in str(sent_card)

@pytest.mark.asyncio
async def test_teams_scheduler_sends_reminders():
    from app.services.report_scheduler import send_weekly_teams_reminders
    member_mock = MagicMock(email="emp@test.com", teams_user_id=None)
    team = MagicMock(id=1, name="Alpha", teams_tenant_id="tenant-xyz",
                     manager=MagicMock(email="mgr@test.com", teams_user_id=None), members=[member_mock])
    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team]), \
         patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="aad-emp-id"), \
         patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()
        await send_weekly_teams_reminders()
    mock_send.assert_called_once()

@pytest.mark.asyncio
async def test_teams_scheduler_notifies_manager_of_unreachable():
    from app.services.report_scheduler import send_weekly_teams_reminders
    member_mock = MagicMock(email="emp@test.com", teams_user_id=None)
    manager_mock = MagicMock(email="mgr@test.com", teams_user_id=None)
    team = MagicMock(id=1, name="Alpha", teams_tenant_id="tenant-xyz",
                     manager=manager_mock, members=[member_mock])
    async def resolve_side(tenant_id, user):
        if user is manager_mock:
            return "aad-mgr-id"
        return None
    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team]), \
         patch("app.services.report_scheduler.resolve_teams_user", side_effect=resolve_side), \
         patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()
        await send_weekly_teams_reminders()
    mock_send.assert_called_once()
    assert mock_send.call_args[0][2] == "aad-mgr-id"

@pytest.mark.asyncio
async def test_teams_scheduler_isolates_per_team_errors():
    from app.services.report_scheduler import send_weekly_teams_reports
    from app.models.reports_model import EmojiDistributionReport, EmojiDistribution
    manager_mock = MagicMock(email="mgr@test.com", teams_user_id=None)
    team_broken = MagicMock(id=1, name="Broken", teams_tenant_id="tenant-a", manager=manager_mock, members=[])
    team_ok = MagicMock(id=2, name="OK", teams_tenant_id="tenant-b", manager=manager_mock, members=[])
    emoji_report = EmojiDistributionReport(
        emoji_distribution=[EmojiDistribution(emotion_name="Happy", frequency=5)],
        negative_emotion_ratio=10.0, alert=None,
    )
    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team_broken, team_ok]), \
         patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="aad-mgr-id"), \
         patch("app.services.report_scheduler.reports_crud.get_emoji_distribution_report",
               side_effect=[Exception("DB error"), emoji_report]), \
         patch("app.services.report_scheduler.reports_crud.get_average_intensity_report", return_value={}), \
         patch("app.services.report_scheduler.reports_crud.get_anonymous_emotion_analysis", return_value={"all_user_emotion_records": []}), \
         patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()
        await send_weekly_teams_reports()
    assert mock_send.call_count == 1
