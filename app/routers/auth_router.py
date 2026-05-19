import os

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.databases.postgres_database import get_db
from app.crud import team_crud
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/teams/callback")
def teams_oauth_callback(
    tenant: str,
    state: str,
    db: Session = Depends(get_db),
):
    """
    Receives the Microsoft admin consent callback.
    Stores the tenant_id for the team identified by state parameter.
    """
    try:
        team_id = int(state)
    except ValueError:
        logger.error(f"Invalid state parameter in Teams callback: {state!r}")
        frontend_url = os.environ.get("FRONTEND_URL", "/")
        return RedirectResponse(f"{frontend_url}?teams_error=invalid_state")

    result = team_crud.update_teams_tenant_id(db, team_id, tenant)
    frontend_url = os.environ.get("FRONTEND_URL", "/")
    if result is None:
        logger.error(f"Teams callback: team {team_id} not found.")
        return RedirectResponse(f"{frontend_url}?teams_error=team_not_found")

    logger.debug(f"Teams connected for team {team_id} (tenant={tenant}).")
    return RedirectResponse(f"{frontend_url}?teams_connected=true")
