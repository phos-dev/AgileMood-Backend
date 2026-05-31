from unittest.mock import AsyncMock, patch
from tests.conftest import client


def test_planner_subscription_id_persists_to_db(team, manager_token, db):
    """After subscribe endpoint succeeds, planner_subscription_id must be stored in DB."""
    team.teams_tenant_id = "tenant-xyz"
    db.commit()

    with patch("app.routers.planner_router.create_graph_subscription", new_callable=AsyncMock, return_value="sub-new-123"):
        resp = client.post(
            f"/integrations/planner/subscribe?team_id={team.id}",
            json={"plan_id": "plan-abc"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
    # Route doesn't exist yet → 404 (RED)
    assert resp.status_code == 200  # will fail — route missing
    db.refresh(team)
    assert team.planner_subscription_id == "sub-new-123"


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def test_create_graph_subscription_calls_graph_api_and_returns_id():
    from app.services.planner_service import create_graph_subscription
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "sub-xyz-456"}
    mock_resp.raise_for_status = MagicMock()

    with patch("app.services.planner_service.get_graph_token", return_value="graph-token"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
        result = asyncio.get_event_loop().run_until_complete(
            create_graph_subscription("tenant-1", 5, "plan-abc")
        )
    assert result == "sub-xyz-456"


def test_renew_graph_subscription_returns_true_on_success():
    from app.services.planner_service import renew_graph_subscription
    mock_resp = MagicMock(raise_for_status=MagicMock())

    with patch("app.services.planner_service.get_graph_token", return_value="token"), \
         patch("httpx.AsyncClient.patch", new_callable=AsyncMock, return_value=mock_resp):
        result = asyncio.get_event_loop().run_until_complete(
            renew_graph_subscription("tenant-1", "sub-abc")
        )
    assert result is True


def test_renew_graph_subscription_returns_false_on_error():
    from app.services.planner_service import renew_graph_subscription

    with patch("app.services.planner_service.get_graph_token", side_effect=Exception("auth error")):
        result = asyncio.get_event_loop().run_until_complete(
            renew_graph_subscription("tenant-1", "sub-abc")
        )
    assert result is False


def test_delete_graph_subscription_returns_true_on_success():
    from app.services.planner_service import delete_graph_subscription
    mock_resp = MagicMock(raise_for_status=MagicMock())

    with patch("app.services.planner_service.get_graph_token", return_value="token"), \
         patch("httpx.AsyncClient.delete", new_callable=AsyncMock, return_value=mock_resp):
        result = asyncio.get_event_loop().run_until_complete(
            delete_graph_subscription("tenant-1", "sub-abc")
        )
    assert result is True


def test_webhook_triggers_rf01_and_teams_dm_sent(team_with_tenant, manager, db):
    """Full RF01 flow: POST notification → send_sprint_end_reminder_teams → Teams DM."""
    # Add manager as team member so they receive the DM
    from app.schemas.team_schema import user_teams
    db.execute(
        user_teams.insert().values(user_id=manager.id, team_id=team_with_tenant.id)
    )
    db.commit()

    notification_body = {
        "value": [{
            "clientState": "planner-secret-changeme",
            "resourceData": {"percentComplete": 100},
        }]
    }

    with patch("app.routers.planner_router.PLANNER_WEBHOOK_SECRET", "planner-secret-changeme"), \
         patch("app.services.report_scheduler.get_bot_token", new_callable=AsyncMock, return_value="bot-tok"), \
         patch("app.services.report_scheduler.resolve_teams_user", new_callable=AsyncMock, return_value="aad-id-123"), \
         patch("app.services.report_scheduler.teams_send_dm", new_callable=AsyncMock, return_value=True) as mock_dm:
        resp = client.post(
            f"/webhooks/planner/plan-completed?team_id={team_with_tenant.id}",
            json=notification_body,
        )

    assert resp.status_code == 202
    mock_dm.assert_called_once()
    call_args = mock_dm.call_args[0]
    assert call_args[2] == "aad-id-123"  # teams_user_id resolved

    # Cleanup member
    db.execute(
        user_teams.delete().where(
            (user_teams.c.user_id == manager.id) & (user_teams.c.team_id == team_with_tenant.id)
        )
    )
    db.commit()
