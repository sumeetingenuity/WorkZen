"""
Task Management Tools - Agent-callable tools for proactive todo & reminder management.
"""
import logging
from typing import Optional, List
from core.decorators import agent_tool
from core.models import TaskEntity
from django.utils import timezone

logger = logging.getLogger(__name__)

@agent_tool(
    name="create_task",
    description="Create a new task or todo item in the system. Use due_date for proactive reminders.",
    category="system"
)
async def create_task(
    title: str,
    description: str = "",
    priority: int = 2,
    due_date: Optional[str] = None,
    project: Optional[str] = None,
    _user_id: str = None
):
    """Creates a persistent task."""
    task = await TaskEntity.objects.acreate(
        user_id=_user_id,
        title=title,
        description=description,
        priority=priority,
        due_date=due_date,
        project=project
    )
    
    # If a due date is set, the Daily Sweeper will automatically include this in briefings.
    return {
        "status": "created",
        "task_id": str(task.id),
        "title": title,
        "due_date": due_date,
        "display_markdown": f"✅ **Task Created**: {title}\n📅 **Due**: {due_date or 'No Date'}\n📌 **Priority**: {priority}"
    }

@agent_tool(
    name="list_tasks",
    description="List active tasks for the current user. Filters: status, project.",
    category="system"
)
async def list_tasks(status: str = 'todo', project: str = None, _user_id: str = None):
    """Lists tasks for the user."""
    qs = TaskEntity.objects.filter(user_id=_user_id, status=status)
    if project:
        qs = qs.filter(project=project)
        
    tasks = []
    async for t in qs:
        tasks.append({
            "id": str(t.id),
            "title": t.title,
            "priority": t.get_priority_display(),
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "project": t.project
        })
    
    return {
        "tasks": tasks, 
        "display_markdown": "### 📋 Your Tasks\n\n" + (chr(10).join([f"- **{t['title']}** ({t['priority']}) - {t['due_date'] or 'No date'}" for t in tasks]) if tasks else "No tasks found.")
    }

@agent_tool(
    name="complete_task",
    description="Mark a task as completed.",
    category="system"
)
async def complete_task(task_id: str, _user_id: str = None):
    """Marks a task as done."""
    try:
        task = await TaskEntity.objects.aget(id=task_id, user_id=_user_id)
        task.status = 'done'
        task.completed_at = timezone.now()
        await task.asave()
        return {"status": "completed", "task": task.title}
    except TaskEntity.DoesNotExist:
        return {"status": "error", "message": f"Task '{task_id}' not found."}
