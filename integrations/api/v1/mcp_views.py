"""
MCP API Views.

Exposes MCP Service via Django Ninja API.
"""
from typing import List, Dict, Any
from ninja import Router, Schema
from core.services.mcp import mcp_service

router = Router(tags=["MCP"])

class ToolSchema(Schema):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class CallToolRequest(Schema):
    tool_name: str
    arguments: Dict[str, Any]
    session_id: str
    user_id: str

@router.get("/tools", response=List[ToolSchema])
async def list_tools(request, user_id: str):
    """List available tools in MCP format."""
    return await mcp_service.list_tools(user_id)

@router.get("/context/{session_id}")
async def get_context(request, session_id: str):
    """Get session context in MCP format."""
    return await mcp_service.get_context(session_id)

@router.post("/call")
async def call_tool(request, data: CallToolRequest):
    """Call a tool via MCP."""
    context = {
        "user_id": data.user_id,
        "session_id": data.session_id
    }
    return await mcp_service.call_tool(data.tool_name, data.arguments, context)
