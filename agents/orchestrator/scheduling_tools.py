"""
Scheduling Tools - Agent-callable tools for managing background tasks.
"""

import logging
from core.decorators import agent_tool
from core.services.scheduler import scheduler_service
from core.models import CronJob

logger = logging.getLogger(__name__)


@agent_tool(
    name="schedule_task",
    description="Schedule a recurring task or reminder using cron expression. Example: '0 8 * * *' for daily at 8am.",
    category="system",
)
async def schedule_task(
    name: str, cron_expression: str, action_description: str, _user_id: str = None, _session_id: str = None
):
    """
    Schedules a dynamic task.
    Note: In this version, we log the intent to CronJob model.
    """
    job = await scheduler_service.add_job(
        user_id=_user_id,
        name=name,
        cron_expression=cron_expression,
        tool_name="notify_user",  # Default action
        parameters={"message": action_description},
    )

    return {
        "status": "scheduled",
        "job_id": str(job.id),
        "name": name,
        "schedule": cron_expression,
        "display_markdown": f"✅ **Task Scheduled Successfully**\n\n**Name:** {name}\n**Schedule:** `{cron_expression}`\n**Action:** {action_description}\n**Job ID:** `{job.id}`"
    }


@agent_tool(
    name="list_scheduled_tasks",
    description="List all active scheduled tasks and reminders for the current user.",
    category="system",
)
async def list_scheduled_tasks(_user_id: str = None, _session_id: str = None):
    """Lists active cron jobs for the user."""
    if not _user_id:
        logger.error(f"list_scheduled_tasks called without _user_id. Session: {_session_id}")
        return {
            "status": "error",
            "error": "user_id is required to list scheduled tasks",
            "hint": "This is an internal error - the orchestrator should provide user_id automatically."
        }

    jobs = []
    async for job in CronJob.objects.filter(user_id=_user_id, is_active=True):
        jobs.append(
            {
                "id": str(job.id),
                "name": job.name,
                "schedule": job.cron_expression,
                "created_at": job.created_at.isoformat(),
            }
        )

    if not jobs:
        return {
            "status": "success",
            "display_markdown": "📋 You have no scheduled tasks.\n\nUse `schedule_task()` to create recurring tasks."
        }

    response = "📋 **Your Scheduled Tasks:**\n\n"
    for job in jobs:
        response += f"• **{job['name']}** - `{job['schedule']}`\n"
        response += f"  ID: `{job['id']}`\n"
        response += f"  Created: {job['created_at']}\n\n"

    return {
        "status": "success",
        "display_markdown": response,
        "scheduled_tasks": jobs
    }


@agent_tool(
    name="cancel_task",
    description="Cancel a scheduled task by name or ID.",
    category="system",
)
async def cancel_task(name_or_id: str, _user_id: str = None, _session_id: str = None):
    """Deactivates a scheduled job."""
    from django.db.models import Q

    if not _user_id:
        raise ValueError("user_id is required to cancel a task")

    try:
        # Try as ID first
        job = await CronJob.objects.aget(
            Q(id=name_or_id) | Q(name=name_or_id), user_id=_user_id
        )
        job.is_active = False
        await job.asave()
        await scheduler_service.sync_crontab()
        return {"status": "cancelled", "job": job.name}
    except CronJob.DoesNotExist:
        return {"status": "error", "message": f"Task '{name_or_id}' not found."}
