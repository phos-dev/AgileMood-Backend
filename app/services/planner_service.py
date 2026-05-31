# app/services/planner_service.py
import os
import httpx
from datetime import datetime, timedelta

from app.services.teams_service import get_graph_token
from app.utils.logger import logger

PLANNER_WEBHOOK_SECRET = os.getenv("PLANNER_WEBHOOK_SECRET", "planner-secret-changeme")
BACKEND_URL = os.getenv("BACKEND_URL", "https://api.agilemood.app")

_GRAPH_SUBSCRIPTIONS = "https://graph.microsoft.com/v1.0/subscriptions"
_MAX_EXPIRY_MINUTES = 4230


def _expiry_iso() -> str:
    return (datetime.utcnow() + timedelta(minutes=_MAX_EXPIRY_MINUTES)).isoformat() + "Z"


async def create_graph_subscription(tenant_id: str, team_id: int, plan_id: str) -> str:
    token = await get_graph_token(tenant_id)
    payload = {
        "changeType": "updated",
        "notificationUrl": f"{BACKEND_URL}/webhooks/planner/plan-completed?team_id={team_id}",
        "resource": f"/planner/plans/{plan_id}/tasks",
        "expirationDateTime": _expiry_iso(),
        "clientState": PLANNER_WEBHOOK_SECRET,
        "includeResourceData": False,
    }
    async with httpx.AsyncClient() as http:
        response = await http.post(
            _GRAPH_SUBSCRIPTIONS,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json()["id"]


async def renew_graph_subscription(tenant_id: str, subscription_id: str) -> bool:
    try:
        token = await get_graph_token(tenant_id)
        async with httpx.AsyncClient() as http:
            response = await http.patch(
                f"{_GRAPH_SUBSCRIPTIONS}/{subscription_id}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"expirationDateTime": _expiry_iso()},
                timeout=10.0,
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to renew Graph subscription {subscription_id}: {e}")
        return False


async def delete_graph_subscription(tenant_id: str, subscription_id: str) -> bool:
    try:
        token = await get_graph_token(tenant_id)
        async with httpx.AsyncClient() as http:
            response = await http.delete(
                f"{_GRAPH_SUBSCRIPTIONS}/{subscription_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Failed to delete Graph subscription {subscription_id}: {e}")
        return False
