import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from fastapi.testclient import TestClient

from app.main import app
from app.models.user_model import UserInDB
from app.models.reports_model import EmojiDistributionReport, EmojiDistribution
from app.utils.constants import Role
from app.routers.authentication import create_access_token
from app.services.slack_service import (
    build_weekly_report_blocks,
    build_no_data_blocks,
    send_slack_report,
    _classify_alert,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

client = TestClient(app)

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

mock_orm_team = MagicMock()
mock_orm_team.id = 1
mock_orm_team.name = "Alpha"
mock_orm_team.manager_id = 1
mock_orm_team.slack_webhook_url = "https://hooks.slack.com/test"

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
        {"emotion_name": "Stressed", "avg_intensity": 4.2},
    ],
    "negative_emotion_ratio": 28.6,
    "alert": None,
}

SAMPLE_ANON_REPORT = {
    "user_name": "Anonymous",
    "all_user_emotion_records": [
        {"emotion_name": "Anxious", "frequency": 2, "avg_intensity": 3.0},
    ],
}

# ---------------------------------------------------------------------------
# API: PUT /teams/{team_id}/slack-webhook
# ---------------------------------------------------------------------------

def test_manager_can_set_slack_webhook():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict), \
         patch("app.routers.team_router.team_crud.update_slack_webhook", return_value=mock_orm_team):
        response = client.put(
            "/teams/1/slack-webhook",
            json={"slack_webhook_url": "https://hooks.slack.com/test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["slack_webhook_url"] == "https://hooks.slack.com/test"


def test_employee_cannot_set_slack_webhook():
    token = create_access_token({"sub": employee_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict):
        response = client.put(
            "/teams/1/slack-webhook",
            json={"slack_webhook_url": "https://hooks.slack.com/test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_set_slack_webhook_team_not_found():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=None):
        response = client.put(
            "/teams/99/slack-webhook",
            json={"slack_webhook_url": "https://hooks.slack.com/test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# API: DELETE /teams/{team_id}/slack-webhook
# ---------------------------------------------------------------------------

def test_manager_can_remove_slack_webhook():
    token = create_access_token({"sub": manager_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict), \
         patch("app.routers.team_router.team_crud.update_slack_webhook", return_value=None):
        response = client.delete(
            "/teams/1/slack-webhook",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "removed" in response.json()["message"]


def test_employee_cannot_remove_slack_webhook():
    token = create_access_token({"sub": employee_user.email})
    with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team_dict):
        response = client.delete(
            "/teams/1/slack-webhook",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# slack_service: _classify_alert
# ---------------------------------------------------------------------------

def test_classify_alert_critical():
    assert _classify_alert(51.0) == "critical"

def test_classify_alert_warning():
    assert _classify_alert(35.0) == "warning"

def test_classify_alert_note():
    assert _classify_alert(20.0) == "note"

def test_classify_alert_ok():
    assert _classify_alert(10.0) == "ok"

def test_classify_alert_boundary_critical():
    assert _classify_alert(50.0) == "warning"  # > 50 is critical, exactly 50 is warning

def test_classify_alert_boundary_ok():
    assert _classify_alert(15.0) == "ok"  # > 15 is note, exactly 15 is ok


# ---------------------------------------------------------------------------
# slack_service: build_weekly_report_blocks
# ---------------------------------------------------------------------------

def test_build_weekly_report_blocks_has_header():
    blocks = build_weekly_report_blocks(
        "Alpha", "2026-04-04", "2026-04-11",
        SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
    )
    headers = [b for b in blocks if b["type"] == "header"]
    assert len(headers) == 1
    assert "Alpha" in headers[0]["text"]["text"]


def test_build_weekly_report_blocks_has_anonymity_footer():
    blocks = build_weekly_report_blocks(
        "Alpha", "2026-04-04", "2026-04-11",
        SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
    )
    context_blocks = [b for b in blocks if b["type"] == "context"]
    assert len(context_blocks) == 1
    footer_text = context_blocks[0]["elements"][0]["text"]
    assert "no per-user data" in footer_text


def test_build_weekly_report_blocks_contains_emotion_names():
    blocks = build_weekly_report_blocks(
        "Alpha", "2026-04-04", "2026-04-11",
        SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
    )
    all_text = " ".join(
        str(b.get("text", {}).get("text", "") or
            " ".join(f.get("text", "") for f in b.get("fields", [])))
        for b in blocks
    )
    assert "Happy" in all_text
    assert "Stressed" in all_text


def test_build_weekly_report_blocks_alert_level_shown():
    blocks = build_weekly_report_blocks(
        "Alpha", "2026-04-04", "2026-04-11",
        SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, SAMPLE_ANON_REPORT,
    )
    # negative_ratio=28.6 → "note" (> 15, not > 30)
    section_texts = [
        str(f.get("text", ""))
        for b in blocks if b["type"] == "section"
        for f in b.get("fields", [])
    ]
    assert any("Note" in t for t in section_texts)


def test_build_weekly_report_blocks_no_anonymous_data():
    empty_anon = {"user_name": "Anonymous", "all_user_emotion_records": []}
    blocks = build_weekly_report_blocks(
        "Alpha", "2026-04-04", "2026-04-11",
        SAMPLE_EMOJI_REPORT, SAMPLE_INTENSITY_REPORT, empty_anon,
    )
    section_texts = [
        b.get("text", {}).get("text", "")
        for b in blocks if b["type"] == "section"
    ]
    assert any("No anonymous submissions" in t for t in section_texts)


# ---------------------------------------------------------------------------
# slack_service: build_no_data_blocks
# ---------------------------------------------------------------------------

def test_build_no_data_blocks_structure():
    blocks = build_no_data_blocks("Alpha", "2026-04-04", "2026-04-11")
    assert blocks[0]["type"] == "header"
    assert "Alpha" in blocks[0]["text"]["text"]
    body_text = blocks[1]["text"]["text"]
    assert "No emotion records" in body_text


# ---------------------------------------------------------------------------
# slack_service: send_slack_report (async)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_slack_report_success():
    mock_response = MagicMock(status_code=200, text="ok")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.slack_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_slack_report("https://hooks.slack.com/test", [])

    assert result is True


@pytest.mark.asyncio
async def test_send_slack_report_slack_error_response():
    mock_response = MagicMock(status_code=400, text="invalid_payload")
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.services.slack_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_slack_report("https://hooks.slack.com/test", [])

    assert result is False


@pytest.mark.asyncio
async def test_send_slack_report_timeout():
    import httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("app.services.slack_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_slack_report("https://hooks.slack.com/test", [])

    assert result is False


@pytest.mark.asyncio
async def test_send_slack_report_network_error():
    import httpx
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("connection refused"))

    with patch("app.services.slack_service.httpx.AsyncClient", return_value=mock_client):
        result = await send_slack_report("https://hooks.slack.com/test", [])

    assert result is False


# ---------------------------------------------------------------------------
# report_scheduler: send_weekly_reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scheduler_skips_team_without_webhook():
    team_no_webhook = MagicMock(id=1, name="NoWebhook", slack_webhook_url=None)

    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team_no_webhook]), \
         patch("app.services.report_scheduler.send_slack_report", new_callable=AsyncMock) as mock_send:
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session_cls.return_value.close = MagicMock()

        from app.services.report_scheduler import send_weekly_reports
        await send_weekly_reports()

    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_scheduler_sends_report_for_team_with_webhook():
    team_with_webhook = MagicMock(
        id=1, name="Alpha", slack_webhook_url="https://hooks.slack.com/test"
    )

    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team_with_webhook]), \
         patch("app.services.report_scheduler.reports_crud.get_emoji_distribution_report", return_value=SAMPLE_EMOJI_REPORT), \
         patch("app.services.report_scheduler.reports_crud.get_average_intensity_report", return_value=SAMPLE_INTENSITY_REPORT), \
         patch("app.services.report_scheduler.reports_crud.get_anonymous_emotion_analysis", return_value=SAMPLE_ANON_REPORT), \
         patch("app.services.report_scheduler.send_slack_report", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()

        from app.services.report_scheduler import send_weekly_reports
        await send_weekly_reports()

    mock_send.assert_called_once()
    call_url = mock_send.call_args[0][0]
    assert call_url == "https://hooks.slack.com/test"


@pytest.mark.asyncio
async def test_scheduler_sends_no_data_message_when_empty():
    team_with_webhook = MagicMock(
        id=1, name="Alpha", slack_webhook_url="https://hooks.slack.com/test"
    )
    empty_report = EmojiDistributionReport(
        emoji_distribution=[], negative_emotion_ratio=0.0, alert=None
    )

    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team_with_webhook]), \
         patch("app.services.report_scheduler.reports_crud.get_emoji_distribution_report", return_value=empty_report), \
         patch("app.services.report_scheduler.reports_crud.get_average_intensity_report", return_value={}), \
         patch("app.services.report_scheduler.reports_crud.get_anonymous_emotion_analysis", return_value={}), \
         patch("app.services.report_scheduler.send_slack_report", new_callable=AsyncMock, return_value=True) as mock_send, \
         patch("app.services.report_scheduler.build_no_data_blocks", return_value=[{"type": "header"}]) as mock_no_data:
        mock_session_cls.return_value.close = MagicMock()

        from app.services.report_scheduler import send_weekly_reports
        await send_weekly_reports()

    mock_no_data.assert_called_once()
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_scheduler_continues_after_per_team_error():
    team_broken = MagicMock(id=1, name="Broken", slack_webhook_url="https://hooks.slack.com/a")
    team_ok = MagicMock(id=2, name="OK", slack_webhook_url="https://hooks.slack.com/b")

    with patch("app.services.report_scheduler.SessionLocal") as mock_session_cls, \
         patch("app.services.report_scheduler.team_crud.get_all_teams", return_value=[team_broken, team_ok]), \
         patch("app.services.report_scheduler.reports_crud.get_emoji_distribution_report",
               side_effect=[Exception("DB error"), SAMPLE_EMOJI_REPORT]), \
         patch("app.services.report_scheduler.reports_crud.get_average_intensity_report", return_value=SAMPLE_INTENSITY_REPORT), \
         patch("app.services.report_scheduler.reports_crud.get_anonymous_emotion_analysis", return_value=SAMPLE_ANON_REPORT), \
         patch("app.services.report_scheduler.send_slack_report", new_callable=AsyncMock, return_value=True) as mock_send:
        mock_session_cls.return_value.close = MagicMock()

        from app.services.report_scheduler import send_weekly_reports
        await send_weekly_reports()

    # Only team_ok should have triggered send_slack_report
    assert mock_send.call_count == 1
    assert mock_send.call_args[0][0] == "https://hooks.slack.com/b"


def test_team_schema_has_slack_bot_token_not_webhook():
    from app.schemas.team_schema import Team as TeamSchema
    assert hasattr(TeamSchema, "slack_bot_token")
    assert not hasattr(TeamSchema, "slack_webhook_url")


def test_user_schema_has_slack_user_id():
    from app.schemas.user_schema import User as UserSchema
    assert hasattr(UserSchema, "slack_user_id")
