"""
Audit Logger - Comprehensive audit trail for all agent actions.
"""
import uuid
import re
import logging
from typing import Optional
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class AuditLogger:
    """Static methods for logging audit events."""
    
    @staticmethod
    async def log(
        action: str,
        tool: Optional[str] = None,
        execution_id: Optional[str] = None,
        user_id: Optional[str] = None,
        agent: Optional[str] = None,
        session_id: Optional[str] = None,
        input_summary: str = "",
        output_summary: str = "",
        error: str = "",
        status: str = "success",
        execution_time_ms: Optional[int] = None,
        metadata: Optional[dict] = None
    ):
        """Log an audit event."""
        from core.models import AuditLog
        
        # Sanitize inputs - never log secrets
        safe_input = AuditLogger._sanitize(input_summary)
        safe_output = AuditLogger._sanitize(output_summary)
        safe_error = AuditLogger._sanitize(error)
        
        audit_log = await sync_to_async(AuditLog.objects.create)(
            action=action,
            tool=tool,
            execution_id=execution_id,
            user_id=user_id,
            agent=agent,
            session_id=uuid.UUID(session_id) if session_id else None,
            input_summary=safe_input[:500],
            output_summary=safe_output[:500],
            error=safe_error,
            status=status,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {}
        )
        
        log_msg = f"[AUDIT] {action}: {tool or 'N/A'} - {status}"
        if status == 'success':
            logger.info(log_msg)
        elif status == 'denied':
            logger.warning(log_msg)
        else:
            logger.error(f"{log_msg} - {error[:100] if error else ''}")
        
        return audit_log
    
    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove potential secrets from audit text."""
        patterns = [
            (r'(api[_-]?key|secret|password|token|auth)["\']?\s*[:=]\s*["\']?([^"\'}\s]+)', r'\1=[REDACTED]'),
            (r'Bearer\s+[A-Za-z0-9\-._~+/]+=*', 'Bearer [REDACTED]'),
            (r'sk-[A-Za-z0-9]{48}', '[REDACTED]'),
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
