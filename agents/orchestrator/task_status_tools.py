"""
Task Status Tools - Allow users to check on long-running tasks.
"""
import logging
from core.decorators import agent_tool
from agents.orchestrator.task_tracker import task_tracker, TaskStatus

logger = logging.getLogger(__name__)


@agent_tool(
    name="check_task_status",
    description="Check the status of a long-running task by its ID. Returns current status, progress updates, and results if completed.",
    category="system"
)
async def check_task_status(
    task_id: str,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Check status of a specific task."""
    
    task = task_tracker.get_task(task_id)
    
    if not task:
        return {
            "status": "error",
            "error": f"Task {task_id} not found. It may have been completed and cleaned up."
        }
    
    # Check if user owns this task
    if _user_id and task.user_id != _user_id:
        return {
            "status": "error",
            "error": "You don't have permission to view this task."
        }
    
    status_dict = task.to_dict()
    
    # Format for display
    status_emoji = {
        TaskStatus.PENDING: "⏳",
        TaskStatus.RUNNING: "🔄",
        TaskStatus.COMPLETED: "✅",
        TaskStatus.FAILED: "❌",
        TaskStatus.CANCELLED: "🚫"
    }
    
    emoji = status_emoji.get(task.status, "❓")
    
    response = f"""{emoji} **Task Status: {task.status.value.upper()}**

**Task ID:** `{task.task_id}`
**Description:** {task.description}
**Tool:** {task.tool_name}
**Created:** {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    if task.started_at:
        response += f"**Started:** {task.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    if task.completed_at:
        response += f"**Completed:** {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        duration = (task.completed_at - task.created_at).total_seconds()
        response += f"**Duration:** {duration:.1f} seconds\n"
    
    if task.progress_updates:
        response += f"\n**Progress Updates:**\n"
        for update in task.progress_updates[-5:]:  # Last 5 updates
            response += f"  {update}\n"
    
    if task.error:
        response += f"\n**Error:** {task.error}\n"
    
    if task.status == TaskStatus.COMPLETED and task.result:
        response += f"\n**Result:**\n{task.result}\n"
    
    return {
        "status": "success",
        "display_markdown": response,
        "task_data": status_dict
    }


@agent_tool(
    name="list_my_tasks",
    description="List all your tasks, optionally filtering to show only active (running/pending) tasks.",
    category="system"
)
async def list_my_tasks(
    active_only: bool = False,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """List all tasks for the current user."""
    
    if not _user_id:
        return {
            "status": "error",
            "error": "User ID not provided"
        }
    
    tasks = task_tracker.get_user_tasks(_user_id, active_only=active_only)
    
    if not tasks:
        message = "You have no active tasks." if active_only else "You have no tasks."
        return {
            "status": "success",
            "display_markdown": f"📋 {message}"
        }
    
    # Group by status
    by_status = {}
    for task in tasks:
        status = task.status.value
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(task)
    
    response = f"📋 **Your Tasks** ({'Active Only' if active_only else 'All'})\n\n"
    
    status_order = ["running", "pending", "completed", "failed", "cancelled"]
    status_emoji = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫"
    }
    
    for status in status_order:
        if status in by_status:
            response += f"\n**{status_emoji.get(status, '❓')} {status.upper()}:**\n"
            for task in by_status[status]:
                response += f"  • `{task.task_id}` - {task.description}\n"
                if task.status == TaskStatus.RUNNING and task.progress_updates:
                    response += f"    └─ {task.progress_updates[-1]}\n"
    
    response += f"\n💡 Use `check_task_status(task_id='...')` to see details."
    
    return {
        "status": "success",
        "display_markdown": response,
        "tasks": [t.to_dict() for t in tasks]
    }


@agent_tool(
    name="cancel_task",
    description="Cancel a running or pending task by its ID.",
    category="system"
)
async def cancel_task(
    task_id: str,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Cancel a task."""
    
    task = task_tracker.get_task(task_id)
    
    if not task:
        return {
            "status": "error",
            "error": f"Task {task_id} not found."
        }
    
    # Check if user owns this task
    if _user_id and task.user_id != _user_id:
        return {
            "status": "error",
            "error": "You don't have permission to cancel this task."
        }
    
    if task.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        return {
            "status": "error",
            "error": f"Task {task_id} is {task.status.value} and cannot be cancelled."
        }
    
    success = await task_tracker.cancel_task(task_id)
    
    if success:
        return {
            "status": "success",
            "display_markdown": f"🚫 **Task Cancelled**\n\nTask `{task_id}` has been cancelled."
        }
    else:
        return {
            "status": "error",
            "error": f"Failed to cancel task {task_id}."
        }
