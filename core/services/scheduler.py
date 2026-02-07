"""
Scheduler Service - Programmatic management of dynamic cron jobs.
"""

import logging
import subprocess
import os
from django.core.management import call_command
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Manages the lifecycle of dynamic cron jobs using django-crontab.
    """

    async def sync_crontab(self):
        """
        Synchronize the database CronJob entries with the system crontab.
        """
        logger.info("Synchronizing system crontab with SecureAssist registry...")

        try:
            # We use 'crontab add' which reads CRONJOBS from settings.
            # However, since ORM-based jobs are dynamic, we need a bridge.
            # For now, we manually update the system crontab or use a dedicated
            # task runner.

            # Simple approach: In the management command 'run_bot' or 'run_scheduler',
            # we periodically check for new CronJob entries.

            # For direct crontab manipulation:
            await sync_to_async(call_command)("crontab", "add")
            logger.info("Crontab successfully updated.")
            return True
        except Exception as e:
            logger.error(f"Failed to sync crontab: {e}")
            return False

    async def add_job(
        self,
        user_id: str,
        name: str,
        cron_expression: str,
        tool_name: str,
        parameters: dict,
    ):
        """Add a new dynamic job."""
        from core.models import CronJob

        if not user_id:
            raise ValueError("user_id is required to create a cron job")

        job = await CronJob.objects.acreate(
            user_id=user_id,
            name=name,
            cron_expression=cron_expression,
            tool_name=tool_name,
            parameters=parameters,
        )
        logger.info(f"New job registered: {name} ({cron_expression})")

        # In a real environment, we'd trigger a crontab sync here
        await self.sync_crontab()
        return job


scheduler_service = SchedulerService()
