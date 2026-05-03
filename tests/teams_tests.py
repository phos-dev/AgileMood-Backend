import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

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
