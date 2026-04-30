import httpx
from app.utils.logger import logger


ALERT_EMOJI_MAP = {
    "critical": ":red_circle:",
    "warning": ":large_yellow_circle:",
    "note": ":large_blue_circle:",
    "ok": ":large_green_circle:",
}

SLACK_API_BASE = "https://slack.com/api"


def _classify_alert(negative_ratio: float) -> str:
    if negative_ratio > 50:
        return "critical"
    if negative_ratio > 30:
        return "warning"
    if negative_ratio > 15:
        return "note"
    return "ok"


async def resolve_slack_user(token: str, user) -> str | None:
    """
    Resolves a Slack user ID for an AgileMood user.
    1. Tries users.lookupByEmail with the user's email.
    2. Falls back to user.slack_user_id (manual override) if set.
    3. Returns None if unresolvable.
    Never raises.
    """
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{SLACK_API_BASE}/users.lookupByEmail",
                params={"email": user.email},
                headers=headers,
            )
            data = response.json()
            if data.get("ok"):
                return data["user"]["id"]
            error = data.get("error", "unknown")
            if error == "missing_scope":
                logger.critical(
                    f"Bot token missing 'users:read.email' scope. "
                    f"Reinstall app with correct scopes."
                )
                return None
            logger.warning(
                f"Slack email lookup failed for {user.email}: {error}"
            )
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.error(f"Slack user lookup request failed: {exc}")

    if getattr(user, "slack_user_id", None):
        return user.slack_user_id

    logger.warning(f"Cannot resolve Slack user for {user.email}. No override set.")
    return None


async def send_dm(token: str, slack_user_id: str, blocks: list[dict]) -> bool:
    """
    Sends a Block Kit DM to a Slack user via chat.postMessage.
    Returns True on success, False on any failure. Never raises.
    """
    payload = {
        "channel": slack_user_id,
        "blocks": blocks,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{SLACK_API_BASE}/chat.postMessage",
                json=payload,
                headers=headers,
            )
            data = response.json()
            if data.get("ok"):
                return True
            logger.warning(
                f"Slack DM failed for user {slack_user_id}: {data.get('error')}"
            )
            return False
    except httpx.TimeoutException:
        logger.error(f"Slack DM timed out for user {slack_user_id}")
        return False
    except httpx.RequestError as exc:
        logger.error(f"Slack DM request failed: {exc}")
        return False


def build_reminder_blocks() -> list[dict]:
    """
    Block Kit payload for the weekly member reminder DM.
    Contains no mood data whatsoever.
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "👋 Lembra de registrar como você está se sentindo essa semana "
                    "no *AgileMood*. Leva menos de 1 minuto."
                ),
            },
        }
    ]


def build_unreachable_notification_blocks(unreachable_emails: list[str]) -> list[dict]:
    """
    Notifies the manager that some members could not be reached via Slack DM.
    """
    email_list = "\n".join(f"• {email}" for email in unreachable_emails)
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"⚠️ {len(unreachable_emails)} membro(s) não receberam lembrete via Slack DM:\n"
                    f"{email_list}\n\n"
                    "Configure manualmente via: `PUT /users/{{id}}/slack-user-id`"
                ),
            },
        }
    ]


def build_weekly_report_blocks(
    team_name: str,
    start_date: str,
    end_date: str,
    emoji_report,
    intensity_report: dict,
    anonymous_report: dict,
) -> list[dict]:
    """
    Builds Slack Block Kit blocks for the weekly team mood report.
    Contains only team-level aggregates — no per-user data.
    """
    negative_ratio = emoji_report.negative_emotion_ratio
    alert_level = _classify_alert(negative_ratio)
    alert_emoji = ALERT_EMOJI_MAP[alert_level]

    # Mapeando os níveis de alerta para português
    alert_translations = {
        "critical": "Crítico",
        "warning": "Atenção",
        "note": "Observação",
        "ok": "Normal"
    }

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Relatório de Humor Semanal — {team_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Período:*\n{start_date} → {end_date}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Nível de Alerta:*\n{alert_emoji} {alert_translations[alert_level]}",
                },
            ],
        },
        {"type": "divider"},
    ]

    dist_rows = emoji_report.emoji_distribution[:10]
    if dist_rows:
        dist_lines = "\n".join(
            f"• *{row.emotion_name}*: {row.frequency} registros"
            for row in dist_rows
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Distribuição de Frequência de Emoções:*\n{dist_lines}",
            },
        })
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Taxa de Emoções Negativas:*\n{negative_ratio:.1f}%",
                },
            ],
        })
        blocks.append({"type": "divider"})

    intensity_rows = intensity_report.get("average_intensity", [])[:10]
    if intensity_rows:
        intensity_lines = "\n".join(
            f"• *{row['emotion_name']}*: intensidade média de {row['avg_intensity']:.1f}"
            for row in intensity_rows
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Intensidade Média por Emoção:*\n{intensity_lines}",
            },
        })
        blocks.append({"type": "divider"})

    anon_rows = anonymous_report.get("all_user_emotion_records", [])[:10]
    if anon_rows:
        anon_lines = "\n".join(
            f"• *{row['emotion_name']}*: {row['frequency']} vezes, intensidade média de {row['avg_intensity']}"
            for row in anon_rows
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Resumo de Registros Anônimos:*\n{anon_lines}",
            },
        })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_Nenhum registro anônimo nesta semana._",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": ":shield: Este relatório não contém dados individuais. Todas as estatísticas são agregadas em nível de time.",
            }
        ],
    })

    return blocks


def build_no_data_blocks(team_name: str, start_date: str, end_date: str) -> list[dict]:
    """
    Minimal Block Kit message when no emotion data was recorded in the period.
    """
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Relatório de Humor Semanal — {team_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Período:* {start_date} → {end_date}\n\n"
                    "_Nenhum registro de emoção foi enviado esta semana. "
                    "Incentive sua equipe a fazer o check-in!_"
                ),
            },
        },
    ]