"""Questionnaire (RF01) tests — mock-based, following project test pattern."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.user_model import UserInDB
from app.routers.authentication import create_access_token, create_sprint_token
from app.utils.constants import Role

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

manager_user = UserInDB(
    id=1, name="Manager", email="manager@example.com",
    disabled=False, role=Role.MANAGER, hashed_password="x",
)
employee_user = UserInDB(
    id=2, name="Employee", email="employee@example.com",
    disabled=False, role=Role.EMPLOYEE, hashed_password="x",
)
employee2_user = UserInDB(
    id=3, name="Employee2", email="employee2@example.com",
    disabled=False, role=Role.EMPLOYEE, hashed_password="x",
)

_mock_team_data = MagicMock(id=1, manager_id=1)
mock_team = {
    "team_data": _mock_team_data,
    "members": [employee_user, employee2_user],
    "manager": manager_user,
}


def _token(user: UserInDB) -> str:
    return create_access_token({"sub": user.email})


_VALID_ANSWERS = {f"q{i}": 3 for i in range(1, 8)}


# ---------------------------------------------------------------------------
# 1. Sprint-end webhook — sprint record created, sprint_number auto-increments
# ---------------------------------------------------------------------------

class TestSprintEndWebhook:
    def test_sprint_created_on_webhook(self):
        """Webhook creates sprint record and queues reminders."""
        import json
        body = json.dumps({
            "webhookEvent": "jira:sprint_closed",
            "sprint": {"id": 55, "name": "Sprint 1"},
        }).encode()
        fake_sprint = MagicMock(id=10, sprint_number=1)
        with patch.dict("os.environ", {"JIRA_WEBHOOK_SECRET": ""}), \
             patch("app.routers.jira_router.team_crud.get_team_by_id", return_value=mock_team), \
             patch("app.routers.jira_router.questionnaire_crud.create_sprint", return_value=fake_sprint) as mock_create, \
             patch("app.routers.jira_router.create_sprint_token", return_value="tok"), \
             patch("app.routers.jira_router.slack_service.send_sprint_end_reminder") as mock_slack, \
             patch("app.routers.jira_router.teams_service.send_sprint_end_reminder"):
            resp = client.post(
                "/webhooks/jira/sprint-end?team_id=1",
                content=body,
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 200
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs[0][1] == 1  # team_id
        mock_slack.assert_called_once()

    def test_sprint_number_increments_per_team(self):
        """Second sprint for same team gets sprint_number=2."""
        from app.crud.questionnaire_crud import _next_sprint_number
        from app.schemas.sprint_schema import Sprint as SprintORM

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = (1,)
        result = _next_sprint_number(mock_db, team_id=1)
        assert result == 2

    def test_first_sprint_gets_number_1(self):
        from app.crud.questionnaire_crud import _next_sprint_number

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        result = _next_sprint_number(mock_db, team_id=1)
        assert result == 1


# ---------------------------------------------------------------------------
# 2. GET /questionnaire/{token}
# ---------------------------------------------------------------------------

class TestGetQuestionnaireState:
    def test_pending_for_new_user(self):
        fake_sprint = MagicMock(id=10, sprint_number=1, team_id=1)
        sprint_token = create_sprint_token(team_id=1, sprint_id=10)
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
             patch("app.routers.questionnaire_router.questionnaire_crud.get_sprint_by_id", return_value=fake_sprint), \
             patch("app.routers.questionnaire_router.questionnaire_crud.has_answered", return_value=None):
            resp = client.get(
                f"/questionnaire/{sprint_token}",
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["sprint_number"] == 1

    def test_answered_for_returning_user(self):
        fake_sprint = MagicMock(id=10, sprint_number=1, team_id=1)
        fake_dedup = MagicMock(answered_at=datetime.now())
        sprint_token = create_sprint_token(team_id=1, sprint_id=10)
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
             patch("app.routers.questionnaire_router.questionnaire_crud.get_sprint_by_id", return_value=fake_sprint), \
             patch("app.routers.questionnaire_router.questionnaire_crud.has_answered", return_value=fake_dedup):
            resp = client.get(
                f"/questionnaire/{sprint_token}",
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"

    def test_expired_token_returns_410(self):
        import jwt as pyjwt
        from app.utils.constants import SECRET_KEY, ALGORITHM
        expired_payload = {
            "team_id": 1,
            "sprint_id": 10,
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        expired_token = pyjwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user):
            resp = client.get(
                f"/questionnaire/{expired_token}",
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 410


# ---------------------------------------------------------------------------
# 3. POST /questionnaire/submit
# ---------------------------------------------------------------------------

class TestSubmitQuestionnaire:
    def test_submit_saves_response_without_user_id(self):
        fake_sprint = MagicMock(id=10, sprint_number=1, team_id=1)
        sprint_token = create_sprint_token(team_id=1, sprint_id=10)
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
             patch("app.routers.questionnaire_router.questionnaire_crud.get_sprint_by_id", return_value=fake_sprint), \
             patch("app.routers.questionnaire_router.questionnaire_crud.has_answered", return_value=None), \
             patch("app.routers.questionnaire_router.questionnaire_crud.save_ps_response") as mock_save, \
             patch("app.routers.questionnaire_router.questionnaire_crud.mark_answered") as mock_mark:
            resp = client.post(
                "/questionnaire/submit",
                json={"sprint_token": sprint_token, "answers": _VALID_ANSWERS},
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 200
        mock_save.assert_called_once()
        save_args = mock_save.call_args[0]
        # save_ps_response(db, sprint_id, answers) — user_id NOT passed
        assert save_args[1] == 10   # sprint_id
        assert save_args[2] == _VALID_ANSWERS
        mock_mark.assert_called_once()

    def test_second_submit_from_same_user_returns_409(self):
        fake_sprint = MagicMock(id=10, sprint_number=1, team_id=1)
        fake_dedup = MagicMock(answered_at=datetime.now())
        sprint_token = create_sprint_token(team_id=1, sprint_id=10)
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
             patch("app.routers.questionnaire_router.questionnaire_crud.get_sprint_by_id", return_value=fake_sprint), \
             patch("app.routers.questionnaire_router.questionnaire_crud.has_answered", return_value=fake_dedup):
            resp = client.post(
                "/questionnaire/submit",
                json={"sprint_token": sprint_token, "answers": _VALID_ANSWERS},
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 409

    def test_invalid_answer_value_returns_422(self):
        sprint_token = create_sprint_token(team_id=1, sprint_id=10)
        bad_answers = {**_VALID_ANSWERS, "q1": 6}  # 6 > 5
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user):
            resp = client.post(
                "/questionnaire/submit",
                json={"sprint_token": sprint_token, "answers": bad_answers},
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 4. Score calculation — mean + std_dev with reverse scoring
# ---------------------------------------------------------------------------

class TestScoreCalculation:
    def test_get_ps_scores_correct_mean_and_std_dev(self):
        """Two users submit known answers → verify mean + std_dev with reverse scoring."""
        from app.crud.questionnaire_crud import get_ps_scores, _adjusted_scores
        from app.schemas.sprint_schema import PSResponse as PSResponseORM, Sprint as SprintORM

        # User 1: all 5s
        answers1 = {f"q{i}": 5 for i in range(1, 8)}
        # User 2: all 1s
        answers2 = {f"q{i}": 1 for i in range(1, 8)}

        # Adjusted for user 1 (items 1,3,5 reverse): q1=6-5=1, q3=6-5=1, q5=6-5=1, rest=5
        adj1 = [1, 5, 1, 5, 1, 5, 5]  # sum=23, items=7
        # Adjusted for user 2: q1=6-1=5, q3=6-1=5, q5=6-1=5, rest=1
        adj2 = [5, 1, 5, 1, 5, 1, 1]  # sum=19, items=7

        assert _adjusted_scores(answers1) == adj1
        assert _adjusted_scores(answers2) == adj2

        user_means = [sum(adj1) / len(adj1), sum(adj2) / len(adj2)]
        expected_mean = sum(user_means) / len(user_means)
        expected_variance = sum((s - expected_mean) ** 2 for s in user_means) / len(user_means)
        expected_std = expected_variance ** 0.5

        fake_sprint = MagicMock(id=10, sprint_number=1, team_id=1)
        fake_r1 = MagicMock(answers=answers1)
        fake_r2 = MagicMock(answers=answers2)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [fake_sprint]
        mock_db.query.return_value.filter.return_value.all.return_value = [fake_r1, fake_r2]

        results = get_ps_scores(mock_db, team_id=1)
        assert len(results) == 1
        r = results[0]
        assert r["sprint_number"] == 1
        assert r["response_count"] == 2
        assert abs(r["mean_score"] - round(expected_mean, 4)) < 0.001
        assert abs(r["std_dev"] - round(expected_std, 4)) < 0.001

    def test_psychological_safety_report_endpoint(self):
        fake_scores = [{"sprint_number": 1, "response_count": 3, "mean_score": 3.5, "std_dev": 0.8}]
        with patch("app.crud.user_crud.get_user_by_email", return_value=manager_user), \
             patch("app.routers.reports_router.questionnaire_crud.get_ps_scores", return_value=fake_scores):
            resp = client.get(
                "/reports/psychological-safety?team_id=1",
                headers={"Authorization": f"Bearer {_token(manager_user)}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["scores"]) == 1
        assert data["scores"][0]["sprint_number"] == 1
        assert data["scores"][0]["mean_score"] == 3.5

    def test_employee_cannot_access_ps_report(self):
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user):
            resp = client.get(
                "/reports/psychological-safety?team_id=1",
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 5. GET /teams/{team_id}/current-sprint-token
# ---------------------------------------------------------------------------

class TestCurrentSprintToken:
    def test_returns_token_when_sprint_active(self):
        fake_sprint = MagicMock(id=10, sprint_number=2, team_id=1)
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
             patch("app.routers.questionnaire_router.team_crud.get_team_by_id", return_value=mock_team), \
             patch("app.routers.questionnaire_router.questionnaire_crud.get_active_sprint", return_value=fake_sprint):
            resp = client.get(
                "/teams/1/current-sprint-token",
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "sprint_token" in data
        assert data["sprint_number"] == 2

    def test_returns_404_when_no_active_sprint(self):
        with patch("app.crud.user_crud.get_user_by_email", return_value=employee_user), \
             patch("app.routers.questionnaire_router.team_crud.get_team_by_id", return_value=mock_team), \
             patch("app.routers.questionnaire_router.questionnaire_crud.get_active_sprint", return_value=None):
            resp = client.get(
                "/teams/1/current-sprint-token",
                headers={"Authorization": f"Bearer {_token(employee_user)}"},
            )
        assert resp.status_code == 404
