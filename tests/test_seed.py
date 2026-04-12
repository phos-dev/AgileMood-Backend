"""Tests for the dev seed script."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.databases.postgres_database import Base
import app.schemas.user_schema  # noqa: F401 - register models with Base.metadata before create_all
import app.schemas.team_schema  # noqa: F401
import app.schemas.emotion_record_schema  # noqa: F401
import app.schemas.feedback_schema  # noqa: F401


@pytest.fixture
def db_session():
    """In-memory SQLite session with all tables created."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


def test_seed_creates_expected_users(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "user"')).scalar()
    assert result == 5


def test_seed_creates_expected_teams(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "team"')).scalar()
    assert result == 3


def test_seed_creates_emotion_records(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "emotion_record"')).scalar()
    assert result >= 30


def test_seed_creates_feedback(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(text('SELECT COUNT(*) FROM "feedback"')).scalar()
    assert result >= 5


def test_seed_is_idempotent(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)
    run_seed(db_session)  # second call must be a no-op

    result = db_session.execute(text('SELECT COUNT(*) FROM "user"')).scalar()
    assert result == 5  # still 5, not 10


def test_manager_role_is_correct(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(
        text('SELECT role FROM "user" WHERE email = :email'),
        {"email": "manager@agilemood.dev"}
    ).scalar()
    assert result == "manager"


def test_member_role_is_correct(db_session):
    from scripts.seed import run_seed
    run_seed(db_session)

    result = db_session.execute(
        text('SELECT role FROM "user" WHERE email = :email'),
        {"email": "alice@agilemood.dev"}
    ).scalar()
    assert result == "employee"


def test_password_is_hashed(db_session):
    from scripts.seed import run_seed
    from hashlib import sha256
    run_seed(db_session)

    result = db_session.execute(
        text('SELECT hashed_password FROM "user" WHERE email = :email'),
        {"email": "manager@agilemood.dev"}
    ).scalar()
    expected = sha256("password123".encode("utf-8")).hexdigest()
    assert result == expected
