"""
Model Context Protocol (MCP) Service.

Provides tools and context in a standardized format for external LLMs
and tools that support the MCP standard.
"""
from typing import List, Dict, Any, Optional
from core.registry import capability_registry
from core.models import ToolResponse, Session

class MCPService:
    """
    Standardizes SecureAssist capabilities for MCP compliance.
    """
    
    async def list_tools(self, user_id: str) -> List[Dict[str, Any]]:
        """List all available tools in MCP format."""
        tools = capability_registry.list_tools_schema()
        mcp_tools = []
        
        for tool in tools:
            mcp_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["input_schema"]
            })
            
        return mcp_tools

    async def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get optimized session context in MCP format."""
        try:
            session = await Session.objects.aget(id=session_id)
            return {
                "summary": session.session_summary,
                "recent_history": session.raw_history[-5:] if session.raw_history else []
            }
        except Session.DoesNotExist:
            return {"error": "Session not found"}

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via MCP request."""
        tool = capability_registry.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool {tool_name} not found"}
        
        # Inject standard context parameters
        arguments["_user_id"] = context.get("user_id")
        arguments["_session_id"] = context.get("session_id")
        
        try:
            result = await tool(**arguments)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

mcp_service = MCPService()
