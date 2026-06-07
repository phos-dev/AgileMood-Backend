from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.auth_utils import ensure_is_team_member_or_manager
from app.crud import questionnaire_crud, team_crud
from app.databases.postgres_database import get_db
from app.models.sprint_model import (
    CurrentSprintTokenResponse,
    PSReportResponse,
    PSScoreEntry,
    PSSubmitRequest,
    QuestionnaireState,
)
from app.models.user_model import UserInDB
from app.routers.authentication import (
    create_sprint_token,
    decode_sprint_token,
    get_current_active_user,
)
from app.utils.constants import Errors

router = APIRouter(tags=["questionnaire"])

_VALID_ANSWER_KEYS = {f"q{i}" for i in range(1, 8)}


def _validate_answers(answers: dict[str, int]) -> None:
    if set(answers.keys()) != _VALID_ANSWER_KEYS:
        raise HTTPException(status_code=422, detail="answers must have exactly keys q1..q7")
    for key, val in answers.items():
        if not isinstance(val, int) or val < 1 or val > 5:
            raise HTTPException(status_code=422, detail=f"{key} must be an integer between 1 and 5")


@router.get("/questionnaire/{sprint_token}", response_model=QuestionnaireState)
def get_questionnaire_state(
    sprint_token: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team_id, sprint_id = decode_sprint_token(sprint_token)

    sprint = questionnaire_crud.get_sprint_by_id(db, sprint_id)
    if not sprint or sprint.team_id != team_id:
        raise Errors.NOT_FOUND

    dedup = questionnaire_crud.has_answered(db, current_user.id, sprint_id)
    if dedup:
        return QuestionnaireState(
            status="answered",
            answered_at=dedup.answered_at,
            sprint_number=sprint.sprint_number,
        )
    return QuestionnaireState(status="pending", sprint_number=sprint.sprint_number)


@router.post("/questionnaire/submit")
def submit_questionnaire(
    body: PSSubmitRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    _validate_answers(body.answers)
    team_id, sprint_id = decode_sprint_token(body.sprint_token)

    sprint = questionnaire_crud.get_sprint_by_id(db, sprint_id)
    if not sprint or sprint.team_id != team_id:
        raise Errors.NOT_FOUND

    if questionnaire_crud.has_answered(db, current_user.id, sprint_id):
        raise HTTPException(status_code=409, detail="Você já respondeu o questionário deste sprint.")

    questionnaire_crud.save_ps_response(db, sprint_id, body.answers)
    questionnaire_crud.mark_answered(db, current_user.id, sprint_id)
    return {"message": "Resposta registrada com sucesso."}


@router.get("/teams/{team_id}/current-sprint-token", response_model=CurrentSprintTokenResponse)
def get_current_sprint_token(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND
    ensure_is_team_member_or_manager(team, current_user)

    sprint = questionnaire_crud.get_active_sprint(db, team_id)
    if not sprint:
        raise HTTPException(status_code=404, detail="Nenhum sprint ativo para este time.")

    token = create_sprint_token(team_id, sprint.id)
    return CurrentSprintTokenResponse(sprint_token=token, sprint_number=sprint.sprint_number, sprint_name=sprint.sprint_name)
