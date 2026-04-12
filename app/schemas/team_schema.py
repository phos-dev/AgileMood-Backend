from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
import app.databases.postgres_database as db
from app.utils.constants import DataBase
import datetime


# Table responsible for the N:N relationship between Users and Teams
user_teams = Table(
    "user_teams",
    db.Base.metadata,
    Column("user_id", Integer, ForeignKey("user.id"), primary_key=True),
    Column("team_id", Integer, ForeignKey("team.id"), primary_key=True)
)


class Team(db.Base):
    __tablename__ = DataBase.TEAM_TABLE_NAME

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    manager_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    slack_bot_token = Column(String, nullable=True)

    manager = relationship("User", back_populates="managed_teams")

    members = relationship("User", secondary="user_teams", back_populates="teams")

    emotions = relationship("Emotion", back_populates="team", cascade="all, delete")
