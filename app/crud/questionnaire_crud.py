import datetime
import math
from sqlalchemy.orm import Session

from app.schemas.sprint_schema import Sprint, PSResponse, PSDeduplication

REVERSE_ITEMS = {1, 3, 5}


def _adjusted_scores(answers: dict) -> list[float]:
    result = []
    for i in range(1, 8):
        raw = answers.get(f"q{i}", 3)
        result.append(6 - raw if i in REVERSE_ITEMS else float(raw))
    return result


def create_sprint(
    db: Session,
    team_id: int,
    jira_sprint_id: str | None = None,
    sprint_name: str | None = None,
    start_date: datetime.datetime | None = None,
) -> Sprint:
    next_number = _next_sprint_number(db, team_id)
    now = datetime.datetime.now(datetime.timezone.utc)
    sprint = Sprint(
        team_id=team_id,
        sprint_number=next_number,
        jira_sprint_id=jira_sprint_id,
        sprint_name=sprint_name,
        start_date=start_date,
        end_date=now,
        questionnaire_expires_at=now + datetime.timedelta(hours=48),
    )
    db.add(sprint)
    db.commit()
    db.refresh(sprint)
    return sprint


def _next_sprint_number(db: Session, team_id: int) -> int:
    last = (
        db.query(Sprint.sprint_number)
        .filter(Sprint.team_id == team_id)
        .order_by(Sprint.sprint_number.desc())
        .first()
    )
    return (last[0] + 1) if last else 1


def get_active_sprint(db: Session, team_id: int) -> Sprint | None:
    now = datetime.datetime.now(datetime.timezone.utc)
    return (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id, Sprint.questionnaire_expires_at > now)
        .order_by(Sprint.sprint_number.desc())
        .first()
    )


def get_sprint_by_id(db: Session, sprint_id: int) -> Sprint | None:
    return db.query(Sprint).filter(Sprint.id == sprint_id).first()


def has_answered(db: Session, user_id: int, sprint_id: int) -> PSDeduplication | None:
    return (
        db.query(PSDeduplication)
        .filter(PSDeduplication.user_id == user_id, PSDeduplication.sprint_id == sprint_id)
        .first()
    )


def save_ps_response(db: Session, sprint_id: int, answers: dict) -> PSResponse:
    response = PSResponse(sprint_id=sprint_id, answers=answers)
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def mark_answered(db: Session, user_id: int, sprint_id: int) -> PSDeduplication:
    dedup = PSDeduplication(user_id=user_id, sprint_id=sprint_id)
    db.add(dedup)
    db.commit()
    db.refresh(dedup)
    return dedup


def get_ps_scores(db: Session, team_id: int) -> list[dict]:
    sprints = (
        db.query(Sprint)
        .filter(Sprint.team_id == team_id)
        .order_by(Sprint.sprint_number)
        .all()
    )
    result = []
    for sprint in sprints:
        responses = db.query(PSResponse).filter(PSResponse.sprint_id == sprint.id).all()
        if not responses:
            continue
        all_scores = [_adjusted_scores(r.answers) for r in responses]
        flat = [score for row in all_scores for score in row]
        count = len(responses)
        mean = sum(flat) / len(flat)
        variance = sum((x - mean) ** 2 for x in flat) / len(flat)
        std_dev = math.sqrt(variance)
        result.append({
            "sprint_number": sprint.sprint_number,
            "response_count": count,
            "mean_score": round(mean, 4),
            "std_dev": round(std_dev, 4),
        })
    return result
