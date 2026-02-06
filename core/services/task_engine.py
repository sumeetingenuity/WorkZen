"""
SecureAssist Task Engine (SATE)

Handles:
1. Decomposition of objectives into DAGs (TaskPlanner).
2. Parallel execution of task graphs (TaskExecutor).
"""
import logging
import json
import asyncio
from typing import List, Dict, Any, Set
from django.utils import timezone
from core.models import TaskEntity
from asgiref.sync import sync_to_async
from asgiref.sync import sync_to_async
from agents.model_router import model_router, async_retry

logger = logging.getLogger(__name__)

class TaskPlanner:
    """
    Decomposes complex objectives into executable TaskEntity DAGs.
    """
    
    SYSTEM_PROMPT = """
    You are a Strategic Task Planner. 
    Break down the user's objective into a JSON DAG (Directed Acyclic Graph) of sub-tasks.
    
    Return ONLY a JSON list of objects format:
    [
        {
            "id": "unique_id_A",
            "title": "Short title",
            "description": "Detailed instruction...",
            "agent": "researcher" | "developer" | "orchestrator",
            "dependencies": []
        },
        {
            "id": "unique_id_B",
            "title": "Use research to build X",
            "description": "...",
            "agent": "developer",
            "dependencies": ["unique_id_A"]
        }
    ]
    
    Rules:
    1. Parallelize where possible (e.g. research two topics at once).
    2. 'agent' must be one of: 'researcher' (web/data), 'developer' (coding), 'orchestrator' (generic/tools).
    3. Keep tasks granular but meaningful.
    """

    @classmethod
    async def plan_objective(cls, objective: str, user_id: str) -> List[str]:
        """
        Generates a plan and persists it to the DB.
        Returns the list of created TaskEntity IDs.
        """
        logger.info(f"Planning objective: {objective}")
        
        response = await model_router.complete(
            task_type="planning",
            messages=[
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": f"Objective: {objective}"}
            ],
            max_tokens=2000
        )
        
        try:
            # Clean and parse JSON
            content = response.replace("```json", "").replace("```", "").strip()
            plan_data = json.loads(content)
        except json.JSONDecodeError:
            logger.error("Failed to parse plan JSON from LLM")
            return []

        # 1. Create all TaskEntities first (without dependencies)
        task_map = {} # local_id -> db_instance
        
        for item in plan_data:
            task = await TaskEntity.objects.acreate(
                user_id=user_id,
                title=item['title'],
                description=item['description'],
                assigned_agent=item.get('agent', 'orchestrator'),
                is_automated=True,
                status='todo',
                priority=2,
                payload={"original_objective": objective}
            )
            task_map[item['id']] = task

        # 2. Link dependencies
        for item in plan_data:
            if not item.get('dependencies'):
                continue
            
            task = task_map[item['id']]
            for dep_id in item['dependencies']:
                if dep_id in task_map:
                    await sync_to_async(task.dependencies.add)(task_map[dep_id])
            
        return [str(t.id) for t in task_map.values()]


class TaskExecutor:
    """
    Executes a graph of TaskEntities, handling parellelism and dependencies.
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        
    async def run_plan(self, task_ids: List[str]):
        """
        Monitors and executes the specific set of tasks until all are complete or failed.
        """
        # We assume task_ids contains all tasks in the current plan graph
        active_ids = set(task_ids)
        
        while active_ids:
            # Fetch fresh state
            # Note: We filter by the specific IDs we care about
            tasks = []
            async for t in TaskEntity.objects.filter(id__in=active_ids):
                tasks.append(t)
            
            # Check for completion
            incomplete = [t for t in tasks if t.status not in ('done', 'cancelled')]
            if not incomplete:
                logger.info("All tasks in plan complete.")
                break
                
            # Find runnable tasks (todo + deps blocked_by are all done)
            runnable = []
            
            for task in incomplete:
                if task.status != 'todo':
                    continue
                    
                # Async dependency check
                deps_met = True
                async for dep in task.dependencies.all():
                    if dep.status != 'done':
                        deps_met = False
                        break
                
                if deps_met:
                    runnable.append(task)
            
            if not runnable:
                # No tasks are runnable, but some are incomplete. 
                # Either they are running ('in_progress') or we have a deadlock/failure in a dep.
                # Check for in_progress
                running = [t for t in incomplete if t.status == 'in_progress']
                if not running and incomplete:
                    logger.error("Deadlock detected in task execution or dependency failure.")
                    break
                
                # Wait a bit before polling again
                await asyncio.sleep(1)
                continue
                
            # Execute runnable tasks in parallel
            # We mark them in_progress first to avoid double-selection
            update_tasks = []
            for t in runnable:
                t.status = 'in_progress'
                update_tasks.append(t)
            
            await TaskEntity.objects.abulk_update(update_tasks, ['status'])
            
            # Fire off execution
            await asyncio.gather(*[self._execute_single_task(t) for t in runnable])
            
    @async_retry(max_retries=3)
    async def _execute_single_task(self, task: TaskEntity):
        """Dispatches a single task to the appropriate agent."""
        logger.info(f"Executing task [{task.assigned_agent}]: {task.title}")
        
        try:
            result = {}
            if task.assigned_agent == 'developer':
                from agents.developer.agent import developer_agent
                # Developer agent takes app_specs mostly, but we can assume the task description implies intent
                # For this simplified engine, we'll assume we can pass instructions
                # But developer agent 'build_app' needs structured input.
                # Just mock for now or use Orchestrator as proxy?
                # Ideally, we call specific tools.
                # Let's route everything thru Orchestrator with a 'persona' hint?
                # Actually, implementing full agent-to-agent protocol is complex.
                # Standard trick: Use Orchestrator to "act as" the agent for the task.
                pass
                
            # Default dispatch (Orchestrator Logic)
            # We use the Orchestrator to solve the sub-task
            from agents.orchestrator.agent import orchestrator_agent
            
            # We treat this as a mini-session
            sub_res = await orchestrator_agent.process_request(
                session_id=None, # Ephemeral
                user_id=self.user_id,
                message=f"Please perform this task: {task.title}\nDetails: {task.description}",
                image_path=None
            )
            
            result = {"response": sub_res.response, "tool_responses": sub_res.tool_responses}
            
            task.result = result
            task.status = 'done'
            task.completed_at = timezone.now()
            await task.asave()
            
        except Exception as e:
            logger.exception(f"Task {task.id} failed: {e}")
            task.status = 'cancelled' # Or error
            task.result = {"error": str(e)}
            await task.asave()

# Singleton
task_executor = TaskExecutor(user_id="system") # Placeholder, will be instantiated per request
