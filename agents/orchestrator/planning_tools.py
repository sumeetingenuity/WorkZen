"""
Planning Tools - Exposes the Task Engine to the Orchestrator.
"""
from core.decorators import agent_tool
from core.services.task_engine import TaskPlanner, TaskExecutor

@agent_tool(
    name="create_execution_plan",
    description="Break down a complex objective into a parallelized execution plan (DAG). Returns a plan_id (list of task IDs).",
    category="planning"
)
async def create_execution_plan(objective: str, _user_id: str = None, _session_id: str = None) -> dict:
    """Generates a plan for the objective."""
    task_ids = await TaskPlanner.plan_objective(objective, _user_id)
    
    return {
        "status": "plan_created",
        "task_count": len(task_ids),
        "plan_id": ",".join(task_ids), # Simple serialization for tool output
        "message": "Plan created. Use execute_plan with these IDs to start."
    }

@agent_tool(
    name="execute_plan",
    description="Execute a previously created plan (DAG). Runs tasks in parallel where possible.",
    category="planning"
)
async def execute_plan(plan_id: str, _user_id: str = None, _session_id: str = None) -> dict:
    """Executes the plan."""
    task_ids = plan_id.split(",")
    executor = TaskExecutor(user_id=_user_id)
    
    await executor.run_plan(task_ids)
    
    return {
        "status": "execution_complete",
        "message": "All tasks in the plan have finished."
    }
