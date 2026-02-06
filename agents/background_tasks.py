"""
Django 6 Background Tasks for SecureAssist.

Uses django.tasks for async background processing.
"""
from django.tasks import task
import logging

logger = logging.getLogger(__name__)


@task
def execute_tool_async(tool_name: str, input_data: dict, session_id: str = None, user_id: str = None):
    """
    Execute a tool in the background using Django 6 tasks.
    
    This allows long-running tools to execute without blocking
    the HTTP request-response cycle.
    """
    from core.registry import capability_registry
    import asyncio
    
    tool = capability_registry.get_tool(tool_name)
    if not tool:
        logger.error(f"Tool not found: {tool_name}")
        return {"error": f"Tool '{tool_name}' not found"}
    
    # Add user and session context
    input_data['_user_id'] = user_id
    input_data['_session_id'] = session_id
    
    # Run the async tool
    result = asyncio.run(tool(**input_data))
    logger.info(f"Background tool completed: {tool_name}")
    
    return result


@task
def compress_session_context(session_id: str):
    """
    Compress session context in the background.
    
    Called when session context exceeds threshold.
    """
    from core.models import Session
    from agents.context_manager import ContextManager
    import asyncio
    
    try:
        session = Session.objects.get(id=session_id)
        context_manager = ContextManager()
        asyncio.run(context_manager.compress_session(session))
        logger.info(f"Session compressed: {session_id}")
    except Session.DoesNotExist:
        logger.error(f"Session not found: {session_id}")
    except Exception as e:
        logger.error(f"Compression failed for {session_id}: {e}")


@task
def process_webhook(webhook_type: str, payload: dict):
    """
    Process incoming webhooks in the background.
    """
    logger.info(f"Processing webhook: {webhook_type}")
    
    if webhook_type == 'telegram':
        from integrations.telegram_bot.handlers import handle_update
        handle_update(payload)
    else:
        logger.warning(f"Unknown webhook type: {webhook_type}")
