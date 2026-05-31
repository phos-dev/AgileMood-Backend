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
