import httpx
from app.utils.logger import logger


ALERT_EMOJI_MAP = {
    "critical": ":red_circle:",
    "warning": ":large_yellow_circle:",
    "note": ":large_blue_circle:",
    "ok": ":large_green_circle:",
}


def _classify_alert(negative_ratio: float) -> str:
    if negative_ratio > 50:
        return "critical"
    if negative_ratio > 30:
        return "warning"
    if negative_ratio > 15:
        return "note"
    return "ok"


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

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Weekly Mood Report — {team_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Period:*\n{start_date} → {end_date}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Alert Level:*\n{alert_emoji} {alert_level.capitalize()}",
                },
            ],
        },
        {"type": "divider"},
    ]

    # Emotion frequency distribution
    dist_rows = emoji_report.emoji_distribution[:10]
    if dist_rows:
        dist_lines = "\n".join(
            f"• *{row.emotion_name}*: {row.frequency} records"
            for row in dist_rows
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Emotion Frequency Distribution:*\n{dist_lines}",
            },
        })
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Negative Emotion Ratio:*\n{negative_ratio:.1f}%",
                },
            ],
        })
        blocks.append({"type": "divider"})

    # Average intensity
    intensity_rows = intensity_report.get("average_intensity", [])[:10]
    if intensity_rows:
        intensity_lines = "\n".join(
            f"• *{row['emotion_name']}*: avg intensity {row['avg_intensity']:.1f}"
            for row in intensity_rows
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Average Intensity per Emotion:*\n{intensity_lines}",
            },
        })
        blocks.append({"type": "divider"})

    # Anonymous submissions
    anon_rows = anonymous_report.get("all_user_emotion_records", [])[:10]
    if anon_rows:
        anon_lines = "\n".join(
            f"• *{row['emotion_name']}*: {row['frequency']} times, avg intensity {row['avg_intensity']}"
            for row in anon_rows
        )
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Anonymous Submissions Summary:*\n{anon_lines}",
            },
        })
    else:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "_No anonymous submissions this week._",
            },
        })

    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": ":shield: This report contains no per-user data. All statistics are team-level aggregates.",
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
                "text": f"Weekly Mood Report — {team_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Period:* {start_date} → {end_date}\n\n"
                    "_No emotion records were submitted this week. "
                    "Encourage your team to check in!_"
                ),
            },
        },
    ]


async def send_slack_report(webhook_url: str, blocks: list[dict]) -> bool:
    """
    POSTs Block Kit payload to a Slack Incoming Webhook URL.
    Returns True on success, False on any failure. Never raises.
    """
    payload = {"blocks": blocks}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code == 200 and response.text == "ok":
                return True
            logger.warning(
                f"Slack webhook unexpected response: "
                f"status={response.status_code} body={response.text!r}"
            )
            return False
    except httpx.TimeoutException:
        logger.error(f"Slack webhook timed out: {webhook_url}")
        return False
    except httpx.RequestError as exc:
        logger.error(f"Slack webhook request failed: {exc}")
        return False
