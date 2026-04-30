from datetime import datetime, timedelta, timezone

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.databases.postgres_database import SessionLocal
from app.crud import reports_crud, team_crud
from app.services.slack_service import (
    build_weekly_report_blocks,
    build_no_data_blocks,
    build_reminder_blocks,
    build_unreachable_notification_blocks,
    resolve_slack_user,
    send_dm,
)
from app.utils.logger import logger


async def send_weekly_reports():
    """
    Sends weekly mood report DM to the manager of each team with a bot token.
    Runs every Monday at 09:00 UTC.
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
            if not team.slack_bot_token:
                logger.debug(f"Team {team.id} ({team.name!r}) has no Slack bot token. Skipping.")
                continue

            try:
                manager_slack_id = await resolve_slack_user(team.slack_bot_token, team.manager)
                if not manager_slack_id:
                    logger.error(
                        f"Cannot resolve Slack user for manager of team {team.id}. Skipping report."
                    )
                    continue

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

                success = await send_dm(team.slack_bot_token, manager_slack_id, blocks)
                if success:
                    logger.debug(f"Slack report DM sent for team {team.id} ({team.name!r}).")
                else:
                    logger.warning(f"Slack report DM FAILED for team {team.id} ({team.name!r}).")

            except Exception as exc:
                logger.error(
                    f"Error generating/sending report for team {team.id} ({team.name!r}): {exc}",
                    exc_info=True,
                )
    finally:
        db.close()


async def send_weekly_reminders():
    """
    Sends weekly reminder DM to all members of teams with a bot token.
    Notifies the manager if any members could not be reached.
    Runs every Friday at 16:00 UTC.
    """
    db = SessionLocal()
    try:
        teams = team_crud.get_all_teams(db)
        logger.debug(f"Weekly reminder job started. Processing {len(teams)} teams.")

        for team in teams:
            if not team.slack_bot_token:
                logger.debug(f"Team {team.id} ({team.name!r}) has no Slack bot token. Skipping.")
                continue

            try:
                unreachable = []
                reminder_blocks = build_reminder_blocks()

                for member in team.members:
                    slack_id = await resolve_slack_user(team.slack_bot_token, member)
                    if slack_id:
                        success = await send_dm(team.slack_bot_token, slack_id, reminder_blocks)
                        if not success:
                            logger.warning(f"Failed to send reminder DM to {member.email}")
                    else:
                        unreachable.append(member.email)

                if unreachable:
                    manager_slack_id = await resolve_slack_user(team.slack_bot_token, team.manager)
                    if manager_slack_id:
                        notification_blocks = build_unreachable_notification_blocks(unreachable)
                        await send_dm(team.slack_bot_token, manager_slack_id, notification_blocks)
                    else:
                        logger.error(
                            f"Manager of team {team.id} is also unreachable. "
                            f"Cannot send unreachable notification."
                        )

            except Exception as exc:
                logger.error(
                    f"Error sending reminders for team {team.id} ({team.name!r}): {exc}",
                    exc_info=True,
                )
    finally:
        db.close()


def create_scheduler() -> AsyncIOScheduler:
    """
    Creates and configures the APScheduler instance with two jobs:
    - Weekly report: every Monday at 09:00 UTC (managers)
    - Weekly reminder: every Friday at 16:00 UTC (team members)
    """
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        send_weekly_reports,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=pytz.UTC),
        id="weekly_slack_report",
        name="Weekly Slack Mood Report",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        send_weekly_reminders,
        CronTrigger(day_of_week="fri", hour=16, minute=0, timezone=pytz.UTC),
        id="weekly_slack_reminder",
        name="Weekly Slack Mood Reminder",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    return scheduler
