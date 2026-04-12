from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.utils.logger import logger
import pytz


async def send_weekly_reports():
    """
    Sends weekly mood report DM to the manager of each team with a bot token.
    NOTE: Full implementation is in Task 8. This stub prevents NameError during migration.
    """
    logger.debug("send_weekly_reports: stub — will be implemented in Task 8 (bot DM migration).")


def create_scheduler() -> AsyncIOScheduler:
    """
    Creates and configures the APScheduler instance.
    Trigger: every Monday at 09:00 UTC.
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
    logger.debug("Scheduler configured: weekly_slack_report (Mon 09:00 UTC)")
    return scheduler

