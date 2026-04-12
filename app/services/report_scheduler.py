from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from app.databases.postgres_database import SessionLocal
from app.crud import reports_crud, team_crud
from app.services.slack_service import (
    build_weekly_report_blocks,
    build_no_data_blocks,
)
from app.utils.logger import logger
import pytz


async def send_weekly_reports():
    """
    Iterates all teams, fetches 7-day reports, and sends to Slack if configured.
    Runs as a scheduled job — no HTTP request context.
    """
    db = SessionLocal()
    try:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        teams = team_crud.get_all_teams(db)
        logger.debug(f"Weekly Slack report job started. Processing {len(teams)} teams.")

        for team in teams:
            if not team.slack_webhook_url:
                logger.debug(f"Team {team.id} ({team.name!r}) has no Slack webhook. Skipping.")
                continue

            try:
                emoji_report = reports_crud.get_emoji_distribution_report(
                    db, team.id, start_str, end_str
                )
                intensity_report = reports_crud.get_average_intensity_report(
                    db, team.id, start_str, end_str
                )
                anonymous_report = reports_crud.get_anonymous_emotion_analysis(
                    db, team.id, start_str, end_str
                )

                if not emoji_report.emoji_distribution:
                    blocks = build_no_data_blocks(team.name, start_str, end_str)
                else:
                    blocks = build_weekly_report_blocks(
                        team_name=team.name,
                        start_date=start_str,
                        end_date=end_str,
                        emoji_report=emoji_report,
                        intensity_report=intensity_report,
                        anonymous_report=anonymous_report,
                    )

                success = await send_slack_report(team.slack_webhook_url, blocks)
                if success:
                    logger.debug(f"Slack report sent for team {team.id} ({team.name!r}).")
                else:
                    logger.warning(f"Slack report FAILED for team {team.id} ({team.name!r}).")

            except Exception as exc:
                logger.error(
                    f"Error generating/sending report for team {team.id} ({team.name!r}): {exc}",
                    exc_info=True,
                )

    finally:
        db.close()


def create_scheduler() -> AsyncIOScheduler:
    """
    Creates and configures the APScheduler instance.
    Trigger: every Monday at 09:00 UTC.
    """
    send_weekly_reports()
    scheduler = AsyncIOScheduler()
    run_time = datetime.now(pytz.UTC) + timedelta(seconds=20)
    scheduler.add_job(
        send_weekly_reports,
        DateTrigger(run_date=run_time),
        id="weekly_slack_report",
        name="Weekly Slack Mood Report",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    print("Adding job weekly_slack_report")
    return scheduler

