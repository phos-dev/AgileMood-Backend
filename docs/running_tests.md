# Running Tests

## Framework & Approach

- **Runner:** pytest
- **Client:** `fastapi.testclient.TestClient` (synchronous, wraps the ASGI app)
- **Mocking:** `unittest.mock` — `patch`, `MagicMock`, `AsyncMock`
- **DB:** No live database required — CRUD functions are mocked at the module level
- **Slack:** `httpx.AsyncClient.post` is mocked — no actual webhook calls

## Test Files

```
tests/
├── user_tests.py              # User registration, login, get/update/delete
├── emotion_record_tests.py    # Emotion record submission, retrieval, anonymity
├── team_tests.py              # Team CRUD, member management, RBAC checks
└── slack_tests.py             # Webhook config, report building, send logic
```

Standalone root-level files (legacy, not in `tests/`):
- `test_anonymity_fix.py`
- `test_manager_bug_fix.py`
- `test_team_emotion_isolation.py`

## Commands

```bash
# Run all tests
pytest tests/ -v

# Run a specific file
pytest tests/slack_tests.py -v

# Run a specific test function
pytest tests/slack_tests.py::test_manager_can_set_slack_webhook -v

# With coverage report
pytest tests/ --cov=app --cov-report=html

# Run standalone files
pytest test_anonymity_fix.py -v
```

## Test Pattern

Tests follow a consistent mock-and-assert pattern:

```python
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.routers.authentication import create_access_token

client = TestClient(app)

def test_manager_can_set_slack_bot_token():
    token = create_access_token({"sub": "manager@example.com"})
    with patch("app.crud.user_crud.get_user_by_email", return_value=mock_manager), \
         patch("app.routers.team_router.team_crud.get_team_by_id", return_value=mock_team), \
         patch("app.routers.team_router.team_crud.update_slack_bot_token", return_value=mock_team_orm):
        response = client.put(
            "/teams/1/slack-bot-token",
            json={"slack_bot_token": "xoxb-test"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
```

Key points:
- Patch the CRUD function at the **router's import path**, not the source module
- Use `create_access_token` directly to generate valid test tokens — no need to call `/user/login`
- For async Slack tests, mock `httpx.AsyncClient` or the `send_dm` function
- `manager_knows_identity` in feedback responses depends on the mocked record's `is_anonymous` value

## What Is NOT Tested Here

- Database migrations (Alembic — test manually or in a staging environment)
- Scheduler timing (APScheduler job trigger — verify by mocking `send_weekly_reports` and calling directly)
- Actual Slack delivery (always mocked)
