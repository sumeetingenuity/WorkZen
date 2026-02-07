"""
Reminder Service - Checks for due tasks and sends notifications to users.
"""
import logging
from django.utils import timezone
from datetime import timedelta
from core.models import TaskEntity, CronJob
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class ReminderService:
    """
    Service for checking and executing due reminders and scheduled tasks.
    """
    
    async def check_and_notify_due_tasks(self):
        """
        Check for tasks that are due and send notifications to users.
        This should be called periodically (e.g., every minute via cron).
        """
        now = timezone.now()
        
        # Find tasks that are due (within the last minute to current time)
        # and haven't been completed yet
        one_minute_ago = now - timedelta(minutes=1)
        
        due_tasks = TaskEntity.objects.filter(
            due_date__gte=one_minute_ago,
            due_date__lte=now,
            status='todo'  # Only notify for pending tasks
        )
        
        notification_count = 0
        
        async for task in due_tasks:
            try:
                await self._send_task_notification(task)
                notification_count += 1
                logger.info(f"[REMINDER] Sent notification for task: {task.title} (user: {task.user_id})")
            except Exception as e:
                logger.error(f"[REMINDER] Failed to send notification for task {task.id}: {e}")
        
        if notification_count > 0:
            logger.info(f"[REMINDER] Sent {notification_count} task notifications")
        
        return notification_count
    
    async def _send_task_notification(self, task: TaskEntity):
        """
        Send a notification to the user about a due task.
        """
        try:
            # Import here to avoid circular dependency
            from integrations.telegram_bot.management.commands.run_bot import bot_instance
            
            if not bot_instance:
                logger.warning("[REMINDER] Bot instance not available for notification")
                return
            
            # Extract Telegram user ID from user_id (format: tg_123456789)
            if task.user_id.startswith('tg_'):
                telegram_user_id = task.user_id.replace('tg_', '')
                
                # Format the reminder message
                message = f"""🔔 **Reminder**

📋 **Task:** {task.title}

{f"📝 **Description:** {task.description}" if task.description else ""}

⏰ **Due:** {task.due_date.strftime('%Y-%m-%d %H:%M')}
📌 **Priority:** {task.get_priority_display()}

Use /tasks to view all your tasks."""
                
                # Send the message
                await bot_instance.bot.send_message(
                    chat_id=telegram_user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                
                logger.info(f"[REMINDER] Notification sent to user {telegram_user_id} for task: {task.title}")
            else:
                logger.warning(f"[REMINDER] Unknown user_id format: {task.user_id}")
                
        except Exception as e:
            logger.error(f"[REMINDER] Failed to send notification: {e}")
            raise
    
    async def execute_scheduled_tasks(self):
        """
        Execute scheduled tasks (CronJobs) that are due.
        This checks the cron expression and executes matching jobs.
        """
        from croniter import croniter
        from datetime import datetime
        
        now = timezone.now()
        
        # Get all active cron jobs
        cron_jobs = CronJob.objects.filter(is_active=True)
        
        execution_count = 0
        
        async for job in cron_jobs:
            try:
                # Check if the job should run now
                if self._should_run_now(job.cron_expression, job.last_run_at, now):
                    await self._execute_cron_job(job)
                    
                    # Update last_run_at timestamp
                    job.last_run_at = now
                    await job.asave()
                    
                    execution_count += 1
                    logger.info(f"[SCHEDULER] Executed cron job: {job.name} (user: {job.user_id})")
                    
            except Exception as e:
                logger.error(f"[SCHEDULER] Failed to execute cron job {job.id}: {e}")
        
        if execution_count > 0:
            logger.info(f"[SCHEDULER] Executed {execution_count} scheduled tasks")
        
        return execution_count
    
    def _should_run_now(self, cron_expression: str, last_run, now) -> bool:
        """
        Check if a cron job should run based on its expression and last run time.
        """
        try:
            from croniter import croniter
            
            # If never run, check if it should run now
            if not last_run:
                cron = croniter(cron_expression, now)
                prev_run = cron.get_prev(datetime)
                # If the previous scheduled time was within the last minute, run it
                return (now - prev_run).total_seconds() < 60
            
            # Check if enough time has passed since last run
            cron = croniter(cron_expression, last_run)
            next_run = cron.get_next(datetime)
            
            # If the next scheduled time has passed, run it
            return now >= next_run
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Error checking cron expression '{cron_expression}': {e}")
            return False
    
    async def _execute_cron_job(self, job: CronJob):
        """
        Execute a scheduled cron job by calling the specified tool.
        """
        try:
            from core.registry import capability_registry
            
            # Get the tool
            tool = capability_registry.get_tool(job.tool_name)
            if not tool:
                logger.error(f"[SCHEDULER] Tool not found: {job.tool_name}")
                return
            
            # Execute the tool with the stored parameters
            result = await tool(
                _user_id=job.user_id,
                _session_id=f"cron_{job.id}",
                **job.parameters
            )
            
            logger.info(f"[SCHEDULER] Cron job '{job.name}' executed successfully")
            
            # If the tool is notify_user, send a message
            if job.tool_name == "notify_user" or "message" in job.parameters:
                await self._send_scheduled_notification(job, result)
            
            return result
            
        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to execute cron job '{job.name}': {e}")
            raise
    
    async def _send_scheduled_notification(self, job: CronJob, result: dict):
        """
        Send a notification for a scheduled task.
        """
        try:
            from integrations.telegram_bot.management.commands.run_bot import bot_instance
            
            if not bot_instance:
                logger.warning("[SCHEDULER] Bot instance not available for notification")
                return
            
            # Extract Telegram user ID
            if job.user_id.startswith('tg_'):
                telegram_user_id = job.user_id.replace('tg_', '')
                
                # Get message from parameters or result
                message = job.parameters.get('message', result.get('message', 'Scheduled task executed'))
                
                # Format the notification
                notification = f"""⏰ **Scheduled Task**

📋 **Task:** {job.name}
📝 **Message:** {message}

Schedule: `{job.cron_expression}`"""
                
                # Send the message
                await bot_instance.bot.send_message(
                    chat_id=telegram_user_id,
                    text=notification,
                    parse_mode='Markdown'
                )
                
                logger.info(f"[SCHEDULER] Notification sent to user {telegram_user_id} for job: {job.name}")
                
        except Exception as e:
            logger.error(f"[SCHEDULER] Failed to send scheduled notification: {e}")


# Singleton instance
reminder_service = ReminderService()
