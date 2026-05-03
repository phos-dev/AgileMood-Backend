import os
import logging
import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE          = "https://graph.microsoft.com/v1.0"
GRAPH_TOKEN_URL         = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
BOT_FRAMEWORK_TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
BOT_FRAMEWORK_BASE      = "https://smba.trafficmanager.net/apis"
REQUEST_TIMEOUT         = 10

ALERT_EMOJI_MAP = {
    "critical": "🔴",
    "warning":  "🟡",
    "note":     "🔵",
    "ok":       "🟢",
}

ALERT_LABEL_MAP = {
    "critical": "Crítico",
    "warning":  "Atenção",
    "note":     "Observação",
    "ok":       "Normal",
}


def _classify_alert(negative_ratio: float) -> str:
    if negative_ratio > 50:
        return "critical"
    if negative_ratio > 30:
        return "warning"
    if negative_ratio > 15:
        return "note"
    return "ok"


async def get_graph_token(tenant_id: str) -> str:
    """
    Obtains an OAuth2 access token for the Microsoft Graph API.
    Raises on any error — callers are responsible for catching.
    """
    url = GRAPH_TOKEN_URL.format(tenant_id=tenant_id)
    data = {
        "grant_type":    "client_credentials",
        "client_id":     os.environ["TEAMS_APP_ID"],
        "client_secret": os.environ["TEAMS_APP_SECRET"],
        "scope":         "https://graph.microsoft.com/.default",
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, data=data)
        response.raise_for_status()
        return response.json()["access_token"]


async def get_bot_token() -> str:
    """
    Obtains an OAuth2 access token for the Bot Framework Connector API.
    Raises on any error — callers are responsible for catching.
    """
    data = {
        "grant_type":    "client_credentials",
        "client_id":     os.environ["TEAMS_APP_ID"],
        "client_secret": os.environ["TEAMS_APP_SECRET"],
        "scope":         "https://api.botframework.com/.default",
    }
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(BOT_FRAMEWORK_TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()["access_token"]


async def resolve_teams_user(tenant_id: str, user) -> str | None:
    """
    Resolves an AAD Object ID for an AgileMood user.
    1. Tries Graph API lookup by email.
    2. Falls back to user.teams_user_id (manual override) if set.
    3. Returns None if unresolvable.
    Never raises.
    """
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            token_resp = await client.post(
                GRAPH_TOKEN_URL.format(tenant_id=tenant_id),
                data={
                    "grant_type":    "client_credentials",
                    "client_id":     os.environ["TEAMS_APP_ID"],
                    "client_secret": os.environ["TEAMS_APP_SECRET"],
                    "scope":         "https://graph.microsoft.com/.default",
                },
            )
            token_resp.raise_for_status()
            graph_token = token_resp.json()["access_token"]

            user_resp = await client.get(
                f"{GRAPH_API_BASE}/users/{user.email}",
                headers={"Authorization": f"Bearer {graph_token}"},
            )
            user_resp.raise_for_status()
            return user_resp.json()["id"]
    except Exception as exc:
        logger.warning(f"Graph API lookup failed for {user.email}: {exc}")

    override = getattr(user, "teams_user_id", None)
    if override:
        return override

    logger.warning(
        f"Cannot resolve Teams user for {user.email}. No manual override set."
    )
    return None


async def send_dm(
    bot_token: str,
    tenant_id: str,
    teams_user_id: str,
    card: dict,
) -> bool:
    """
    Sends a proactive DM to a Teams user via the Bot Framework Connector REST API.
    Returns True on success, False on any failure. Never raises.
    """
    app_id = os.environ.get("TEAMS_APP_ID", "")
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type":  "application/json",
    }
    conversation_payload = {
        "bot":         {"id": f"28:{app_id}", "name": "AgileMood"},
        "members":     [{"id": f"29:{teams_user_id}"}],
        "channelData": {"tenant": {"id": tenant_id}},
        "isGroup":     False,
        "tenantId":    tenant_id,
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            conv_resp = await client.post(
                f"{BOT_FRAMEWORK_BASE}/v3/conversations",
                json=conversation_payload,
                headers=headers,
            )
            conv_resp.raise_for_status()
            conversation_id = conv_resp.json()["id"]

            activity_payload = {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content":     card,
                    }
                ],
            }
            act_resp = await client.post(
                f"{BOT_FRAMEWORK_BASE}/v3/conversations/{conversation_id}/activities",
                json=activity_payload,
                headers=headers,
            )
            act_resp.raise_for_status()
            return True
    except httpx.TimeoutException as exc:
        logger.error(f"Teams DM timed out for user {teams_user_id}: {exc}")
        return False
    except httpx.RequestError as exc:
        logger.error(f"Teams DM request failed for user {teams_user_id}: {exc}")
        return False
    except Exception as exc:
        logger.error(f"Teams DM failed for user {teams_user_id}: {exc}")
        return False


# ---------------------------------------------------------------------------
# Adaptive Card builders
# ---------------------------------------------------------------------------

