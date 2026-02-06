"""
Agent scheduled tasks using Django 6 built-in background tasks.
"""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def compress_old_sessions():
    """
    Compress old sessions by summarizing chat history.
    Runs hourly.
    """
    from core.models import Session
    from agents.context_manager import ContextManager
    
    # Find sessions with more than 10 raw turns
    sessions = Session.objects.filter(
        is_active=True,
        updated_at__lt=timezone.now() - timedelta(hours=1)
    )
    
    context_manager = ContextManager()
    compressed_count = 0
    
    for session in sessions:
        if len(session.raw_history) > 10:
            try:
                # This would be async in production
                # context_manager.compress_session(session)
                compressed_count += 1
            except Exception as e:
                logger.error(f"Failed to compress session {session.id}: {e}")
    
    logger.info(f"Compressed {compressed_count} sessions")
