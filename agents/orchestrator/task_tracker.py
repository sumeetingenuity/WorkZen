"""
Task Tracker - Manages long-running agent tasks with progress updates.

Allows the orchestrator to:
- Start tasks asynchronously
- Track their progress
- Notify users on completion
- Show status updates
"""
import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrackedTask:
    """Represents a tracked long-running task."""
    
    def __init__(
        self,
        task_id: str,
        user_id: str,
        session_id: str,
        description: str,
        tool_name: str,
        parameters: dict
    ):
        self.task_id = task_id
        self.user_id = user_id
        self.session_id = session_id
        self.description = description
        self.tool_name = tool_name
        self.parameters = parameters
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[Any] = None
        self.error: Optional[str] = None
        self.progress_updates: list[str] = []
        self._task: Optional[asyncio.Task] = None
    
    def add_progress(self, message: str):
        """Add a progress update."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.progress_updates.append(f"[{timestamp}] {message}")
        logger.info(f"[TASK {self.task_id}] {message}")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "description": self.description,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress_updates": self.progress_updates,
            "has_result": self.result is not None,
            "error": self.error
        }


class TaskTracker:
    """
    Manages long-running tasks with progress tracking.
    
    Features:
    - Async task execution
    - Progress updates
    - Status queries
    - User notifications
    """
    
    def __init__(self):
        self._tasks: Dict[str, TrackedTask] = {}
        self._user_tasks: Dict[str, list[str]] = {}  # user_id -> [task_ids]
        self._notification_callbacks: list[Callable] = []
    
    def register_notification_callback(self, callback: Callable):
        """Register a callback to be called when tasks complete."""
        self._notification_callbacks.append(callback)
    
    async def start_task(
        self,
        user_id: str,
        session_id: str,
        description: str,
        tool_name: str,
        parameters: dict,
        executor: Callable
    ) -> str:
        """
        Start a long-running task.
        
        Args:
            user_id: User who initiated the task
            session_id: Session ID
            description: Human-readable task description
            tool_name: Name of the tool being executed
            parameters: Tool parameters
            executor: Async function that executes the task
        
        Returns:
            task_id: Unique identifier for tracking
        """
        task_id = str(uuid.uuid4())[:8]
        
        logger.info(f"[TASK TRACKER] Creating task {task_id}")
        logger.info(f"[TASK TRACKER] user_id={user_id}, tool_name={tool_name}")
        logger.info(f"[TASK TRACKER] executor={executor}")
        
        task = TrackedTask(
            task_id=task_id,
            user_id=user_id,
            session_id=session_id,
            description=description,
            tool_name=tool_name,
            parameters=parameters
        )
        
        self._tasks[task_id] = task
        
        # Track by user
        if user_id not in self._user_tasks:
            self._user_tasks[user_id] = []
        self._user_tasks[user_id].append(task_id)
        
        # Start the task asynchronously
        logger.info(f"[TASK TRACKER] Creating asyncio task for {task_id}")
        task._task = asyncio.create_task(self._execute_task(task, executor))
        logger.info(f"[TASK TRACKER] asyncio task created: {task._task}")
        
        logger.info(f"[TASK TRACKER] Started task {task_id} for user {user_id}: {description}")
        
        return task_id
    
    async def _execute_task(self, task: TrackedTask, executor: Callable):
        """Execute a task and track its progress."""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            task.add_progress("Task started")
            
            logger.info(f"[TASK TRACKER] Executing task {task.task_id} with executor: {executor}")
            
            # Execute the task
            result = await executor(task)
            
            logger.info(f"[TASK TRACKER] Task {task.task_id} completed successfully")
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            task.add_progress("Task completed successfully")
            
            # Notify user
            await self._notify_completion(task)
            
        except asyncio.CancelledError:
            logger.warning(f"[TASK TRACKER] Task {task.task_id} was cancelled")
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            task.add_progress("Task cancelled")
            
        except Exception as e:
            logger.exception(f"[TASK TRACKER] Task {task.task_id} failed with exception: {e}")
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            task.add_progress(f"Task failed: {str(e)}")
            
            # Notify user of failure
            await self._notify_completion(task)
    
    async def _notify_completion(self, task: TrackedTask):
        """Notify user that task completed."""
        for callback in self._notification_callbacks:
            try:
                await callback(task)
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")
    
    def get_task(self, task_id: str) -> Optional[TrackedTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    def get_user_tasks(self, user_id: str, active_only: bool = False) -> list[TrackedTask]:
        """Get all tasks for a user."""
        task_ids = self._user_tasks.get(user_id, [])
        tasks = [self._tasks[tid] for tid in task_ids if tid in self._tasks]
        
        if active_only:
            tasks = [t for t in tasks if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)]
        
        return tasks
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get task status as dictionary."""
        task = self.get_task(task_id)
        return task.to_dict() if task else None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        task = self.get_task(task_id)
        if not task or not task._task:
            return False
        
        if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            task._task.cancel()
            return True
        
        return False
    
    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove old completed tasks."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        to_remove = []
        for task_id, task in self._tasks.items():
            if task.completed_at and task.completed_at < cutoff:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            task = self._tasks.pop(task_id)
            if task.user_id in self._user_tasks:
                self._user_tasks[task.user_id].remove(task_id)
        
        if to_remove:
            logger.info(f"[TASK TRACKER] Cleaned up {len(to_remove)} old tasks")


# Singleton instance
task_tracker = TaskTracker()
