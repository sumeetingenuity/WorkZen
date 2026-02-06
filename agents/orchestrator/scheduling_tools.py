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
    category="system"
)
async def schedule_task(
    name: str,
    cron_expression: str,
    action_description: str,
    _user_id: str = None
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
        parameters={"message": action_description}
    )
    
    return {
        "status": "scheduled",
        "job_id": str(job.id),
        "name": name,
        "schedule": cron_expression
    }

@agent_tool(
    name="list_scheduled_tasks",
    description="List all active scheduled tasks and reminders for the current user.",
    category="system"
)
async def list_scheduled_tasks(_user_id: str = None):
    """Lists active cron jobs for the user."""
    jobs = []
    async for job in CronJob.objects.filter(user_id=_user_id, is_active=True):
        jobs.append({
            "id": str(job.id),
            "name": job.name,
            "schedule": job.cron_expression,
            "created_at": job.created_at.isoformat()
        })
    
    return {"scheduled_tasks": jobs}

@agent_tool(
    name="cancel_task",
    description="Cancel a scheduled task by name or ID.",
    category="system"
)
async def cancel_task(name_or_id: str, _user_id: str = None):
    """Deactivates a scheduled job."""
    from django.db.models import Q
    
    try:
        # Try as ID first
        job = await CronJob.objects.aget(Q(id=name_or_id) | Q(name=name_or_id), user_id=_user_id)
        job.is_active = False
        await job.asave()
        await scheduler_service.sync_crontab()
        return {"status": "cancelled", "job": job.name}
    except CronJob.DoesNotExist:
        return {"status": "error", "message": f"Task '{name_or_id}' not found."}
