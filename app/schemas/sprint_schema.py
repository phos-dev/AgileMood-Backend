import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, JSON, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
import app.databases.postgres_database as db


class Sprint(db.Base):
    __tablename__ = 'sprint'

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey('team.id'), nullable=False)
    sprint_number = Column(Integer, nullable=False)
    jira_sprint_id = Column(Text, nullable=True)
    sprint_name = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint('team_id', 'sprint_number', name='uq_sprint_team_number'),)

    responses = relationship('PSResponse', back_populates='sprint')
    deduplication = relationship('PSDeduplication', back_populates='sprint')


class PSResponse(db.Base):
    __tablename__ = 'ps_response'

    id = Column(Integer, primary_key=True, index=True)
    sprint_id = Column(Integer, ForeignKey('sprint.id'), nullable=False)
    answers = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    sprint = relationship('Sprint', back_populates='responses')


class PSDeduplication(db.Base):
    __tablename__ = 'ps_deduplication'

    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    sprint_id = Column(Integer, ForeignKey('sprint.id'), nullable=False)
    answered_at = Column(DateTime, default=datetime.datetime.now)

    __table_args__ = (PrimaryKeyConstraint('user_id', 'sprint_id', name='pk_ps_dedup'),)

    sprint = relationship('Sprint', back_populates='deduplication')
