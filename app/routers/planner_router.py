from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.auth_utils import ensure_is_team_manager
from app.crud import team_crud
from app.databases.postgres_database import get_db
from app.models.team_model import PlannerSubscribeRequest
from app.routers.authentication import get_current_active_user
from app.schemas.user_schema import User
from app.services.planner_service import (
    PLANNER_WEBHOOK_SECRET,
    create_graph_subscription,
    delete_graph_subscription,
    renew_graph_subscription,
)
from app.services.report_scheduler import send_sprint_end_reminder_teams
from app.utils.logger import logger

router = APIRouter(tags=["planner"])


@router.post("/webhooks/planner/plan-completed")
async def planner_notification(
    team_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    validationToken: str | None = None,
):
    if validationToken:
        if len(validationToken) > 512:
            raise HTTPException(status_code=400, detail="Invalid validation token.")
        return PlainTextResponse(validationToken)

    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")

    try:
        body = await request.json()
    except ValueError:
        logger.warning(f"Malformed JSON in planner webhook for team {team_id}")
        return Response(status_code=202)

    triggered = False
    for notification in body.get("value", []):
        if notification.get("clientState") != PLANNER_WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid clientState")
        resource_data = notification.get("resourceData", {})
        if resource_data.get("percentComplete") == 100 and not triggered:
            background_tasks.add_task(send_sprint_end_reminder_teams, team_id)
            triggered = True

    return Response(status_code=202)


@router.post("/integrations/planner/subscribe")
async def subscribe_planner(
    team_id: int,
    body: PlannerSubscribeRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    ensure_is_team_manager(team, current_user)
    team_data = team["team_data"]
    if not team_data.teams_tenant_id:
        raise HTTPException(status_code=400, detail="Teams integration required before subscribing to Planner.")
    subscription_id = await create_graph_subscription(team_data.teams_tenant_id, team_id, body.plan_id)
    team_crud.update_planner_subscription_id(db, team_id, subscription_id)
    return {"subscription_id": subscription_id}


@router.post("/integrations/planner/renew")
async def renew_planner_subscription(
    team_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    ensure_is_team_manager(team, current_user)
    team_data = team["team_data"]
    if not team_data.planner_subscription_id or not team_data.teams_tenant_id:
        raise HTTPException(status_code=404, detail="No active Planner subscription.")
    success = await renew_graph_subscription(team_data.teams_tenant_id, team_data.planner_subscription_id)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to renew Planner subscription.")
    return {"renewed": True}


@router.delete("/integrations/planner/unsubscribe")
async def unsubscribe_planner(
    team_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found.")
    ensure_is_team_manager(team, current_user)
    team_data = team["team_data"]
    if team_data.planner_subscription_id and team_data.teams_tenant_id:
        await delete_graph_subscription(team_data.teams_tenant_id, team_data.planner_subscription_id)
    team_crud.update_planner_subscription_id(db, team_id, None)
    return {"unsubscribed": True}
