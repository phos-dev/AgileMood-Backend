from hashlib import sha256

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.schemas.user_schema import User as UserModel
from app.schemas.team_schema import Team as TeamSchema, user_teams
from app.models.user_model import UserCreate, UserInDB

from app.utils.logger import logger


def get_user_by_id(db: Session, user_id: int) -> UserInDB | None:
    return db.query(UserModel).filter(UserModel.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> UserInDB | None:
    return db.query(UserModel).filter(UserModel.email == email).first()


def get_user_team(db: Session, user_id: int):
    # Try member join table first (employees and managers who are also members)
    team_id = db.execute(
        select(user_teams.c.team_id)
        .where(user_teams.c.user_id == user_id)
        .order_by(user_teams.c.team_id)
    ).scalar()
    if team_id is not None:
        return team_id
    # Fallback: user is a manager who owns a team directly (not in user_teams)
    team = db.query(TeamSchema).filter(TeamSchema.manager_id == user_id).first()
    return team.id if team else None


def create_user(db: Session, user: UserCreate):
    db_user = UserModel(
        name=user.name,
        email=user.email,
        disabled=False,
        hashed_password=get_password_hash(user.password),
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: dict):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()

    if user is None:
        logger.error(f"User with ID {user_id} not found.")
        return None

    for key, value in user_update.items():
        if hasattr(user, key):
            logger.debug("Updating user field %s to: %s", key, value)
            setattr(user, key, value)

    db.commit()
    db.refresh(user)

    logger.debug(f"User with ID {user_id} updated successfully.")
    return user


def update_slack_user_id(db: Session, user_id: int, slack_user_id: str | None):
    """
    Sets or clears the manual Slack user ID override for a user.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.error(f"User with ID {user_id} not found.")
        return None
    user.slack_user_id = slack_user_id
    db.commit()
    db.refresh(user)
    logger.debug(f"Slack user ID updated for user {user_id}.")
    return user


def update_teams_user_id(db: Session, user_id: int, teams_user_id: str | None):
    """
    Sets or clears the Microsoft Teams user ID override for a user.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        logger.error(f"User with ID {user_id} not found.")
        return None
    user.teams_user_id = teams_user_id
    db.commit()
    db.refresh(user)
    logger.debug(f"Teams user ID updated for user {user_id}.")
    return user


def reset_password(db: Session, user_id: int, new_password: str):
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int):
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    db.delete(user)
    db.commit()


def get_password_hash(password: str) -> str:
    return sha256(password.encode('utf-8')).hexdigest()
