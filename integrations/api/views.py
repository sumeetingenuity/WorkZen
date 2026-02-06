"""
REST API Views using Django Ninja.
"""
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from typing import Optional, List, Any
from django.http import HttpRequest
import uuid

api = NinjaAPI(
    title="SecureAssist API",
    version="1.0.0",
    description="Secure Django Agent Platform API"
)


# =============================================================================
# Schemas
# =============================================================================

class ToolExecutionRequest(Schema):
    tool_name: str
    input_data: dict
    session_id: Optional[str] = None
    require_approval: bool = False


class ToolExecutionResponse(Schema):
    execution_id: str
    tool_name: str
    status: str
    result: Optional[dict] = None
    summary: Optional[str] = None


class ChatRequest(Schema):
    message: str
    session_id: Optional[str] = None


class ChatResponse(Schema):
    session_id: str
    response: str
    tool_executions: List[dict] = []
    requires_approval: bool = False
    pending_task_id: Optional[str] = None


class CapabilitySchema(Schema):
    category: str
    tools: List[str]


class DashboardStats(Schema):
    total_sessions: int
    total_tool_executions: int
    pending_approvals: int
    active_apps: int
    last_audit_events: List[dict]


# =============================================================================
# Endpoints
# =============================================================================

@api.get("/dashboard/stats", tags=["System"], response=DashboardStats)
async def get_dashboard_stats(request):
    """Get system stats for the dashboard."""
    from core.models import Session, ToolResponse, PendingApproval
    from auditlog.models import LogEntry
    from django.apps import apps
    
    # Simple aggregates (async)
    total_sessions = await Session.objects.acount()
    total_tools = await ToolResponse.objects.acount()
    pending = await PendingApproval.objects.filter(status="pending").acount()
    
    # Count apps in the 'apps' directory
    active_apps = len([a for a in apps.get_app_configs() if a.name.startswith("apps.")])
    
    # Fetch last 5 audit entries
    # django-auditlog doesn't natively support async slicing/iteration easily without wrappers
    # but we can fetch ID list and then objects.
    last_audit = []
    async for entry in LogEntry.objects.order_by("-timestamp")[:5]:
        last_audit.append({
            "action": entry.get_action_display(),
            "content_type": str(entry.content_type),
            "object_id": str(entry.object_id),
            "timestamp": str(entry.timestamp),
            "msg": entry.changes
        })

    return {
        "total_sessions": total_sessions,
        "total_tool_executions": total_tools,
        "pending_approvals": pending,
        "active_apps": active_apps,
        "last_audit_events": last_audit
    }


@api.get("/health", tags=["System"])
def health_check(request):
    """Health check endpoint."""
    return {"status": "healthy"}


@api.get("/capabilities", tags=["Agent"], response=List[CapabilitySchema])
def list_capabilities(request):
    """List all available agent capabilities."""
    from core.registry import capability_registry
    
    registry = capability_registry.get_full_registry()
    return [
        {
            "category": category,
            "tools": [t["name"] for t in data["tools"]]
        }
        for category, data in registry.items()
    ]


@api.get("/tools", tags=["Tools"])
def list_tools(request):
    """List all registered tools with their schemas."""
    from core.registry import capability_registry
    
    tools = []
    for category, data in capability_registry.get_full_registry().items():
        for tool in data["tools"]:
            tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "category": category,
                "requires_approval": tool.get("requires_approval", False),
                "input_schema": tool.get("input_schema", {})
            })
    
    return {"tools": tools}


@api.post("/tools/execute", tags=["Tools"], response=ToolExecutionResponse)
async def execute_tool(request, payload: ToolExecutionRequest):
    """
    Execute a tool directly.
    
    Response is logged to ORM for user display.
    LLM only receives summary.
    """
    from core.registry import capability_registry
    
    tool = capability_registry.get_tool(payload.tool_name)
    if not tool:
        raise HttpError(404, f"Tool not found: {payload.tool_name}")
    
    execution_id = str(uuid.uuid4())
    
    # Add context
    input_data = payload.input_data.copy()
    input_data["_session_id"] = payload.session_id
    
    # Execute tool
    result = await tool(**input_data)
    
    # Check if approval required
    if isinstance(result, dict) and result.get("status") == "pending_approval":
        return {
            "execution_id": result.get("task_id", execution_id),
            "tool_name": payload.tool_name,
            "status": "pending_approval",
            "result": None,
            "summary": result.get("description")
        }
    
    return {
        "execution_id": execution_id,
        "tool_name": payload.tool_name,
        "status": result.get("status", "success") if isinstance(result, dict) else "success",
        "result": result,
        "summary": str(result)[:200] if result else None
    }


@api.post("/chat", tags=["Agent"], response=ChatResponse)
async def chat(request, payload: ChatRequest):
    """
    Chat with the agent orchestrator.
    
    The orchestrator will:
    1. Parse intent (create app, use tool, general query)
    2. If "create app": Research → Developer Agent → Build app
    3. If "use tool": Execute tool
    4. Return response with tool results logged to ORM
    """
    from agents.orchestrator.agent import orchestrator_agent
    
    # Get or create session
    session_id = payload.session_id or str(uuid.uuid4())
    
    # Process through orchestrator
    result = await orchestrator_agent.process(
        user_id="api_user",
        message=payload.message,
        session_id=session_id
    )
    
    return {
        "session_id": result.session_id,
        "response": result.response,
        "tool_executions": [{"id": r} for r in result.tool_responses],
        "requires_approval": result.requires_approval,
        "pending_task_id": result.pending_task_id
    }


@api.get("/responses/{response_id}", tags=["Responses"])
async def get_response(request, response_id: str):
    """
    Get full tool response by ID.
    
    This is used by the UI to display full results
    that are stored in ORM instead of passed through LLM.
    """
    from core.services.orm_logger import ToolResponseLogger
    
    try:
        return await ToolResponseLogger.get_full(response_id)
    except Exception as e:
        raise HttpError(404, f"Response not found: {response_id}")


@api.post("/approvals/{task_id}/approve", tags=["Approvals"])
async def approve_task(request, task_id: str):
    """Approve a pending tool execution."""
    from core.models import PendingApproval
    from django.utils import timezone
    
    try:
        approval = await PendingApproval.objects.aget(id=task_id)
        approval.status = "approved"
        approval.resolved_at = timezone.now()
        await approval.asave()
        
        # TODO: Execute the approved tool
        return {"status": "approved", "task_id": task_id}
    except PendingApproval.DoesNotExist:
        raise HttpError(404, f"Task not found: {task_id}")


@api.post("/approvals/{task_id}/reject", tags=["Approvals"])
async def reject_task(request, task_id: str):
    """Reject a pending tool execution."""
    from core.models import PendingApproval
    from django.utils import timezone
    
    try:
        approval = await PendingApproval.objects.aget(id=task_id)
        approval.status = "rejected"
        approval.resolved_at = timezone.now()
        await approval.asave()
        
        return {"status": "rejected", "task_id": task_id}
    except PendingApproval.DoesNotExist:
        raise HttpError(404, f"Task not found: {task_id}")
