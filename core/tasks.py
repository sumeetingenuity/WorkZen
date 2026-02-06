"""
Core scheduled tasks for cron jobs.

These functions are called by django-crontab based on CRONJOBS in settings.py.
"""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def cleanup_old_responses():
    """
    Clean up old tool responses (older than 30 days).
    Runs daily at midnight.
    """
    from core.models import ToolResponse
    
    cutoff = timezone.now() - timedelta(days=30)
    count, _ = ToolResponse.objects.filter(created_at__lt=cutoff).delete()
    logger.info(f"Cleaned up {count} old tool responses")


def sync_capability_registry():
    """
    Sync capability registry by re-discovering tools.
    Runs every 5 minutes.
    """
    from core.registry import capability_registry
    
    try:
        capability_registry.discover_tools()
        logger.info("Capability registry synced")
    except Exception as e:
        logger.error(f"Registry sync failed: {e}")


def generate_audit_summary():
    """
    Generate daily audit summary.
    Runs daily at 1 AM.
    """
    from core.models import AuditLog
    from django.db.models import Count
    
    yesterday = timezone.now() - timedelta(days=1)
    
    stats = AuditLog.objects.filter(
        created_at__gte=yesterday
    ).values('status').annotate(count=Count('id'))
    
    summary = {item['status']: item['count'] for item in stats}
    logger.info(f"Daily audit summary: {summary}")
