import asyncio
import random
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
from app.services.teams_service import (
    build_weekly_report_card,
    build_no_data_card,
    build_reminder_card,
    build_unreachable_notification_card,
    resolve_teams_user,
    get_bot_token,
    send_dm as teams_send_dm,
)
from app.schemas.team_schema import Team
from app.services.planner_service import renew_graph_subscription
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


async def send_weekly_teams_reports():
    """
    Sends weekly mood report Adaptive Card DM to the manager of each team with a Teams tenant_id.
    Runs every Monday at 09:00 UTC.
    """
    db = SessionLocal()
    try:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=7)
        start_str = start_date.isoformat()
        end_str = end_date.isoformat()

        try:
            bot_token = await get_bot_token()
        except Exception as exc:
            logger.error(f"Failed to get Teams bot token: {exc}", exc_info=True)
            return

        teams = team_crud.get_all_teams(db)
        logger.debug(f"Weekly Teams report job started. Processing {len(teams)} teams.")

        for team in teams:
            if not team.teams_tenant_id:
                logger.debug(f"Team {team.id} ({team.name!r}) has no Teams tenant ID. Skipping.")
                continue

            try:
                manager_teams_id = await resolve_teams_user(team.teams_tenant_id, team.manager)
                if not manager_teams_id:
                    logger.error(f"Cannot resolve Teams user for manager of team {team.id}. Skipping report.")
                    continue

                emoji_report = reports_crud.get_emoji_distribution_report(db, team.id, start_str, end_str)
                intensity_report = reports_crud.get_average_intensity_report(db, team.id, start_str, end_str)
                anonymous_report = reports_crud.get_anonymous_emotion_analysis(db, team.id, start_str, end_str)

                if not emoji_report.emoji_distribution:
                    card = build_no_data_card(team.name, start_str, end_str)
                else:
                    card = build_weekly_report_card(
                        team_name=team.name,
                        start_date=start_str,
                        end_date=end_str,
                        emoji_report=emoji_report,
                        intensity_report=intensity_report,
                        anonymous_report=anonymous_report,
                    )

                success = await teams_send_dm(bot_token, team.teams_tenant_id, manager_teams_id, card)
                if success:
                    logger.debug(f"Teams report DM sent for team {team.id} ({team.name!r}).")
                else:
                    logger.warning(f"Teams report DM FAILED for team {team.id} ({team.name!r}).")

            except Exception as exc:
                logger.error(
                    f"Error generating/sending Teams report for team {team.id} ({team.name!r}): {exc}",
                    exc_info=True,
                )
    finally:
        db.close()


async def send_weekly_teams_reminders():
    """
    Sends weekly reminder Adaptive Card DM to all members of teams with a Teams tenant_id.
    Notifies the manager if any members could not be reached.
    Runs every Friday at 16:00 UTC.
    """
    db = SessionLocal()
    try:
        try:
            bot_token = await get_bot_token()
        except Exception as exc:
            logger.error(f"Failed to get Teams bot token: {exc}", exc_info=True)
            return

        teams = team_crud.get_all_teams(db)
        logger.debug(f"Weekly Teams reminder job started. Processing {len(teams)} teams.")

        for team in teams:
            if not team.teams_tenant_id:
                logger.debug(f"Team {team.id} ({team.name!r}) has no Teams tenant ID. Skipping.")
                continue

            try:
                unreachable = []
                reminder_card = build_reminder_card()

                for member in team.members:
                    member_teams_id = await resolve_teams_user(team.teams_tenant_id, member)
                    if member_teams_id:
                        success = await teams_send_dm(bot_token, team.teams_tenant_id, member_teams_id, reminder_card)
                        if not success:
                            logger.warning(f"Failed to send Teams reminder DM to {member.email}")
                    else:
                        unreachable.append(member.email)
                    # Bot Framework rate-limit mitigation
                    await asyncio.sleep(random.uniform(0.1, 0.5))

                if unreachable:
                    manager_teams_id = await resolve_teams_user(team.teams_tenant_id, team.manager)
                    if manager_teams_id:
                        notification_card = build_unreachable_notification_card(unreachable)
                        await teams_send_dm(bot_token, team.teams_tenant_id, manager_teams_id, notification_card)
                    else:
                        logger.error(
                            f"Manager of team {team.id} is also unreachable. "
                            f"Cannot send Teams unreachable notification."
                        )

            except Exception as exc:
                logger.error(
                    f"Error sending Teams reminders for team {team.id} ({team.name!r}): {exc}",
                    exc_info=True,
                )
    finally:
        db.close()


async def send_sprint_end_reminder_teams(team_id: int) -> None:
    db = SessionLocal()
    try:
        team = db.query(Team).filter(Team.id == team_id).first()
        if not team or not team.teams_tenant_id:
            return
        bot_token = await get_bot_token()
        card = build_reminder_card()
        for member in team.members:
            teams_user_id = await resolve_teams_user(team.teams_tenant_id, member)
            if teams_user_id:
                await teams_send_dm(bot_token, team.teams_tenant_id, teams_user_id, card)
    except Exception as e:
        logger.error(f"send_sprint_end_reminder_teams failed for team {team_id}: {e}")
    finally:
        db.close()


async def renew_all_planner_subscriptions() -> None:
    db = SessionLocal()
    try:
        teams = team_crud.get_all_teams(db)
        for team in teams:
            if team.planner_subscription_id and team.teams_tenant_id:
                success = await renew_graph_subscription(team.teams_tenant_id, team.planner_subscription_id)
                if not success:
                    logger.warning(f"Could not renew Planner subscription for team {team.id}")
    except Exception as e:
        logger.error(f"Planner subscription renewal error: {e}")
    finally:
        db.close()


def create_scheduler() -> AsyncIOScheduler:
    """
    Creates and configures the APScheduler instance with four jobs:
    - Weekly report: every Monday at 09:00 UTC (managers)
    - Weekly reminder: every Friday at 16:00 UTC (team members)
    - Weekly Teams report: every Monday at 09:00 UTC (managers)
    - Weekly Teams reminder: every Friday at 16:00 UTC (team members)
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

    scheduler.add_job(
        send_weekly_teams_reports,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=pytz.UTC),
        id="weekly_teams_report",
        name="Weekly Teams Mood Report",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        send_weekly_teams_reminders,
        CronTrigger(day_of_week="fri", hour=16, minute=0, timezone=pytz.UTC),
        id="weekly_teams_reminder",
        name="Weekly Teams Mood Reminder",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        renew_all_planner_subscriptions,
        "interval",
        hours=48,
        id="renew_planner_subscriptions",
        misfire_grace_time=3600,
    )

    return scheduler
