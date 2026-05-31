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


def test_webhook_returns_validation_token():
    resp = client.post(
        "/webhooks/planner/plan-completed?team_id=1&validationToken=hello-world",
        content=b"",
    )
    assert resp.status_code == 200
    assert resp.text == "hello-world"
    assert "text/plain" in resp.headers["content-type"]


def test_webhook_rejects_invalid_client_state(team_with_tenant):
    body = {"value": [{"clientState": "wrong-secret", "resourceData": {"percentComplete": 100}}]}
    with patch("app.routers.planner_router.PLANNER_WEBHOOK_SECRET", "correct-secret"):
        resp = client.post(
            f"/webhooks/planner/plan-completed?team_id={team_with_tenant.id}",
            json=body,
        )
    assert resp.status_code == 401


def test_webhook_ignores_incomplete_task(team_with_tenant):
    body = {
        "value": [{
            "clientState": "planner-secret-changeme",
            "resourceData": {"percentComplete": 50},
        }]
    }
    with patch("app.routers.planner_router.PLANNER_WEBHOOK_SECRET", "planner-secret-changeme"), \
         patch("app.routers.planner_router.send_sprint_end_reminder_teams") as mock_rf01:
        resp = client.post(
            f"/webhooks/planner/plan-completed?team_id={team_with_tenant.id}",
            json=body,
        )
    assert resp.status_code == 202
    mock_rf01.assert_not_called()


def test_subscribe_requires_teams_tenant(team, manager_token, db):
    """Returns 400 when team has no teams_tenant_id."""
    assert team.teams_tenant_id is None
    resp = client.post(
        f"/integrations/planner/subscribe?team_id={team.id}",
        json={"plan_id": "plan-abc"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 400


def test_subscribe_non_manager_forbidden(team_with_tenant, employee, employee_token, db):
    """Returns 403 when employee tries to subscribe."""
    resp = client.post(
        f"/integrations/planner/subscribe?team_id={team_with_tenant.id}",
        json={"plan_id": "plan-abc"},
        headers={"Authorization": f"Bearer {employee_token}"},
    )
    assert resp.status_code == 403


def test_subscribe_creates_subscription_and_persists(team_with_tenant, manager_token, db):
    """Subscribe endpoint: calls Graph API and stores subscription_id in DB."""
    with patch("app.routers.planner_router.create_graph_subscription", new_callable=AsyncMock, return_value="sub-new-789"):
        resp = client.post(
            f"/integrations/planner/subscribe?team_id={team_with_tenant.id}",
            json={"plan_id": "plan-abc"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["subscription_id"] == "sub-new-789"
    # DB reflects the new subscription
    db.refresh(team_with_tenant)
    assert team_with_tenant.planner_subscription_id == "sub-new-789"


def test_renew_returns_404_when_no_subscription(team_with_tenant, manager_token, db):
    assert team_with_tenant.planner_subscription_id is None
    resp = client.post(
        f"/integrations/planner/renew?team_id={team_with_tenant.id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp.status_code == 404


def test_renew_existing_subscription(team_with_tenant, manager_token, db):
    team_with_tenant.planner_subscription_id = "sub-existing"
    db.commit()

    with patch("app.routers.planner_router.renew_graph_subscription", new_callable=AsyncMock, return_value=True):
        resp = client.post(
            f"/integrations/planner/renew?team_id={team_with_tenant.id}",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["renewed"] is True


def test_unsubscribe_clears_subscription_in_db(team_with_tenant, manager_token, db):
    team_with_tenant.planner_subscription_id = "sub-to-remove"
    db.commit()

    with patch("app.routers.planner_router.delete_graph_subscription", new_callable=AsyncMock, return_value=True):
        resp = client.delete(
            f"/integrations/planner/unsubscribe?team_id={team_with_tenant.id}",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
    assert resp.status_code == 200
    # DB cleared
    db.refresh(team_with_tenant)
    assert team_with_tenant.planner_subscription_id is None


def test_get_task_returns_title_and_percent():
    from app.services.planner_service import get_task
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"id": "task-1", "title": "Sprint 3 - Fim", "percentComplete": 100}

    with patch("app.services.planner_service.get_graph_token", return_value="tok"), \
         patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        result = asyncio.get_event_loop().run_until_complete(
            get_task("tenant-1", "task-1")
        )
    assert result["title"] == "Sprint 3 - Fim"
    assert result["percentComplete"] == 100


def test_get_task_returns_none_on_error():
    from app.services.planner_service import get_task

    with patch("app.services.planner_service.get_graph_token", side_effect=Exception("fail")):
        result = asyncio.get_event_loop().run_until_complete(
            get_task("tenant-1", "task-1")
        )
    assert result is None


import pytest


@pytest.mark.asyncio
async def test_renewal_job_renews_teams_with_subscription(team_with_tenant, db):
    """Scheduler renewal job calls renew_graph_subscription for teams with active subscription."""
    team_with_tenant.planner_subscription_id = "sub-to-renew"
    db.commit()

    with patch("app.services.report_scheduler.renew_graph_subscription", new_callable=AsyncMock, return_value=True) as mock_renew:
        from app.services.report_scheduler import renew_all_planner_subscriptions
        await renew_all_planner_subscriptions()

    # Verify the call used the correct tenant + subscription from real DB
    mock_renew.assert_any_call("test-tenant-abc", "sub-to-renew")


@pytest.mark.asyncio
async def test_renewal_job_skips_teams_without_subscription(team, db):
    """Scheduler renewal job does not call Graph API for teams with no subscription."""
    assert team.planner_subscription_id is None

    with patch("app.services.report_scheduler.renew_graph_subscription", new_callable=AsyncMock) as mock_renew:
        from app.services.report_scheduler import renew_all_planner_subscriptions
        await renew_all_planner_subscriptions()

    # None of the calls should reference this team's (non-existent) subscription
    for call in mock_renew.call_args_list:
        assert call[0][1] is not None
