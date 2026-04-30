from sqlalchemy import Column, Integer, String, Boolean
import app.databases.postgres_database as db
from sqlalchemy.orm import relationship

from app.utils.constants import DataBase, Role


class User(db.Base):
    __tablename__ = DataBase.USER_TABLE_NAME

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    disabled = Column(Boolean, nullable=False, default=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default=Role.EMPLOYEE)
    avatar = Column(String, nullable=True)
    slack_user_id = Column(String, nullable=True)

    emotion_records = relationship("EmotionRecord", back_populates="user")

    managed_teams = relationship("Team", back_populates="manager")

    teams = relationship("Team", secondary="user_teams", back_populates="members")
