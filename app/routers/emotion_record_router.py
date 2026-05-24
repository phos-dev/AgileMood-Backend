from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import APIRouter, Depends, Request

from app.crud import emotion_record_crud
from app.crud import emotion_crud

from app.models.emotion_record_model import (
    EmotionRecordInDb,
    EmotionRecord,
    AllEmotionReportsResponse,
    EmotionRecordWithEmotion,
)

from app.models.user_model import UserInDB

from app.routers.authentication import get_current_active_user

from app.databases.postgres_database import get_db

from app.core.rate_limiter import limiter
from app.utils.constants import Errors, Role
from app.utils.logger import logger


router = APIRouter(
    prefix="/emotion_record",
    tags=["emotion records"],
)


@router.post("/", response_model=EmotionRecordInDb)
def create_emotion_record(
    emotion_record: EmotionRecord,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    logger.debug("call to create emotion record")

    emotion_record.user_id = current_user.id
    response = emotion_record_crud.create_emotion_record(db, emotion_record)
    if response is None:
        raise Errors.INVALID_PARAMS

    return response


@router.post("/public", response_model=EmotionRecordInDb)
@limiter.limit("10/minute")
def create_emotion_record_public(
    request: Request,
    team_id: int,
    emotion_record: EmotionRecord,
    db: Session = Depends(get_db),
):
    from app.schemas.emotion_record_schema import Emotion as EmotionSchema
    emotion = db.query(EmotionSchema).filter(EmotionSchema.id == emotion_record.emotion_id).first()
    if not emotion or emotion.team_id != team_id:
        raise Errors.INVALID_PARAMS

    anon_record = EmotionRecord(
        emotion_id=emotion_record.emotion_id,
        intensity=emotion_record.intensity,
        notes=emotion_record.notes,
        user_id=None,
        is_anonymous=True,
    )
    response = emotion_record_crud.create_emotion_record(db, anon_record)
    if response is None:
        raise Errors.INVALID_PARAMS

    logger.debug(f"Anonymous emotion record created for team {team_id}.")
    return response


@router.get("/", response_model=AllEmotionReportsResponse)
def get_all_emotion_report_for_logged_user(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
    include_feedbacks: bool = False,
):
    logger.debug("call to get all emotion records")

    response = emotion_record_crud.get_emotion_records_by_user_id(
        db, [current_user.id], for_team=False, include_feedbacks=include_feedbacks
    )
    if response is None:
        logger.error(f"no emotion record found in the database")

    return AllEmotionReportsResponse(emotion_records=response)


@router.get("/{emotion_name}", response_model=AllEmotionReportsResponse)
def get_emotion_report_for_logged_user_by_emotion_name(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    emotion_name: str,
    db: Session = Depends(get_db),
    include_feedbacks: bool = False,
):
    logger.debug("call to get emotions records by emotion name")

    emotion_id = emotion_crud.get_emotion_id_by_name(db, emotion_name)
    response = emotion_record_crud.get_emotion_records_by_user_id_and_emotion_id(
        db, current_user.id, emotion_id, include_feedbacks=include_feedbacks
    )
    if response is None:
        logger.error(
            f"no emotion record found in the database for this emotion name: {emotion_name}"
        )
        raise Errors.NOT_FOUND
    return AllEmotionReportsResponse(emotion_records=response)


@router.get("/id/{record_id}", response_model=EmotionRecordWithEmotion)
def get_emotion_record_by_id(
    record_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    logger.debug("call to get emotion record by id")

    from app.schemas.emotion_record_schema import EmotionRecord as EmotionRecordSchema

    db_record = (
        db.query(EmotionRecordSchema)
        .filter(EmotionRecordSchema.id == record_id)
        .first()
    )
    if db_record is None or db_record.user_id != current_user.id:
        raise Errors.NOT_FOUND

    record = emotion_record_crud.get_emotion_record_by_id(db, record_id)
    return record
