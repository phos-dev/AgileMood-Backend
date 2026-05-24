import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["teams"])

ZIP_PATH = "app/static/teams/teams-app.zip"


@router.get("/integrations/teams/app")
def download_teams_app():
    if not os.path.isfile(ZIP_PATH):
        raise HTTPException(status_code=404, detail="Teams app package not found.")
    return FileResponse(
        path=ZIP_PATH,
        media_type="application/zip",
        filename="teams-app.zip",
    )
