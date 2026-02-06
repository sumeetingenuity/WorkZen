"""
ORM Logger - Direct-to-database response logging.

API responses are logged directly to the database and displayed to users,
bypassing expensive LLM re-ingestion.
"""
import uuid
import hashlib
import logging
from typing import Any, Optional
from asgiref.sync import sync_to_async
import json

logger = logging.getLogger(__name__)


class ToolResponseLogger:
    """
    Logs tool responses directly to ORM.
    
    Benefits:
    1. User sees full response immediately in UI
    2. LLM only receives a short summary (saves tokens)
    3. Enables response caching and deduplication
    """
    
    SUMMARIZERS = {
        'search_web': lambda d: f"Found {len(d.get('results', []))} results. Top: {d.get('results', [{}])[0].get('title', 'N/A')[:50]}",
        'browse_page': lambda d: f"Loaded '{d.get('title', 'page')[:30]}' ({len(d.get('text_content', ''))} chars)",
        'extract_pdf_text': lambda d: f"Extracted {d.get('total_pages', 0)} pages from PDF",
        'send_email': lambda d: f"Email sent to {d.get('to', 'recipient')[:30]}",
    }
    
    @staticmethod
    async def log(
        tool_name: str,
        model_name: Optional[str],
        input_data: dict,
        output_data: Any,
        session_id: Optional[str] = None,
        execution_time_ms: int = 0
    ):
        """Log a tool response to the database."""
        from core.models import ToolResponse
        
        # Create input hash for deduplication
        input_hash = hashlib.sha256(
            json.dumps(input_data, sort_keys=True).encode()
        ).hexdigest()
        
        # Generate summary for LLM
        summary = ToolResponseLogger._generate_summary(tool_name, output_data)
        
        # Determine status
        status = 'success'
        if isinstance(output_data, dict):
            if 'error' in output_data:
                status = 'error'
            elif output_data.get('status') == 'timeout':
                status = 'timeout'
        
        response = await sync_to_async(ToolResponse.objects.create)(
            tool_name=tool_name,
            session_id=uuid.UUID(session_id) if session_id else None,
            input_data=input_data,
            input_hash=input_hash,
            response_data=output_data if isinstance(output_data, dict) else {'data': output_data},
            response_summary=summary,
            execution_time_ms=execution_time_ms,
            status=status
        )
        
        logger.debug(f"Logged tool response: {tool_name} (id={response.id})")
        
        # 8. Trigger Webhooks
        try:
            from core.services.webhooks import webhook_service
            # Find user_id from session or use a default
            user_id = 'system'
            if session_id:
                from core.models import Session
                # We do a quick lookup if needed, but for performance, we might want to pass user_id
                # For now, let's assume we can get it or use 'system'
                pass
                
            await webhook_service.trigger(
                user_id=user_id,
                event_type="tool_execution_success" if status == 'success' else "tool_execution_failed",
                payload={
                    "tool": tool_name,
                    "status": status,
                    "summary": summary,
                    "execution_time_ms": execution_time_ms
                }
            )
        except Exception as e:
            logger.error(f"Failed to trigger webhook: {e}")

        return response
    
    @staticmethod
    def _generate_summary(tool_name: str, output_data: dict) -> str:
        """Generate a concise summary for LLM consumption."""
        if isinstance(output_data, dict) and 'error' in output_data:
            return f"Error: {str(output_data['error'])[:200]}"
        
        summarizer = ToolResponseLogger.SUMMARIZERS.get(
            tool_name,
            lambda d: f"Completed with {len(str(d))} bytes"
        )
        
        try:
            return summarizer(output_data)[:500]
        except Exception:
            return "Completed successfully"
    
    @staticmethod
    async def get_for_llm(response_id: str) -> dict:
        """Get minimal response data for LLM context."""
        from core.models import ToolResponse
        
        response = await sync_to_async(ToolResponse.objects.get)(id=response_id)
        return {
            "tool": response.tool_name,
            "status": response.status,
            "summary": response.response_summary,
            "response_id": str(response.id)
        }
    
    @staticmethod
    async def get_full(response_id: str) -> dict:
        """Get full response data for user display."""
        from core.models import ToolResponse
        
        response = await sync_to_async(ToolResponse.objects.get)(id=response_id)
        return {
            "tool": response.tool_name,
            "status": response.status,
            "data": response.response_data,
            "execution_time_ms": response.execution_time_ms,
            "created_at": response.created_at.isoformat()
        }
