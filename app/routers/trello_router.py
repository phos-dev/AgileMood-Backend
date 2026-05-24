import base64
import hashlib
import hmac
import json
import os
import time
from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.auth_utils import ensure_is_team_manager
from app.crud import team_crud
from app.databases.postgres_database import get_db
from app.models.team_model import TeamDataSafe, TrelloConnectRequest
from app.routers.authentication import get_current_active_user
from app.models.user_model import UserInDB
from app.services.slack_service import send_sprint_end_reminder
from app.utils.constants import Errors
from app.utils.logger import logger

router = APIRouter(tags=["trello"])

_SEEN_ACTION_IDS: dict[str, float] = {}
_DEDUP_TTL_SECONDS = 60


def _is_duplicate_action(action_id: str) -> bool:
    now = time.time()
    cutoff = now - _DEDUP_TTL_SECONDS
    expired = [k for k, v in _SEEN_ACTION_IDS.items() if v < cutoff]
    for k in expired:
        del _SEEN_ACTION_IDS[k]
    if action_id in _SEEN_ACTION_IDS:
        return True
    _SEEN_ACTION_IDS[action_id] = now
    return False


def _verify_trello_signature(body: bytes, callback_url: str, signature_header: str | None) -> bool:
    """Validate Trello webhook HMAC-SHA1 signature.

    Trello computes: base64(HMAC-SHA1(secret, body + callbackURL))
    """
    secret = os.getenv("TRELLO_API_SECRET", "")
    if not secret:
        return True  # skip validation when secret not configured (dev/test env)
    if not signature_header:
        return False
    digest = hmac.new(secret.encode(), body + callback_url.encode(), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature_header)

_POWERUP_JS = """/* AgileMood Trello Power-Up */
(function () {
  var BASE_URL = window.location.origin;
  var TRELLO_API_KEY = "__TRELLO_API_KEY__";

  TrelloPowerUp.initialize(
    {
      "board-buttons": function (t) {
        return [
          {
            icon: BASE_URL + "/powerup/icon.png",
            text: "Dashboard AgileMood",
            callback: function (t) {
              return t.popup({
                title: "Dashboard de Humor",
                url: BASE_URL + "/powerup/rf03-dashboard.html",
                height: 500,
              });
            },
          },
        ];
      },

      "card-buttons": function (t) {
        return [
          {
            icon: BASE_URL + "/powerup/icon.png",
            text: "Registar Sentimento",
            callback: function (t) {
              return t.popup({
                title: "Registar Sentimento",
                url: BASE_URL + "/powerup/rf06-register.html",
                height: 400,
              });
            },
          },
          {
            icon: BASE_URL + "/powerup/icon.png",
            text: "Mensagens Recebidas",
            callback: function (t) {
              return t.popup({
                title: "Mensagens Recebidas",
                url: BASE_URL + "/powerup/rf07-messages.html",
                height: 400,
              });
            },
          },
        ];
      },

      "show-settings": function (t) {
        return t.popup({
          title: "Configurar AgileMood",
          url: BASE_URL + "/powerup/settings.html",
          height: 300,
        });
      },
    },
    Object.assign(
      { appName: "AgileMood" },
      TRELLO_API_KEY ? { appKey: TRELLO_API_KEY } : {}
    )
  );
})();
"""


@router.get("/icon.png", include_in_schema=False)
def get_powerup_icon():
    """Serves the Power-Up icon at root so the Trello Admin Portal can fetch it."""
    from fastapi.responses import FileResponse
    return FileResponse("app/static/powerup/icon.png", media_type="image/png")


@router.get("/powerup-config.js")
def get_powerup_js():
    """Serves powerup.js with TRELLO_API_KEY injected at runtime. Loaded by index.html."""
    api_key = os.getenv("TRELLO_API_KEY", "")
    js = _POWERUP_JS.replace("__TRELLO_API_KEY__", api_key)
    return Response(content=js, media_type="application/javascript")


@router.post("/integrations/trello/connect", response_model=TeamDataSafe)
def trello_connect(
    team_id: int,
    body: TrelloConnectRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    updated = team_crud.update_trello_token(db, team_id, body.trello_token)
    if updated is None:
        raise Errors.INVALID_PARAMS

    logger.debug(f"Trello integration connected for team {team_id}.")
    return updated


@router.delete("/integrations/trello/disconnect")
def trello_disconnect(
    team_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db: Session = Depends(get_db),
):
    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND

    ensure_is_team_manager(team, current_user)

    team_crud.update_trello_token(db, team_id, None)
    logger.debug(f"Trello integration disconnected for team {team_id}.")
    return {"message": f"Trello integration removed for team {team_id}."}


@router.api_route("/webhooks/trello/sprint-end", methods=["POST", "HEAD"])
async def trello_sprint_end(
    team_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if request.method == "HEAD":
        return Response(status_code=200)

    body = await request.body()
    callback_url = str(request.url)
    signature = request.headers.get("x-trello-webhook")
    if not _verify_trello_signature(body, callback_url, signature):
        raise HTTPException(status_code=401, detail="Invalid Trello webhook signature.")

    team = team_crud.get_team_by_id(db, team_id)
    if not team:
        raise Errors.NOT_FOUND
    team_data = team["team_data"]
    if not team_data.trello_token:
        raise Errors.NOT_FOUND

    try:
        payload = json.loads(body)
    except (ValueError, KeyError):
        return {"message": "Event ignored."}

    action = payload.get("action", {})
    if action.get("type") != "updateCard":
        return {"message": "Event ignored."}

    action_id = action.get("id", "")
    if action_id and _is_duplicate_action(action_id):
        return {"message": "Duplicate event ignored."}

    data = action.get("data", {})
    list_before = data.get("listBefore", {})
    list_after = data.get("listAfter", {})
    if not list_after or list_before.get("id") == list_after.get("id"):
        return {"message": "Event ignored."}

    # Only trigger when the card is moved INTO a completion list
    _DONE_LIST_KEYWORDS = {"done", "concluído", "concluido", "finalizado", "pronto", "encerrado", "fim"}
    list_after_name = list_after.get("name", "").lower()
    if not any(kw in list_after_name for kw in _DONE_LIST_KEYWORDS):
        return {"message": "Event ignored."}

    # Only trigger when the moved card is a sprint-end sentinel
    # (card name must contain "sprint" AND one of the end keywords)
    _SPRINT_END_KEYWORDS = {"fim", "end", "terminou", "encerrado"}
    card_name = data.get("card", {}).get("name", "").lower()
    if "sprint" not in card_name or not any(kw in card_name for kw in _SPRINT_END_KEYWORDS):
        return {"message": "Event ignored."}

    background_tasks.add_task(send_sprint_end_reminder, team_id)
    logger.debug(f"Trello sprint-end webhook received for team {team_id}. Reminder queued.")
    return {"message": "Sprint-end reminder triggered."}
