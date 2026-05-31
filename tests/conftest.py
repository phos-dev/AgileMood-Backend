import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.databases.postgres_database import SessionLocal
from app.schemas.user_schema import User as UserORM
from app.schemas.team_schema import Team as TeamORM
from app.routers.authentication import create_access_token
from app.utils.constants import Role
from app.crud.user_crud import get_password_hash

client = TestClient(app)


def _unique_email(prefix: str) -> str:
    return f"{prefix}.{uuid.uuid4().hex[:8]}@test.example.com"


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def manager(db):
    user = UserORM(
        name="Test Manager",
        email=_unique_email("mgr"),
        hashed_password=get_password_hash("testpass"),
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
        name="Test Employee",
        email=_unique_email("emp"),
        hashed_password=get_password_hash("testpass"),
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
    t = TeamORM(name=f"Test Team {uuid.uuid4().hex[:6]}", manager_id=manager.id)
    db.add(t)
    db.commit()
    db.refresh(t)
    yield t
    db.delete(t)
    db.commit()


@pytest.fixture
def team_with_tenant(db, team):
    team.teams_tenant_id = "test-tenant-abc"
    db.commit()
    db.refresh(team)
    yield team


@pytest.fixture
def manager_token(manager):
    return create_access_token({"sub": manager.email})


@pytest.fixture
def employee_token(employee):
    return create_access_token({"sub": employee.email})
