from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Annotated
from app.core.auth_utils import ensure_is_team_manager, ensure_is_team_member_or_manager
from app.models.team_model import Team, TeamResponse, AllTeamsResponse, TeamData, SlackBotTokenUpdate
from app.models.user_model import UserInDB
from app.models.emotion_model import AllEmotionsResponse
from app.databases.postgres_database import get_db
from app.utils.constants import Errors, Role, Messages
from app.utils.logger import logger
from app.crud import team_crud
from app.crud import emotion_crud
from app.crud import user_crud
from app.routers.authentication import get_current_active_user

router = APIRouter(
    prefix="/teams",
    tags=["teams"],
)


@router.post("/", response_model=TeamData)
def create_team(
        team: Team,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    """
    Creates a new team.
    Only users with the 'manager' role can create new teams.
    """
    logger.debug("Call to create a new team.")

    if current_user.role != Role.MANAGER:
        logger.error(f"User doesn't have the permission to create new teams.")
        raise Errors.NO_PERMISSION
    
    db_team = team_crud.create_team(db, team.name, current_user.id)
    if db_team is None:
        raise Errors.INVALID_PARAMS

    return db_team


@router.get("/{team_id}", response_model=TeamResponse)
def get_team_by_id(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_member_or_manager(team, current_user)

    emotions = emotion_crud.get_emotions_by_team(db, team_id)
    team["emotions"] = emotions

    return team


@router.get("/", response_model=AllTeamsResponse)
def get_all_teams(
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    logger.debug("Listing Teams for manager %s", current_user.id)
    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION

    teams = team_crud.get_teams_by_manager(db, current_user.id)
    return AllTeamsResponse(teams=teams)


@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    team_update: Team,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    team_update.manager_id = current_user.id
    return team_crud.update_team(db, team_id, team_update)

@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    team_crud.delete_team(db, team_id)
    return {"message": f"Team {team_id} deleted."}

@router.post("/{team_id}")
def add_team_member(
        team_id: int,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
        user_email: str = Query(..., description="Email do usuário a ser adicionado"),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    user = user_crud.get_user_by_email(db, user_email)
    if not user:
        raise Errors.INVALID_PARAMS

    team_crud.add_team_member(db, team_id, user.id)
    return Messages.MEMBER_ADDED_TO_TEAM


@router.delete("/{team_id}/member")
def remove_team_member(
        team_id: int,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
        user_email: str = Query(..., description="Email do usuário a ser removido"),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    user = user_crud.get_user_by_email(db, user_email)
    if not user:
        raise Errors.INVALID_PARAMS

    team_crud.remove_team_member(db, team_id, user.id)
    return Messages.MEMBER_ADDED_TO_TEAM


@router.put("/{team_id}/slack-bot-token", response_model=TeamData)
def set_slack_bot_token(
    team_id: int,
    token_update: SlackBotTokenUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    Sets or updates the Slack bot token for a team.
    Only the team manager can configure this.
    """
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    updated = team_crud.update_slack_bot_token(db, team_id, token_update.slack_bot_token)
    if updated is None:
        raise Errors.INVALID_PARAMS
    return updated


@router.delete("/{team_id}/slack-bot-token")
def remove_slack_bot_token(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    Removes the Slack bot token from a team (disables Slack integration).
    Only the team manager can do this.
    """
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    team_crud.update_slack_bot_token(db, team_id, None)
    return {"message": f"Slack bot token removed for team {team_id}."}


@router.get("/{team_id}/emotions", response_model=AllEmotionsResponse)
def get_emotions_by_team(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_member_or_manager(team, current_user)

    emotions = emotion_crud.get_emotions_by_team(db, team_id)
    return AllEmotionsResponse(emotions=emotions)
