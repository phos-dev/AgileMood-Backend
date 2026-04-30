from typing import Annotated

from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.routers.authentication import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
)

from app.services.report_scheduler import send_weekly_reports, send_weekly_reminders
from app.models.user_model import UserCreate, UserInDB, UserInTeam
from app.models.token_model import Token

from app.crud import user_crud
from app.databases.postgres_database import get_db
from app.utils.constants import Errors, Messages, Role
from app.utils.logger import logger


router = APIRouter(
    prefix="/user",
    tags=["user"],
)


@router.post("/test/trigger-reports")
async def trigger_reports_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_weekly_reports)
    return {"message": "Weekly reports triggered in the background!"}

@router.post("/test/trigger-reminders")
async def trigger_reminders_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(send_weekly_reminders)
    return {"message": "Weekly reminders triggered in the background!"}

@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    if not authenticate_user(db, form_data.username, form_data.password):
        raise Errors.INCORRECT_CREDENTIALS

    access_token = create_access_token({"sub": form_data.username})
    return Token(access_token=access_token, token_type="bearer")


@router.post("/", response_model=UserInDB)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    logger.info("Call to create User")
    db_user = user_crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise Errors.EMAIL_ALREADY_EXISTS

    response = user_crud.create_user(db=db, user=user)
    if response is None:
        raise Errors.INVALID_PARAMS
    return response


@router.get("/logged", response_model=UserInTeam)
def get_logged_user(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db)
):

    team_id = user_crud.get_user_team(db, current_user.id)
    result = UserInTeam(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        team_id=team_id,
        avatar=current_user.avatar,
        role=current_user.role
    )

    return result


@router.get("/{user_id}", response_model=UserInDB)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_id(db, user_id=user_id)
    if user is None:
        raise Errors.NOT_FOUND
    return user


@router.get("/")
def get_user_by_email(email: str, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_email(db, email)
    if not user:
        raise Errors.NOT_FOUND
    return user


@router.put("/", response_model=UserInDB)
def update_user_by_id(
        user_update: dict,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    logger.debug(f"Call to update emotion by id: {current_user.id}")

    updated_user = user_crud.update_user(db, current_user.id, user_update)
    if updated_user is None:
        logger.error(f"Failed to update emotion with name: {current_user.id}")
        raise Errors.INVALID_PARAMS

    return updated_user


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = user_crud.get_user_by_id(db, user_id=user_id)
    if user is None:
        raise Errors.NOT_FOUND
    user_crud.delete_user(db=db, user_id=user_id)
    return Messages.USER_DELETE


class SlackUserIdUpdate(BaseModel):
    slack_user_id: str


@router.put("/{user_id}/slack-user-id", response_model=UserInDB)
def set_slack_user_id(
    user_id: int,
    slack_id_update: SlackUserIdUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    Sets a manual Slack user ID override for a user.
    Only managers can configure this.
    """
    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION

    target_user = user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise Errors.NOT_FOUND

    updated = user_crud.update_slack_user_id(db, user_id, slack_id_update.slack_user_id)
    if updated is None:
        raise Errors.INVALID_PARAMS
    return updated


@router.delete("/{user_id}/slack-user-id")
def remove_slack_user_id(
    user_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    """
    Removes the manual Slack user ID override for a user.
    Only managers can do this.
    """
    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION

    target_user = user_crud.get_user_by_id(db, user_id)
    if not target_user:
        raise Errors.NOT_FOUND

    user_crud.update_slack_user_id(db, user_id, None)
    return {"message": f"Slack user ID removed for user {user_id}."}
