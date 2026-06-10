import uuid
import pytest
from app.crud import feedback_crud, emotion_record_crud
from app.schemas.emotion_record_schema import Emotion, EmotionRecord
from app.schemas.feedback_schema import Feedback
from app.schemas.team_schema import Team as TeamORM, user_teams as user_teams_table
from app.schemas.user_schema import User as UserORM
from app.crud.user_crud import get_password_hash
from app.utils.constants import Role


def _email():
    return f"test.{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def manager(db):
    user = UserORM(
        name="Mgr",
        email=_email(),
        hashed_password=get_password_hash("x"),
        role=Role.MANAGER,
        disabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


@pytest.fixture
def employee(db):
    user = UserORM(
        name="Emp",
        email=_email(),
        hashed_password=get_password_hash("x"),
        role=Role.EMPLOYEE,
        disabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


@pytest.fixture
def team(db, manager):
    t = TeamORM(name=f"Team {uuid.uuid4().hex[:6]}", manager_id=manager.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    yield t
    db.delete(t)
    db.commit()


@pytest.fixture
def emotion(db, team):
    e = Emotion(name="Happy", team_id=team.id, is_negative=False)
    db.add(e)
    db.commit()
    db.refresh(e)
    yield e
    db.delete(e)
    db.commit()


@pytest.fixture
def emotion_record(db, employee, emotion):
    er = EmotionRecord(
        user_id=employee.id,
        emotion_id=emotion.id,
        intensity=3,
        is_anonymous=False,
    )
    db.add(er)
    db.commit()
    db.refresh(er)
    yield er
    db.delete(er)
    db.commit()


@pytest.fixture
def anonymous_emotion_record(db, employee, emotion):
    er = EmotionRecord(
        user_id=employee.id,
        emotion_id=emotion.id,
        intensity=3,
        is_anonymous=True,
    )
    db.add(er)
    db.commit()
    db.refresh(er)
    yield er
    db.delete(er)
    db.commit()


def test_manager_of_team_can_send_feedback(db, manager, emotion_record):
    """Manager owns the team via Emotion.team_id — must return True."""
    result = feedback_crud.can_manager_send_feedback(db, manager.id, emotion_record.id)
    assert result is True


def test_manager_of_team_can_send_feedback_anonymous(db, manager, anonymous_emotion_record):
    """Same check holds for anonymous records."""
    result = feedback_crud.can_manager_send_feedback(db, manager.id, anonymous_emotion_record.id)
    assert result is True


def test_other_manager_cannot_send_feedback(db, employee, emotion, emotion_record):
    """A manager who does NOT own the team must return False."""
    # Create a second manager who manages a different team
    other_mgr = UserORM(
        name="Other Mgr",
        email=_email(),
        hashed_password=get_password_hash("x"),
        role=Role.MANAGER,
        disabled=False,
    )
    db.add(other_mgr)
    db.commit()
    db.refresh(other_mgr)

    result = feedback_crud.can_manager_send_feedback(db, other_mgr.id, emotion_record.id)

    db.delete(other_mgr)
    db.commit()

    assert result is False


def test_nonexistent_emotion_record_returns_false(db, manager):
    result = feedback_crud.can_manager_send_feedback(db, manager.id, 9999999)
    assert result is False


def test_anonymous_record_with_user_id_appears_in_team_listing(db, employee, anonymous_emotion_record, team, emotion):
    """
    After the resolver fix, anonymous records store user_id.
    The team listing query (for_team=True) must find them via user_id.in_()
    and must NOT produce ghost entries (user_id=None in the raw query).
    """
    results = emotion_record_crud.get_emotion_records_by_user_id(
        db, [employee.id], for_team=True, team_id=team.id
    )

    ids = [r.id for r in results]
    assert anonymous_emotion_record.id in ids

    # identity masked in response even though DB has real user_id
    anon_result = next(r for r in results if r.id == anonymous_emotion_record.id)
    assert anon_result.user_id is None
    assert anon_result.is_anonymous is True


def test_employee_sees_feedback_on_anonymous_emotion_record(db, manager, anonymous_emotion_record):
    """
    Regression: anonymous records now store user_id, so employee must see manager replies.
    Before the fix, user_id was NULL → get_feedbacks_by_user_id returned nothing.
    """
    feedback = Feedback(
        message="Keep it up!",
        emotion_record_id=anonymous_emotion_record.id,
        manager_id=manager.id,
        is_anonymous=False,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    results = feedback_crud.get_feedbacks_by_user_id(db, anonymous_emotion_record.user_id)

    db.delete(feedback)
    db.commit()

    assert len(results) == 1
    assert results[0].id == feedback.id
    assert results[0].manager_knows_identity is False


def test_manager_without_user_teams_row_can_still_send_feedback(db, manager, emotion_record):
    """
    Key regression: employee NOT in user_teams but emotion belongs to manager's team.
    The fix must return True without relying on user_teams.
    """
    # Verify employee has no user_teams row for this team
    from sqlalchemy import select
    rows = db.execute(
        select(user_teams_table).where(user_teams_table.c.user_id == emotion_record.user_id)
    ).all()
    assert rows == [], "Precondition: employee must not be in user_teams for this test"

    result = feedback_crud.can_manager_send_feedback(db, manager.id, emotion_record.id)
    assert result is True
