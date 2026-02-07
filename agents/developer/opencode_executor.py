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
        provider: Optional[str] = None,
        timeout: int = 300,  # 5 minutes default
        expected_output_dir: Optional[str] = None
    ) -> GenerationResult:
        """
        Run OpenCode in non-interactive mode to generate code.
        
        Args:
            prompt: The generation prompt
            working_dir: Directory to work in
            model: Optional model override (e.g., 'anthropic/claude-3-5-sonnet')
            provider: Optional provider override ('anthropic', 'openai', 'gemini', 'openrouter', 'together_ai', 'local')
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
            
            # Build OpenCode config with provider support (fallback to vault/env defaults)
            import json
            env_model = os.environ.get("OPENCODE_MODEL")
            env_provider = os.environ.get("OPENCODE_PROVIDER")
            selected_model = model or env_model or "anthropic/claude-3-5-sonnet"
            selected_provider = provider or env_provider
            if not selected_provider:
                if selected_model.startswith("openrouter/"):
                    selected_provider = "openrouter"
                elif selected_model.startswith("together_ai/") or selected_model.startswith("together/"):
                    selected_provider = "together_ai"

            # Preflight provider requirements to avoid opaque CLI failures
            provider_requirements = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "together_ai": "TOGETHER_API_KEY",
                "local": "LITELLM_LOCAL_BASE_URL",
            }
            required_env = provider_requirements.get(selected_provider)
            if required_env and not env.get(required_env):
                return GenerationResult(
                    success=False,
                    error=f"Missing required environment variable: {required_env}"
                )

            def _strip_provider_prefix(model_id: str) -> str:
                for prefix in ("openrouter/", "together_ai/", "together/"):
                    if model_id.startswith(prefix):
                        return model_id.split("/", 1)[1]
                return model_id

            def _build_custom_provider(provider_name: str, model_id: str) -> tuple[str, dict]:
                if provider_name == "openrouter":
                    provider_key = "openrouter_compat"
                    return provider_key, {
                        provider_key: {
                            "npm": "@ai-sdk/openai-compatible",
                            "name": "OpenRouter (OpenAI Compatible)",
                            "options": {
                                "baseURL": "https://openrouter.ai/api/v1",
                                "apiKey": "{env:OPENROUTER_API_KEY}",
                            },
                            "models": {
                                model_id: {
                                    "name": model_id
                                }
                            }
                        }
                    }
                if provider_name == "together_ai":
                    provider_key = "together_compat"
                    return provider_key, {
                        provider_key: {
                            "npm": "@ai-sdk/openai-compatible",
                            "name": "Together AI (OpenAI Compatible)",
                            "options": {
                                "baseURL": "https://api.together.xyz/v1",
                                "apiKey": "{env:TOGETHER_API_KEY}",
                            },
                            "models": {
                                model_id: {
                                    "name": model_id
                                }
                            }
                        }
                    }
                return "", {}

            model_for_config = selected_model
            model_for_run = selected_model
            if selected_provider in {"openrouter", "together_ai"}:
                model_name = _strip_provider_prefix(selected_model)
                provider_key, _ = _build_custom_provider(selected_provider, model_name)
                if provider_key:
                    model_for_config = f"{provider_key}/{model_name}"
                    model_for_run = model_for_config
                else:
                    model_for_config = model_name
                    model_for_run = model_name
            config = {
                "$schema": "https://opencode.ai/config.json",
                "model": model_for_config
            }
            
            # Add provider-specific configuration
            if selected_provider:
                if selected_provider in {"openrouter", "together_ai"}:
                    model_name = _strip_provider_prefix(selected_model)
                    _, provider_config = _build_custom_provider(selected_provider, model_name)
                else:
                    provider_config = self._get_provider_config(selected_provider, selected_model)
                if provider_config:
                    config["provider"] = provider_config
            
            env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
            def _mask_config(cfg: dict) -> dict:
                try:
                    safe = json.loads(json.dumps(cfg))
                except Exception:
                    return {"$schema": cfg.get("$schema"), "model": cfg.get("model")}
                provider_cfg = safe.get("provider", {})
                for provider_value in provider_cfg.values():
                    options = provider_value.get("options", {})
                    if "apiKey" in options and options["apiKey"]:
                        options["apiKey"] = "<redacted>"
                return safe

            logger.debug(f"OpenCode config: {json.dumps(_mask_config(config), indent=2)}")
            if selected_provider == "openrouter":
                logger.debug(f"OpenRouter API key present: {bool(env.get('OPENROUTER_API_KEY'))}")

            async def _run_opencode(cmd: list[str]) -> tuple[int, str, str]:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=working_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                return (
                    process.returncode,
                    stdout_bytes.decode("utf-8", errors="replace"),
                    stderr_bytes.decode("utf-8", errors="replace"),
                )

            # Run OpenCode in non-interactive mode (primary)
            primary_cmd = [
                self.opencode_path,
                "--log-level", "DEBUG",
                "--print-logs",
                "run",
                "--agent",
                "build",
                "-m",
                model_for_run,
                prompt
            ]
            returncode, output, error_output = await _run_opencode(primary_cmd)
            
            # Track files after generation
            files_after = self._list_files(working_dir)
            
            # Determine created/modified files
            files_created = [f for f in files_after if f not in files_before]
            files_modified = self._find_modified_files(files_before, files_after, working_dir)

            # Ensure core Django app files exist (when expected_output_dir is provided)
            required_files = {"apps.py", "models.py", "tools.py", "admin.py"}
            missing_required = []
            if expected_output_dir:
                output_dir = Path(expected_output_dir)
                missing_required = [
                    f for f in required_files if not (output_dir / f).exists()
                ]
            
            success = returncode == 0
            
            if success and missing_required:
                success = False
                details = []
                if error_output:
                    details.append(f"OpenCode stderr:\n{error_output[:2000]}")
                if output:
                    details.append(f"OpenCode stdout:\n{output[:2000]}")
                detail_text = f"\n\n{chr(10).join(details)}" if details else ""
                error_output = (
                    "OpenCode did not generate required files: "
                    + ", ".join(sorted(missing_required))
                    + detail_text
                )
                logger.error(error_output)
            elif not success:
                # Retry without explicit model flag
                fallback_cmd = [
                    self.opencode_path,
                    "--log-level", "DEBUG",
                    "--print-logs",
                    "run",
                    "--agent",
                    "build",
                    prompt
                ]
                fallback_returncode, fallback_output, fallback_error = await _run_opencode(fallback_cmd)
                if fallback_returncode == 0:
                    output = fallback_output
                    error_output = ""
                    # Refresh file tracking after fallback run
                    files_after = self._list_files(working_dir)
                    files_created = [f for f in files_after if f not in files_before]
                    files_modified = self._find_modified_files(files_before, files_after, working_dir)
                    if expected_output_dir:
                        output_dir = Path(expected_output_dir)
                        missing_required = [
                            f for f in required_files if not (output_dir / f).exists()
                        ]
                    else:
                        missing_required = []
                    if missing_required:
                        success = False
                        details = []
                        if fallback_error:
                            details.append(f"OpenCode stderr:\n{fallback_error[:2000]}")
                        if output:
                            details.append(f"OpenCode stdout:\n{output[:2000]}")
                        detail_text = f"\n\n{chr(10).join(details)}" if details else ""
                        error_output = (
                            "OpenCode did not generate required files: "
                            + ", ".join(sorted(missing_required))
                            + detail_text
                        )
                        logger.error(error_output)
                    else:
                        success = True
                else:
                    combined_error = error_output or fallback_error or "Unknown error"
                    # If stderr is empty, include stdout to aid debugging
                    if not combined_error and (output or fallback_output):
                        combined_error = output or fallback_output
                    error_output = combined_error
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
    
    def _get_provider_config(self, provider: str, model: Optional[str] = None) -> dict:
        """
        Generate provider-specific configuration for OpenCode CLI.
        
        Uses environment variable substitution format: {env:VARIABLE_NAME}
        to securely load API keys from the secure vault.
        
        Args:
            provider: Provider name ('anthropic', 'openai', 'gemini', 'openrouter', 'together_ai', 'local')
            model: Optional model identifier
            
        Returns:
            Provider configuration dictionary for OpenCode config
        """
        provider_configs = {
            'anthropic': {
                'anthropic': {
                    'models': {},
                    'options': {
                        'apiKey': '{env:ANTHROPIC_API_KEY}'
                    }
                }
            },
            'openai': {
                'openai': {
                    'models': {},
                    'options': {
                        'apiKey': '{env:OPENAI_API_KEY}'
                    }
                }
            },
            'gemini': {
                'gemini': {
                    'models': {},
                    'options': {
                        'apiKey': '{env:GEMINI_API_KEY}'
                    }
                }
            },
            'openrouter': self._build_openai_compatible_provider(
                provider_name="openrouter",
                display_name="OpenRouter",
                base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                api_key_env="OPENROUTER_API_KEY",
                model=model
            ),
            'together_ai': self._build_openai_compatible_provider(
                provider_name="together_ai",
                display_name="Together AI",
                base_url=os.environ.get("TOGETHER_BASE_URL", "https://api.together.xyz/v1"),
                api_key_env="TOGETHER_API_KEY",
                model=model
            ),
            'local': {
                'local': {
                    'models': {},
                    'options': {
                        'baseURL': '{env:LITELLM_LOCAL_BASE_URL}'
                    }
                }
            }
        }
        
        return provider_configs.get(provider, {})

    def _build_openai_compatible_provider(
        self,
        provider_name: str,
        display_name: str,
        base_url: str,
        api_key_env: str,
        model: Optional[str] = None
    ) -> dict:
        model_name = model or ""
        if model_name.startswith(f"{provider_name}/"):
            model_name = model_name.split("/", 1)[1]
        headers = {}
        if provider_name == "openrouter":
            referrer = os.environ.get("OPENROUTER_REFERRER")
            title = os.environ.get("OPENROUTER_TITLE")
            if referrer:
                headers["HTTP-Referer"] = referrer
            if title:
                headers["X-Title"] = title
        provider = {
            provider_name: {
                "npm": "@ai-sdk/openai-compatible",
                "name": display_name,
                "options": {
                    "baseURL": base_url,
                    "apiKey": f"{{env:{api_key_env}}}",
                },
                "models": {}
            }
        }
        if headers:
            provider[provider_name]["options"]["headers"] = headers
        if model_name:
            provider[provider_name]["models"][model_name] = {
                "name": model_name
            }
        return provider
    
    async def generate_django_app(
        self,
        app_name: str,
        app_spec: str,
        base_dir: str,
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> GenerationResult:
        """
        Generate a complete Django app using OpenCode.
        
        Args:
            app_name: Name of the Django app
            app_spec: Description of what the app should contain
            base_dir: Base project directory
            model: Optional model override
            provider: Optional provider override ('anthropic', 'openai', 'gemini', 'openrouter', 'together_ai', 'local')
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
6. SECRETS: Any tool requiring API keys MUST list them in the `secrets` argument of `@agent_tool`.
7. SECRET ENGINE: Secrets are injected at runtime by SecretEngine; NEVER read `.env` or scan environment files.
8. RUNTIME SECRETS: Access secrets ONLY via injected `_secret_NAME` parameters (add them to the function signature).

TOOL TEMPLATE (use this pattern for any tool with secrets):
@agent_tool(
    name="tool_name",
    description="What the tool does",
    secrets=["PROVIDER_API_KEY"],
    log_response_to_orm=True,
    category="{app_name}"
)
async def tool_name(
    required_arg: str,
    optional_arg: str = "default",
    _secret_PROVIDER_API_KEY: str = None
) -> dict:
    # Use the injected _secret_PROVIDER_API_KEY directly.
    # Do not read from .env or os.environ here.
    ...

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
        
        return await self.generate(
            prompt,
            str(Path(base_dir)),
            model=model,
            provider=provider,
            expected_output_dir=str(app_dir)
        )


# Singleton instance
opencode_executor = OpenCodeExecutor()
