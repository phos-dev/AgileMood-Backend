"""Idempotent dev seed script for AgileMood.

Run via: python scripts/seed.py
Or automatically via entrypoint.sh on docker-compose up.
"""
from hashlib import sha256
import datetime

from sqlalchemy.orm import Session

from app.databases.postgres_database import SessionLocal
from app.schemas.user_schema import User
from app.schemas.team_schema import Team
from app.schemas.emotion_record_schema import Emotion, EmotionRecord
from app.schemas.feedback_schema import Feedback


def _hash_password(password: str) -> str:
    return sha256(password.encode("utf-8")).hexdigest()


def run_seed(session: Session) -> None:
    """Insert dev seed data. No-op if users already exist."""
    if session.query(User).count() > 0:
        print("Seed skipped: data already exists.")
        return

    # --- Users ---
    manager = User(
        name="Alex Manager",
        email="manager@agilemood.dev",
        role="manager",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    alice = User(
        name="Alice Dev",
        email="alice@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    bob = User(
        name="Bob Dev",
        email="bob@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    carol = User(
        name="Carol Dev",
        email="carol@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    dave = User(
        name="Dave Dev",
        email="dave@agilemood.dev",
        role="employee",
        hashed_password=_hash_password("password123"),
        disabled=False,
    )
    session.add_all([manager, alice, bob, carol, dave])
    session.flush()  # get IDs before using in FKs

    # --- Teams ---
    backend_team = Team(
        name="Backend Team",
        manager_id=manager.id,
        members=[alice, bob],
    )
    frontend_team = Team(
        name="Frontend Team",
        manager_id=manager.id,
        members=[carol, dave],
    )
    platform_team = Team(
        name="Platform Team",
        manager_id=manager.id,
        members=[alice, carol],
    )
    session.add_all([backend_team, frontend_team, platform_team])
    session.flush()

    # --- Emotions (per team) ---
    def _make_emotions(team: Team):
        return [
            Emotion(name="Happy", emoji="😊", color="#FFD700", team_id=team.id, is_negative=False),
            Emotion(name="Anxious", emoji="😰", color="#FF6347", team_id=team.id, is_negative=True),
            Emotion(name="Focused", emoji="🎯", color="#4169E1", team_id=team.id, is_negative=False),
            Emotion(name="Frustrated", emoji="😤", color="#DC143C", team_id=team.id, is_negative=True),
        ]

    backend_emotions = _make_emotions(backend_team)
    frontend_emotions = _make_emotions(frontend_team)
    platform_emotions = _make_emotions(platform_team)
    session.add_all(backend_emotions + frontend_emotions + platform_emotions)
    session.flush()

    # --- Emotion Records (30+, spread over 30 days) ---
    now = datetime.datetime.utcnow()
    records = []

    # ~11 records per team = 33 total
    team_configs = [
        (backend_emotions, [alice, bob]),
        (frontend_emotions, [carol, dave]),
        (platform_emotions, [alice, carol]),
    ]

    day_offset = 0
    for emotions, members in team_configs:
        for i in range(11):
            user = members[i % len(members)]
            emotion = emotions[i % len(emotions)]
            is_anon = (i % 3 == 0)  # every 3rd record is anonymous
            records.append(EmotionRecord(
                user_id=None if is_anon else user.id,
                emotion_id=emotion.id,
                intensity=(i % 5) + 1,  # 1-5
                notes=f"Dev seed record {i}" if i % 2 == 0 else None,
                is_anonymous=is_anon,
                created_at=now - datetime.timedelta(days=day_offset % 30),
            ))
            day_offset += 1
    session.add_all(records)
    session.flush()

    # --- Feedback (5+) ---
    feedback_texts = [
        "Great sprint, team energy was high!",
        "Some blockers caused frustration mid-week.",
        "Communication improved noticeably this week.",
        "Deployment anxiety was palpable on Thursday.",
        "The team handled the incident really well.",
        "Would like more async updates to reduce meeting fatigue.",
    ]
    feedbacks = []
    for i, text in enumerate(feedback_texts):
        record = records[i]
        feedbacks.append(Feedback(
            message=text,
            emotion_record_id=record.id,
            manager_id=manager.id,
            is_anonymous=(i % 2 == 0),
            created_at=now - datetime.timedelta(days=i * 4),
        ))
    session.add_all(feedbacks)
    session.commit()
    print(f"Seed complete: 5 users, 3 teams, {len(records)} emotion records, {len(feedbacks)} feedback entries.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()
