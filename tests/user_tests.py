from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models.user_model import UserCreate, UserInDB, UserInTeam
from app.models.token_model import Token
from app.utils.constants import Errors, Messages, Role
from app.databases.postgres_database import get_db
from app.routers.authentication import create_access_token 
from sqlalchemy.orm import Session

client = TestClient(app)

mock_current_user = UserInDB(
    id=1,
    name="John Doe",
    email="johndoe@example.com",
    disabled=False,
    role=Role.MANAGER,
    hashed_password="hashed_password_123"
)

mock_db = MagicMock(spec=Session)


def test_login_successful():
    with patch("app.routers.user_router.authenticate_user", return_value=True), \
         patch("app.routers.user_router.create_access_token", return_value="fake_token"):
        response = client.post(
            "/user/login",
            data={"username": "johndoe@example.com", "password": "password123"}
        )
        assert response.status_code == 200
        assert response.json() == {"access_token": "fake_token", "token_type": "bearer"}


def test_login_failed():
    with patch("app.routers.user_router.authenticate_user", return_value=False):
        response = client.post(
            "/user/login",
            data={"username": "johndoe@example.com", "password": "wrongpassword"}
        )
        assert response.status_code == 404
        assert response.json()["detail"] == Errors.INCORRECT_CREDENTIALS.detail


def test_create_user_successful():
    mock_user_create = UserCreate(
        name="Jane Doe",
        email="janedoe@example.com",
        password="password123",
        role=Role.EMPLOYEE
    )
    with patch("app.routers.user_router.user_crud.get_user_by_email", return_value=None), \
         patch("app.routers.user_router.user_crud.create_user", return_value=mock_current_user):
        response = client.post("/user/", json=mock_user_create.model_dump())
        assert response.status_code == 200
        assert response.json() == mock_current_user.model_dump()


def test_create_user_email_exists():
    mock_user_create = UserCreate(
        name="Jane Doe",
        email="janedoe@example.com",
        password="password123",
        role=Role.EMPLOYEE
    )
    with patch("app.routers.user_router.user_crud.get_user_by_email", return_value=mock_current_user):
        response = client.post("/user/", json=mock_user_create.model_dump())
        assert response.status_code == 400
        assert response.json()["detail"] == Errors.EMAIL_ALREADY_EXISTS.detail


def test_get_logged_user():
    fake_token = create_access_token({"sub": mock_current_user.email})
    print(fake_token)

    with patch("app.crud.user_crud.get_user_by_email", return_value=mock_current_user), \
         patch("app.crud.user_crud.get_user_team", return_value=1):

        response = client.get(
            "/user/logged",
            headers={"Authorization": f"Bearer {fake_token}"}
        )
        
        assert response.status_code == 200
        assert response.json() == {
            "name": "John Doe",
            "email": "johndoe@example.com",
            "team_id": 1,
            "avatar": None,
            "role": "manager",
            "slack_user_id": None,
            "teams_user_id": None,
        }
        

def test_get_user_by_id_successful():
    with patch("app.routers.user_router.user_crud.get_user_by_id", return_value=mock_current_user):
        response = client.get("/user/1")
        assert response.status_code == 200
        assert response.json() == mock_current_user.model_dump()


def test_get_user_by_id_not_found():
    with patch("app.routers.user_router.user_crud.get_user_by_id", return_value=None):
        response = client.get("/user/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == Errors.NOT_FOUND.detail


def test_update_user_successful():
    fake_token = create_access_token({"sub": mock_current_user.email})

    with patch("app.crud.user_crud.get_user_by_email", return_value=mock_current_user), \
         patch("app.routers.user_router.user_crud.update_user", return_value=mock_current_user):
        response = client.put(
            "/user/",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {fake_token}"} 
        )
        

        assert response.status_code == 200
        assert response.json() == mock_current_user.model_dump()


def test_delete_user_successful():
    with patch("app.routers.user_router.user_crud.get_user_by_id", return_value=mock_current_user), \
         patch("app.routers.user_router.user_crud.delete_user", return_value=True):
        response = client.delete("/user/1")
        assert response.status_code == 200


def test_delete_user_not_found():
    with patch("app.routers.user_router.user_crud.get_user_by_id", return_value=None):
        response = client.delete("/user/9999")
        assert response.status_code == 404
        assert response.json()["detail"] == Errors.NOT_FOUND.detail