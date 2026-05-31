from pydantic import BaseModel, Field
from datetime import datetime
from app.models.user_model import UserInTeam
from app.models.emotion_record_model import EmotionRecordInTeam
from app.models.emotion_model import EmotionInDb
from typing import List, Optional


class Team(BaseModel):
    name: str

    class Config:
        from_attributes = True


class TeamData(Team):
    id: int
    manager_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    slack_bot_token: Optional[str] = None
    teams_tenant_id: Optional[str] = None
    trello_token: Optional[str] = None
    jira_token: Optional[str] = None
    jira_cloud_id: Optional[str] = None
    planner_subscription_id: Optional[str] = None

    class Config:
        from_attributes = True


class TeamDataSafe(Team):
    """TeamData without sensitive integration tokens — safe to return in API responses."""
    id: int
    manager_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    teams_tenant_id: Optional[str] = None
    jira_cloud_id: Optional[str] = None  # cloud ID is not secret; token excluded

    class Config:
        from_attributes = True


class SlackBotTokenUpdate(BaseModel):
    slack_bot_token: str


class TrelloConnectRequest(BaseModel):
    trello_token: str


class JiraConnectRequest(BaseModel):
    jira_token: str
    jira_cloud_id: str


class PlannerSubscribeRequest(BaseModel):
    plan_id: str


class TeamResponse(BaseModel):
    team_data: TeamData
    members: List[UserInTeam]
    emotions_reports: List[EmotionRecordInTeam]
    emotions: List[EmotionInDb]
    manager: UserInTeam


class AllTeamsResponse(BaseModel):
    teams: List[TeamData]
