import jwt
from jwt.exceptions import InvalidTokenError
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.crud import user_crud

from app.models.user_model import UserInDB
from app.models.token_model import TokenData

from app.databases.postgres_database import get_db
from app.utils.constants import Errors, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
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
