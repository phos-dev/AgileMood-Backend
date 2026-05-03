from pydantic import BaseModel, Field
from typing import Literal, Optional


class User(BaseModel):
    name: str
    email: str
    disabled: bool | None = False
    role: Literal["manager", "employee"] = Field(default="employee", description="User role in the organization")
    avatar: str | None = None


class UserCreate(User):
    password: str


class UserInDB(User):
    id: int | None = None
    hashed_password: str
    slack_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None


class UserInTeam(BaseModel):
    name: str
    email: str
    team_id: int | None = None
    role: Literal["manager", "employee"] = Field(default="employee", description="User role in the organization")
    avatar: str | None = None
    slack_user_id: Optional[str] = None
    teams_user_id: Optional[str] = None
