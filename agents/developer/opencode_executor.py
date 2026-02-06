"""
OpenCode Executor - Executes OpenCode CLI for code generation.

Uses OpenCode's non-interactive mode to generate Django apps.
"""
import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GenerationResult(BaseModel):
    """Result from OpenCode execution."""
    success: bool
    output: str = ""
    error: str = ""
    files_created: list[str] = []
    files_modified: list[str] = []


class OpenCodeExecutor:
    """
    Execute OpenCode CLI commands for code generation.
    
    OpenCode must be installed and configured with API keys.
    """
    
    def __init__(self):
        self.opencode_path = shutil.which("opencode") or "opencode"
        
    def is_available(self) -> bool:
        """Check if OpenCode CLI is available."""
        return shutil.which("opencode") is not None
    
    async def generate(
        self,
        prompt: str,
        working_dir: str,
        model: Optional[str] = None,
        timeout: int = 300  # 5 minutes default
    ) -> GenerationResult:
        """
        Run OpenCode in non-interactive mode to generate code.
        
        Args:
            prompt: The generation prompt
            working_dir: Directory to work in
            timeout: Maximum execution time in seconds
            
        Returns:
            GenerationResult with output and created files
        """
        logger.info(f"OpenCode generation in {working_dir}")
        logger.debug(f"Prompt: {prompt[:200]}...")
        
        if not self.is_available():
            return GenerationResult(
                success=False,
                error="OpenCode CLI not found. Install with: curl -fsSL https://opencode.ai/install | bash"
            )
        
        # Track files before generation
        files_before = self._list_files(working_dir)
        
        try:
            # Prepare environment with dynamic model if provided
            env = os.environ.copy()
            env["OPENCODE_NON_INTERACTIVE"] = "true"
            
            if model:
                import json
                # Construct a minimal config to force the model
                config = {
                    "$schema": "https://opencode.ai/config.json",
                    "model": model
                }
                env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)

            # Run OpenCode in non-interactive mode
            process = await asyncio.create_subprocess_exec(
                self.opencode_path,
                "--non-interactive",
                prompt,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")
            
            # Track files after generation
            files_after = self._list_files(working_dir)
            
            # Determine created/modified files
            files_created = [f for f in files_after if f not in files_before]
            files_modified = self._find_modified_files(files_before, files_after, working_dir)
            
            success = process.returncode == 0
            
            if not success:
                logger.error(f"OpenCode failed: {error_output}")
            else:
                logger.info(f"OpenCode created {len(files_created)} files")
            
            return GenerationResult(
                success=success,
                output=output,
                error=error_output if not success else "",
                files_created=files_created,
                files_modified=files_modified
            )
            
        except asyncio.TimeoutError:
            return GenerationResult(
                success=False,
                error=f"OpenCode timed out after {timeout} seconds"
            )
        except Exception as e:
            logger.exception(f"OpenCode execution failed: {e}")
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    def _list_files(self, directory: str) -> set[str]:
        """List all files in directory recursively."""
        path = Path(directory)
        if not path.exists():
            return set()
        
        return {
            str(f.relative_to(path))
            for f in path.rglob("*")
            if f.is_file() and not self._should_ignore(f)
        }
    
    def _should_ignore(self, path: Path) -> bool:
        """Check if file should be ignored."""
        ignore_patterns = [
            "__pycache__",
            ".pyc",
            ".git",
            ".venv",
            "venv",
            ".env",
            "node_modules",
        ]
        return any(pattern in str(path) for pattern in ignore_patterns)
    
    def _find_modified_files(
        self,
        before: set[str],
        after: set[str],
        directory: str
    ) -> list[str]:
        """Find files that were modified (existed before and after)."""
        # For simplicity, consider all existing files as potentially modified
        # A more sophisticated approach would compare file hashes
        return list(before & after)
    
    async def generate_django_app(
        self,
        app_name: str,
        app_spec: str,
        base_dir: str,
        model: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate a complete Django app using OpenCode.
        
        Args:
            app_name: Name of the Django app
            app_spec: Description of what the app should contain
            base_dir: Base project directory
        """
        app_dir = Path(base_dir) / "apps" / app_name
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py
        (app_dir / "__init__.py").write_text("")
        
        prompt = f"""
In the directory {app_dir}, create a complete Django app called '{app_name}' with the following specifications:

{app_spec}

Requirements:
1. Create models.py with all specified models using UUID primary keys and timestamps
2. Create tools.py with @agent_tool decorated functions for CRUD operations
3. Create admin.py with ModelAdmin for each model
4. Create apps.py with proper AppConfig
5. Follow Django best practices

Import the @agent_tool decorator from core.decorators:
from core.decorators import agent_tool

Each tool should be async and decorated like:
@agent_tool(
    name="create_entity",
    description="Description for LLM",
    log_response_to_orm=True,
    category="{app_name}"
)
async def create_entity(field1: str, field2: str) -> dict:
    ...
"""
        
        return await self.generate(prompt, str(app_dir), model=model)


# Singleton instance
opencode_executor = OpenCodeExecutor()
