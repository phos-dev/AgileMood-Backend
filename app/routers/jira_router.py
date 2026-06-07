import hashlib
import hmac
import json
import os
import time
from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.auth_utils import ensure_is_team_manager
from app.crud import team_crud, questionnaire_crud
from app.databases.postgres_database import get_db
from app.models.team_model import JiraConnectRequest, TeamDataSafe
from app.models.user_model import UserInDB
from app.routers.authentication import get_current_active_user, create_sprint_token
from app.services import slack_service, teams_service
from app.utils.constants import Errors
from app.utils.logger import logger

router = APIRouter(tags=["jira"])

_SEEN_SPRINT_IDS: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 60


def _is_duplicate_sprint(sprint_id: str) -> bool:
    now = time.time()
    cutoff = now - _DEDUP_TTL_SECONDS
    expired = [k for k, v in _SEEN_SPRINT_IDS.items() if v < cutoff]
    for k in expired:
        del _SEEN_SPRINT_IDS[k]
    if sprint_id in _SEEN_SPRINT_IDS:
        return True
    _SEEN_SPRINT_IDS[sprint_id] = now
    return False


def _verify_jira_signature(body: bytes, signature_header: str | None) -> bool:
    """Validate HMAC-SHA256 signature sent by Forge trigger.

    Forge computes: sha256=HMAC-SHA256(JIRA_WEBHOOK_SECRET, body)
    """
    secret = os.getenv("JIRA_WEBHOOK_SECRET", "")
    if not secret:
        return True  # skip validation when secret not configured (dev/test)
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.post("/integrations/jira/connect", response_model=TeamDataSafe)
def jira_connect(
    team_id: int,
    body: JiraConnectRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    updated = team_crud.update_jira_credentials(db, team_id, body.jira_token, body.jira_cloud_id)
    if updated is None:
        raise Errors.INVALID_PARAMS

    logger.debug(f"Jira integration connected for team {team_id}.")
    return updated


@router.delete("/integrations/jira/disconnect")
def jira_disconnect(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    team_crud.update_jira_credentials(db, team_id, None, None)
    logger.debug(f"Jira integration disconnected for team {team_id}.")
    return {"message": f"Jira integration removed for team {team_id}."}


@router.api_route("/webhooks/jira/sprint-end", methods=["POST", "HEAD"])
async def jira_sprint_end(
    team_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if request.method == "HEAD":
        return Response(status_code=200)

    body = await request.body()
    signature = request.headers.get("x-jira-signature")
    if not _verify_jira_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid Jira webhook signature.")

    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    try:
        payload = json.loads(body)
    except (ValueError, KeyError):
        return {"message": "Event ignored."}

    if payload.get("webhookEvent") != "jira:sprint_closed":
        return {"message": "Event ignored."}

    jira_sprint_id = str(payload.get("sprint", {}).get("id", ""))
    if jira_sprint_id and _is_duplicate_sprint(jira_sprint_id):
        return {"message": "Duplicate event ignored."}

    sprint = questionnaire_crud.create_sprint(db, team_id, jira_sprint_id=jira_sprint_id or None)
    sprint_token = create_sprint_token(team_id, sprint.id)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    questionnaire_url = f"{frontend_url}/questionnaire/{sprint_token}"

    background_tasks.add_task(slack_service.send_sprint_end_reminder, team_id, questionnaire_url, sprint.sprint_number)
    background_tasks.add_task(teams_service.send_sprint_end_reminder, team_id, questionnaire_url, sprint.sprint_number)
    logger.debug(f"Jira sprint-end webhook received for team {team_id}. Reminders queued.")
    return {"message": "Sprint-end reminder queued."}