def build_weekly_report_card(
    team_name: str,
    start_date: str,
    end_date: str,
    emoji_report,
    intensity_report: dict,
    anonymous_report: dict,
) -> dict:
    """
    Builds an Adaptive Card for the weekly team mood report.
    Contains only team-level aggregates — no per-user data.
    """
    negative_ratio = emoji_report.negative_emotion_ratio
    alert_level    = _classify_alert(negative_ratio)
    alert_emoji    = ALERT_EMOJI_MAP[alert_level]
    alert_label    = ALERT_LABEL_MAP[alert_level]

    body = [
        {
            "type":   "TextBlock",
            "text":   f"Relatório de Humor Semanal — {team_name}",
            "weight": "Bolder",
            "size":   "Large",
            "wrap":   True,
        },
        {
            "type":  "TextBlock",
            "text":  f"Período: {start_date} → {end_date}",
            "wrap":  True,
        },
        {
            "type":  "TextBlock",
            "text":  f"Nível de Alerta: {alert_emoji} {alert_label}",
            "wrap":  True,
        },
    ]

    # Emotion frequency distribution
    dist_rows = emoji_report.emoji_distribution[:10]
    if dist_rows:
        body.append({
            "type":   "TextBlock",
            "text":   "Distribuição de Frequência de Emoções:",
            "weight": "Bolder",
            "wrap":   True,
        })
        for row in dist_rows:
            body.append({
                "type": "TextBlock",
                "text": f"• {row.emotion_name}: {row.frequency} registros",
                "wrap": True,
            })
        body.append({
            "type": "TextBlock",
            "text": f"Taxa de Emoções Negativas: {negative_ratio:.1f}%",
            "wrap": True,
        })

    # Average intensity
    intensity_rows = intensity_report.get("average_intensity", [])[:10]
    if intensity_rows:
        body.append({
            "type":   "TextBlock",
            "text":   "Intensidade Média por Emoção:",
            "weight": "Bolder",
            "wrap":   True,
        })
        for row in intensity_rows:
            body.append({
                "type": "TextBlock",
                "text": f"• {row['emotion_name']}: intensidade média de {row['avg_intensity']:.1f}",
                "wrap": True,
            })

    # Anonymous records
    anon_rows = anonymous_report.get("all_user_emotion_records", [])[:10]
    body.append({
        "type":   "TextBlock",
        "text":   "Resumo de Registros Anônimos:",
        "weight": "Bolder",
        "wrap":   True,
    })
    if anon_rows:
        for row in anon_rows:
            body.append({
                "type": "TextBlock",
                "text": f"• {row['emotion_name']}: {row['frequency']} vezes, intensidade média de {row['avg_intensity']}",
                "wrap": True,
            })
    else:
        body.append({
            "type": "TextBlock",
            "text": "Nenhum registro anônimo nesta semana.",
            "wrap": True,
        })

    # Privacy footer
    body.append({
        "type":      "TextBlock",
        "text":      "🛡️ Este relatório não contém dados individuais. Todas as estatísticas são agregados do time.",
        "wrap":      True,
        "isSubtle":  True,
        "size":      "Small",
    })

    return {
        "type":    "AdaptiveCard",
        "version": "1.3",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body":    body,
    }


def build_no_data_card(team_name: str, start_date: str, end_date: str) -> dict:
    """
    Minimal Adaptive Card when no emotion data was recorded in the period.
    """
    return {
        "type":    "AdaptiveCard",
        "version": "1.3",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {
                "type":   "TextBlock",
                "text":   f"Relatório de Humor Semanal — {team_name}",
                "weight": "Bolder",
                "size":   "Large",
                "wrap":   True,
            },
            {
                "type": "TextBlock",
                "text": f"Período: {start_date} → {end_date}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": (
                    "Nenhum registro de emoção foi enviado esta semana. "
                    "Incentive sua equipe a fazer o check-in!"
                ),
                "wrap": True,
            },
        ],
    }


def build_reminder_card() -> dict:
    """
    Adaptive Card for the weekly member reminder DM.
    Contains no mood data.
    """
    return {
        "type":    "AdaptiveCard",
        "version": "1.3",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {
                "type": "TextBlock",
                "text": (
                    "👋 Lembra de registrar como você está se sentindo essa semana "
                    "no AgileMood. Leva menos de 1 minuto."
                ),
                "wrap": True,
            }
        ],
    }


def build_unreachable_notification_card(unreachable_emails: list[str]) -> dict:
    """
    Adaptive Card notifying the manager that some members could not be reached.
    """
    email_lines = "\n".join(f"• {email}" for email in unreachable_emails)
    return {
        "type":    "AdaptiveCard",
        "version": "1.3",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "body": [
            {
                "type":   "TextBlock",
                "text":   f"⚠️ {len(unreachable_emails)} membro(s) não receberam mensagem via Teams DM:",
                "weight": "Bolder",
                "wrap":   True,
            },
            {
                "type": "TextBlock",
                "text": email_lines,
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "Configure manualmente via: PUT /users/{id}/teams-user-id",
                "wrap": True,
            },
        ],
    }
