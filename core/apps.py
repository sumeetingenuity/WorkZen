"""
Core Django app configuration.
"""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'SecureAssist Core'
    
    def ready(self):
        """Called when Django starts - discover tools."""
        # Import here to avoid circular imports
        try:
            from core.registry import capability_registry
            capability_registry.discover_tools()
        except Exception:
            pass  # Skip during migrations
