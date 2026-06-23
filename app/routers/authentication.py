import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.crud import user_crud

from app.models.user_model import UserInDB
from app.models.token_model import TokenData

from app.databases.postgres_database import get_db
from app.utils.constants import Errors, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, RESET_TOKEN_EXPIRE_MINUTES
from app.utils.logger import logger


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")


def create_access_token(data: dict | None = None):
    to_encode = data.copy()

    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, email: str, password: str) -> UserInDB | bool | None:
    db_user = user_crud.get_user_by_email(db, email)
    if db_user is None:
        logger.debug("User not found")
        return False
    if db_user.hashed_password != user_crud.get_password_hash(password):
        logger.debug("Incorrect password")
        return False
    return db_user


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise Errors.CREDENTIALS_EXCEPTION
        token_data = TokenData(email=email)
    except InvalidTokenError:
        raise Errors.CREDENTIALS_EXCEPTION

    user = user_crud.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise Errors.CREDENTIALS_EXCEPTION
    return user


async def get_current_active_user(current_user: Annotated[UserInDB, Depends(get_current_user)]):
    if current_user.disabled:
        raise Errors.INACTIVE_USER
    return current_user


def create_reset_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": email, "purpose": "password_reset", "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_reset_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
        email = payload.get("sub")
        if not email:
            raise HTTPException(status_code=400, detail="Invalid reset token")
        return email
    except ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Reset token expired")
    except InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid reset token")


SPRINT_TOKEN_EXPIRE_HOURS = 48


def create_sprint_token(team_id: int, sprint_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=SPRINT_TOKEN_EXPIRE_HOURS)
    payload = {"team_id": team_id, "sprint_id": sprint_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_sprint_token(token: str) -> tuple[int, int]:
    """Returns (team_id, sprint_id). Raises HTTPException on invalid or expired token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["team_id"], payload["sprint_id"]
    except ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="Sprint token expired.")
    except (InvalidTokenError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid sprint token.")
