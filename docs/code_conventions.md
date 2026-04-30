# Code Conventions

> See `docs/backend_architecture.md` for auth/RBAC implementation reference.

## Language & Runtime

- Python 3.12 (`runtime.txt`)
- No JavaScript/TypeScript — this is a backend-only repo

## Linting & Formatting

No linter or formatter config exists in the repo yet. Do not manually reformat code.

Recommended setup (not yet added):
```bash
pip install black pylint
black app/ tests/          # auto-format
pylint app/                # lint
```

If you add these, create a `pyproject.toml` with black and pylint config.

## Pydantic v2 Patterns

Use `model_config = ConfigDict(from_attributes=True)` — **not** the old `class Config`:

```python
from pydantic import BaseModel
from pydantic import ConfigDict

class UserInDB(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
```

Use `Literal` for enums in models:
```python
role: Literal["manager", "employee"]
```

## Router Pattern

Standard endpoint signature:
```python
@router.post("/", response_model=SomePydanticModel)
def create_something(
    body: InputModel,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    ...
```

Always use `Annotated[UserInDB, Depends(...)]` for the current user dependency.

## Error Handling

Use pre-built exceptions from `app/utils/constants.py` — **raise them directly**, don't construct new `HTTPException`:

```python
from app.utils.constants import Errors, Messages

raise Errors.NO_PERMISSION       # 403
raise Errors.NOT_FOUND           # 404
raise Errors.INVALID_PARAMS      # 422
raise Errors.INCORRECT_CREDENTIALS  # 404
raise Errors.EMAIL_ALREADY_EXISTS   # 400

return Messages.USER_DELETE      # {"message": "Used deleted"}
```

## RBAC Checks

Use auth_utils helpers for team access — don't inline the logic:

```python
from app.core.auth_utils import ensure_is_team_manager, ensure_is_team_member_or_manager

ensure_is_team_manager(team, current_user)           # raises 403 if not manager
ensure_is_team_member_or_manager(team, current_user) # raises 403 if not member or manager
```

Role constants from `app/utils/constants.py`:
```python
from app.utils.constants import Role

if current_user.role != Role.MANAGER:
    raise Errors.NO_PERMISSION
```

## Logging

Use the project logger — don't use `print`:

```python
from app.utils.logger import logger

logger.debug("Call to create team")
logger.info("User created: %s", user.id)
logger.error("Failed to update: %s", error)
```

## Project Structure Convention

```
app/
├── routers/     # FastAPI route handlers (thin — delegate to crud/)
├── crud/        # DB access logic (SQLAlchemy queries)
├── models/      # Pydantic request/response models
├── schemas/     # SQLAlchemy ORM table definitions
├── services/    # Business logic / external integrations
├── core/        # Shared utilities (auth_utils)
└── utils/       # Constants, logger
```

Routers stay thin. Business logic goes in `crud/` or `services/`. ORM definitions live in `schemas/`, never in `models/`.
