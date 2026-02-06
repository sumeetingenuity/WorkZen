"""
Dynamic App Reloader - Handles hot-reloading of generated Django apps.

Allows the system to inject new models and tools into a running process
without requiring a manual server restart.
"""
import logging
import importlib
import signal
import os
from asgiref.sync import sync_to_async
from django.conf import settings
from django.apps import apps
from django.db import connection
from django.core.management import call_command
from core.registry import capability_registry
import sys

logger = logging.getLogger(__name__)

class DynamicAppReloader:
    """
    Manages the reloading of Django applications and their capabilities.
    Supports both development (direct reload) and production (Gunicorn SIGHUP).
    """
    
    @staticmethod
    async def reload_app(app_name: str):
        """
        Reload a specific app and its components.
        
        1. Reload app config
        2. Run migrations
        3. Reload tools.py
        4. Re-discover tools
        """
        logger.info(f"Hot-reloading app: {app_name}")
        
        try:
            # 1. Ensure app is in sys.modules
            app_module_path = f"apps.{app_name}"
            
            # 2. Reload models and tools (with syntax protection)
            for sub_module in ["models", "tools", "apps"]:
                mod_path = f"{app_module_path}.{sub_module}"
                if mod_path in sys.modules:
                    # Syntax Check
                    mod_file = sys.modules[mod_path].__file__
                    if mod_file and not DynamicAppReloader._check_syntax(mod_file):
                        logger.error(f"Syntax error in {mod_path}, skipping reload.")
                        return False
                        
                    importlib.reload(sys.modules[mod_path])
                    logger.debug(f"Reloaded module: {mod_path}")
            
            # 3. Apply any pending migrations
            await DynamicAppReloader._run_migrations(app_name)
            
            # 4. Trigger tool re-discovery
            capability_registry.discover_tools()
            
            # 5. Handle Gunicorn workers if applicable
            await DynamicAppReloader._handle_gunicorn_reload()
            
            logger.info(f"Successfully hot-reloaded {app_name}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to hot-reload app {app_name}: {e}")
            return False

    @staticmethod
    async def _handle_gunicorn_reload():
        """
        In a production VPS environment (Gunicorn), we need to signal
        the master process to gracefully reload its workers so they
        all pick up the new INSTALLED_APPS and files.
        """
        pid_file = os.environ.get('GUNICORN_PID_FILE', '/tmp/gunicorn_secureassist.pid')
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    master_pid = int(f.read().strip())
                
                logger.info(f"Signalling Gunicorn Master (PID {master_pid}) for graceful reload...")
                os.kill(master_pid, signal.SIGHUP)
            except Exception as e:
                logger.error(f"Failed to signal Gunicorn: {e}")
        else:
            logger.debug("Gunicorn PID file not found, skipping Gunicorn reload.")

    @staticmethod
    def _check_syntax(file_path: str) -> bool:
        """Check if a python file has syntax errors."""
        try:
            with open(file_path, 'r') as f:
                source = f.read()
            compile(source, file_path, 'exec')
            return True
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return False
            
    @staticmethod
    async def _run_migrations(app_name: str):
        """Run Django migrations for the specific app."""
        from asgiref.sync import sync_to_async
        
        try:
            # Sync migrations to DB
            await sync_to_async(call_command)('makemigrations', app_name)
            await sync_to_async(call_command)('migrate', app_name)
            logger.info(f"Migrations applied for {app_name}")
        except Exception as e:
            logger.error(f"Migration error during reload: {e}")
            raise e

# Singleton instance
app_reloader = DynamicAppReloader()
