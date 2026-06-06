from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class PSSubmitRequest(BaseModel):
    sprint_token: str
    answers: dict[str, int]


class QuestionnaireState(BaseModel):
    status: Literal["pending", "answered", "expired"]
    answered_at: datetime | None = None
    sprint_number: int | None = None


class CurrentSprintTokenResponse(BaseModel):
    sprint_token: str
    sprint_number: int


class PSScoreEntry(BaseModel):
    sprint_number: int
    response_count: int
    mean_score: float
    std_dev: float


class PSReportResponse(BaseModel):
    scores: list[PSScoreEntry]
