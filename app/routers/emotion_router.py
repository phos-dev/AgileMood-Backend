from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import Annotated

from app.core.rate_limiter import limiter
from app.crud import emotion_crud

from app.models.emotion_model import EmotionInDb, Emotion, AllEmotionsResponse
from app.models.emotion_record_model import AllEmotionReportsResponse

from app.models.user_model import UserInDB

from app.databases.postgres_database import get_db

from app.utils.constants import Errors, Role, Messages
from app.utils.logger import logger

from app.routers.authentication import get_current_active_user

router = APIRouter(
    prefix="/emotions",
    tags=["emotions"],
)


@router.post("/", response_model=EmotionInDb)
def create_emotion(
        emotion: Emotion,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    logger.debug("call to create a new emotion")

    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION
    
    response = emotion_crud.create_emotion(db, emotion, current_user.id)
    if response is None:
        raise Errors.INVALID_PARAMS

    return response


@router.get("/public", response_model=AllEmotionsResponse)
@limiter.limit("60/minute")
def get_emotions_public(request: Request, team_id: int, db: Session = Depends(get_db)):
    emotions = emotion_crud.get_emotions_by_team(db, team_id)
    return AllEmotionsResponse(emotions=emotions or [])


@router.get("/{emotion_id}", response_model=AllEmotionReportsResponse)
def get_emotion_by_id(
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        emotion_id: int,
        db: Session = Depends(get_db),
):
    logger.debug("call to get an emotion by its id: %s", emotion_id)

    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION
    
    reports = emotion_crud.get_emotion_by_id(db, emotion_id, current_user.id)
    if reports is None:
        logger.error(f"no emotion report found for this id: ", emotion_id)
        raise Errors.NOT_FOUND
    
    return AllEmotionReportsResponse(reports=reports)


@router.get("/", response_model=AllEmotionsResponse)
def get_all_emotions(
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
        team_id: int | None = None,
):
    logger.debug("call to get all emotions")

    if team_id is not None:
        emotions = emotion_crud.get_emotions_by_team(db, team_id)
    else:
        emotions = emotion_crud.get_all_emotions(db, current_user.id)

    return AllEmotionsResponse(emotions=emotions or [])


@router.put("/{emotion_id}", response_model=EmotionInDb)
def update_emotion_by_id(
        emotion_id: int,
        emotion_update: dict,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    logger.debug(f"Call to update emotion by id: {emotion_id}")

    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION

    updated_emotion = emotion_crud.update_emotion(db, emotion_id, emotion_update, current_user.id)
    if updated_emotion is None:
        logger.error(f"Failed to update emotion with name: {emotion_id}")
        raise Errors.INVALID_PARAMS

    return updated_emotion


@router.delete("/{emotion_id}")
def delete_emotion_by_id(
        emotion_id: int,
        current_user: Annotated[UserInDB, Depends(get_current_active_user)],
        db: Session = Depends(get_db),
):
    logger.debug(f"Call to delete emotion by ID: {emotion_id}")

    if current_user.role != Role.MANAGER:
        raise Errors.NO_PERMISSION

    success = emotion_crud.delete_emotion(db, emotion_id, current_user.id)
    if not success:
        raise Errors.NOT_FOUND

    return Messages.EMOTION_DELETE
