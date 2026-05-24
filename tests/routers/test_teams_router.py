import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app

client = TestClient(app)

ZIP_PATH = "app/static/teams/teams-app.zip"


def test_download_teams_app_returns_zip(tmp_path):
    fake_zip = tmp_path / "teams-app.zip"
    fake_zip.write_bytes(b"PK\x03\x04fake-zip-content")

    with patch("app.routers.teams_router.ZIP_PATH", str(fake_zip)):
        response = client.get("/integrations/teams/app")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "teams-app.zip" in response.headers.get("content-disposition", "")


def test_download_teams_app_missing_file(tmp_path):
    with patch("app.routers.teams_router.ZIP_PATH", str(tmp_path / "missing.zip")):
        response = client.get("/integrations/teams/app")

    assert response.status_code == 404
