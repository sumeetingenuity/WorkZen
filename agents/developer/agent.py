"""
Developer Agent - Coordinates code generation using OpenCode CLI.

Translates AppSpec into OpenCode prompts and manages the generation process.
"""
import logging
from typing import Optional
from pathlib import Path
from django.conf import settings
from agents.schemas import AppSpec, EntitySpec, ToolSpec
from agents.developer.opencode_executor import opencode_executor, GenerationResult
from core.services.reloader import app_reloader
from core.services.git_service import git_service

logger = logging.getLogger(__name__)


class DeveloperAgent:
    """
    Developer agent that uses OpenCode CLI to generate Django apps.
    
    Flow:
    1. Receive AppSpec from Orchestrator
    2. Generate OpenCode prompt from spec
    3. Execute OpenCode in non-interactive mode
    4. Validate generated code
    5. Register new app with Django
    """
    
    def __init__(self):
        self.base_dir = str(settings.BASE_DIR)
    
    async def build_app(self, app_spec: AppSpec, model: Optional[str] = None) -> dict:
        """
        Build a complete Django app from specification.
        
        Args:
            app_spec: Complete app specification
            
        Returns:
            Result dict with success status and details
        """
        logger.info(f"Building app: {app_spec.name}")
        
        # 1. Pre-build checkpoint
        git_service.checkpoint(f"Pre-generation checkpoint for {app_spec.name}")
        
        # Check if OpenCode is available
        if not opencode_executor.is_available():
            return {
                "success": False,
                "error": "OpenCode CLI not installed",
                "message": "Install with: curl -fsSL https://opencode.ai/install | bash"
            }
        
        # Generate the app structure prompt
        prompt = self._generate_app_prompt(app_spec)
        
        # Execute OpenCode
        result = await opencode_executor.generate_django_app(
            app_name=app_spec.name,
            app_spec=prompt,
            base_dir=self.base_dir,
            model=model
        )
        
        if not result.success:
            app_dir = Path(self.base_dir) / "apps" / app_spec.name
            if result.error and "tools.py" in result.error:
                required_files = ["apps.py", "models.py", "admin.py"]
                if all((app_dir / f).exists() for f in required_files):
                    logger.warning(f"OpenCode missed tools.py for {app_spec.name}; generating fallback tools.")
                    generated = await self._generate_tools_file(app_spec, app_dir)
                    if generated:
                        result.success = True
                    else:
                        return {
                            "success": False,
                            "error": "Failed to generate fallback tools.py",
                            "output": result.output
                        }
                else:
                    return {
                        "success": False,
                        "error": result.error,
                        "output": result.output
                    }
            else:
                return {
                    "success": False,
                    "error": result.error,
                    "output": result.output
                }

        # Ensure core files exist before registering app
        app_dir = Path(self.base_dir) / "apps" / app_spec.name
        required_files = ["apps.py", "models.py", "tools.py", "admin.py"]
        missing_files = [f for f in required_files if not (app_dir / f).exists()]
        if "tools.py" in missing_files:
            logger.warning(f"tools.py missing for {app_spec.name}; generating fallback tools.")
            generated = await self._generate_tools_file(app_spec, app_dir)
            if generated:
                missing_files = [f for f in required_files if not (app_dir / f).exists()]
        else:
            tools_path = app_dir / "tools.py"
            if tools_path.exists():
                try:
                    compile(tools_path.read_text(), str(tools_path), "exec")
                except SyntaxError:
                    logger.warning(f"tools.py has syntax errors for {app_spec.name}; regenerating fallback tools.")
                    await self._generate_tools_file(app_spec, app_dir)
        if missing_files:
            return {
                "success": False,
                "error": f"OpenCode did not create required files: {', '.join(missing_files)}"
            }
        
        # Update Django settings to include new app
        settings_updated = await self._update_settings(app_spec)
        
        # Run migrations for new app
        migrations_result = await self._run_migrations(app_spec.name)
        
        # 3. Apply migrations and reload app
        logger.info(f"App files created. Triggering hot-reload for {app_spec.name}...")
        reload_success = await app_reloader.reload_app(app_spec.name)
        if not reload_success:
            logger.warning("Hot-reload failed; continuing with generation results.")
        
        # 4. Register tools from the new app
        tools_registered = await self._register_tools(app_spec)
            
        # 5. Self-Correction Loop (Phase 10)
        validation_result = await self._validate_and_fix(app_spec, model=model)
        if not validation_result["success"]:
            return validation_result
        
        # 6. Success Checkpoint
        git_service.checkpoint(f"Successfully generated and validated {app_spec.name}")

        return {
            "success": True,
            "app_name": app_spec.name,
            "app_path": app_spec.get_app_path(self.base_dir),
            "files_created": result.files_created,
            "settings_updated": settings_updated,
            "migrations_run": migrations_result,
            "tools_registered": tools_registered,
            "message": f"Successfully created and validated {app_spec.display_name}!"
        }
    
    def _generate_app_prompt(self, app_spec: AppSpec) -> str:
        """Generate detailed prompt for OpenCode with strict architecture enforcement."""
        
        # Build entities section
        entities_desc = []
        for entity in app_spec.entities:
            fields_desc = []
            for field in entity.fields:
                field_str = f"  - {field.name}: {field.field_type.value}"
                if field.max_length:
                    field_str += f"(max_length={field.max_length})"
                if not field.required:
                    field_str += " (optional)"
                if field.related_model:
                    field_str += f" -> {field.related_model}"
                fields_desc.append(field_str)
            
            entities_desc.append(f"""
{entity.name}:
  Description: {entity.description}
  Fields:
{chr(10).join(fields_desc)}
  Include UUID primary key: {entity.include_uuid}
  Include timestamps: {entity.include_timestamps}
""")
        
        # Build tools section
        tools_desc = []
        for tool in app_spec.tools:
            tool_str = f"- {tool.name}: {tool.description}"
            if tool.requires_approval:
                tool_str += " [REQUIRES APPROVAL]"
            if tool.secrets:
                tool_str += f" [MANDATORY SECRETS: {', '.join(tool.secrets)}]"
            tools_desc.append(tool_str)
        
        return f"""
App Name: {app_spec.name}
Display Name: {app_spec.display_name}
Description: {app_spec.description}

=== SECURITY ARCHITECTURE RULES (CRITICAL) ===
1. MUST import @agent_tool from `core.decorators`.
2. ALL tools MUST use `@agent_tool(..., log_response_to_orm=True)`.
3. NO tool should return large data directly to the LLM. 
4. SECRETS: Any tool requiring API keys MUST list them in the `secrets` argument of `@agent_tool`.
5. SECRET ENGINE: All secrets are injected at runtime by SecretEngine; NEVER read env files.
6. RUNTIME SECRETS: Access secrets ONLY via injected `_secret_NAME` parameters (add them to the function signature).
7. NO ENV SCANNING: DO NOT search for or read `.env` files. Sensitive keys are stored in a secure OUT-OF-WORKSPACE vault inaccessible to you.
8. NO LLM INGESTION: Tool results are for the USER, not for the LLM.

=== TOOL DESCRIPTION FORMAT (CRITICAL) ===
Every tool MUST have a comprehensive description following this format:

@agent_tool(
    name="tool_name",
    description=\"\"\"Brief one-line summary.
    
    REQUIRED PARAMETERS:
    - param1 (type): Description with example (e.g., 'John Doe')
    - param2 (type): Description with example
    
    OPTIONAL PARAMETERS:
    - param3 (type, default=value): Description
    
    EXAMPLES:
    1. Basic: tool_name(param1='value1', param2='value2')
    2. Advanced: tool_name(param1='value1', param2='value2', param3='value3')
    
    RETURNS:
    - status: Success/error indicator
    - data: Result data
    - display_markdown: User-friendly output
    
    IMPORTANT: [Critical notes]\"\"\",
    category="{app_spec.name}",
    log_response_to_orm=True
)

WHY: The LLM needs explicit parameter docs to call tools correctly. Without examples, 
it may pass empty dicts or wrong types, causing validation errors.

CHECKLIST FOR EACH TOOL:
✓ One-line summary
✓ REQUIRED PARAMETERS with types and examples
✓ OPTIONAL PARAMETERS (if any)
✓ EXAMPLES with 1-3 concrete usage examples
✓ RETURNS explaining output structure
✓ IMPORTANT with critical notes
✓ For dict/list params, show expected structure

=== REQUIRED FILES (MUST CREATE ALL) ===
1. apps.py with AppConfig class name {app_spec.name.title()}Config and name = "apps.{app_spec.name}"
2. models.py with ALL models defined in the spec
3. tools.py with @agent_tool functions for every tool in the spec (with comprehensive descriptions!)
4. admin.py registering all models

=== MODELS ===
{''.join(entities_desc)}

=== TOOLS (with @agent_tool decorator) ===
{chr(10).join(tools_desc)}

=== ADDITIONAL REQUIREMENTS ===
1. Use UUID as primary key for all models.
2. Use Django 6's async ORM methods (aget, acreate, alist, etc.).
3. Tools should be async and focus on discrete operations (CRUD or API actions).
4. Include robust error handling that returns a dict with 'error' or 'success' fields.
5. USER-FACING OUTPUT: ALL tools MUST return a "display_markdown" key in the result dict. This should be a user-friendly Markdown summary of the action (e.g., "✅ Client **John Doe** created successfully."). The system consumes this to show the user.
6. Register models in admin.py for visibility.
7. Function signatures MUST place required params BEFORE optional params (no defaults before required).
8. tools.py MUST import models from `.models` and use async ORM.
"""
    
    async def _update_settings(self, app_spec: AppSpec) -> bool:
        """Update Django settings to include the new app."""
        try:
            settings_path = Path(self.base_dir) / "secureassist" / "settings.py"
            content = settings_path.read_text()
            
            app_config = f"'apps.{app_spec.name}.apps.{app_spec.name.title()}Config'"
            
            # Check if already added
            if app_config in content:
                logger.info(f"App {app_spec.name} already in INSTALLED_APPS")
                return True
            
            # Find INSTALLED_APPS and add the new app
            if "INSTALLED_APPS" in content:
                # Add before the closing bracket
                new_content = content.replace(
                    "'integrations.telegram_bot.apps.TelegramBotConfig',",
                    f"'integrations.telegram_bot.apps.TelegramBotConfig',\n    {app_config},"
                )
                settings_path.write_text(new_content)
                logger.info(f"Added {app_spec.name} to INSTALLED_APPS")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update settings: {e}")
            return False
    
    async def _run_migrations(self, app_name: str) -> bool:
        """Run migrations for the new app."""
        import asyncio
        import sys
        
        try:
            # Make migrations
            process = await asyncio.create_subprocess_exec(
                sys.executable, "manage.py", "makemigrations", app_name,
                cwd=self.base_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            
            # Apply migrations
            process = await asyncio.create_subprocess_exec(
                sys.executable, "manage.py", "migrate", app_name,
                cwd=self.base_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0
            if success:
                logger.info(f"Migrations applied for {app_name}")
            else:
                logger.error(f"Migration failed: {stderr.decode()}")
            
            return success
            
        except Exception as e:
            logger.error(f"Migration error: {e}")
            return False

    async def _generate_tools_file(self, app_spec: AppSpec, app_dir: Path) -> bool:
        """Generate a minimal tools.py file if OpenCode missed it."""
        try:
            from textwrap import indent

            def _py_type(field) -> str:
                mapping = {
                    "CharField": "str",
                    "TextField": "str",
                    "EmailField": "str",
                    "FileField": "str",
                    "ImageField": "str",
                    "JSONField": "dict",
                    "UUIDField": "str",
                    "ForeignKey": "str",
                    "ManyToManyField": "list[str]",
                    "IntegerField": "int",
                    "FloatField": "float",
                    "DecimalField": "float",
                    "BooleanField": "bool",
                    "DateTimeField": "str",
                    "DateField": "str",
                }
                return mapping.get(field.field_type.value, "str")
            
            def _build_comprehensive_description(tool, entity=None) -> str:
                """Build a comprehensive tool description with parameters and examples."""
                desc_lines = [tool.description]
                desc_lines.append("")
                
                # Build parameter documentation
                required_params = []
                optional_params = []
                
                if tool.operation in {"read", "update", "delete"}:
                    required_params.append("- id (str): UUID of the record to operate on")
                
                if tool.operation in {"create", "update"} and entity:
                    for field in entity.fields:
                        param_type = _py_type(field)
                        param_desc = f"- {field.name} ({param_type}): {field.name.replace('_', ' ').title()}"
                        if field.required:
                            required_params.append(param_desc)
                        else:
                            optional_params.append(f"{param_desc} (optional)")
                
                if tool.operation == "search":
                    optional_params.append("- limit (int, default=20): Maximum number of results")
                
                if required_params:
                    desc_lines.append("REQUIRED PARAMETERS:")
                    desc_lines.extend(required_params)
                    desc_lines.append("")
                
                if optional_params:
                    desc_lines.append("OPTIONAL PARAMETERS:")
                    desc_lines.extend(optional_params)
                    desc_lines.append("")
                
                # Add examples
                desc_lines.append("EXAMPLES:")
                if tool.operation == "create" and entity:
                    example_params = []
                    for field in entity.fields[:3]:  # First 3 fields as example
                        if field.required:
                            example_val = "'example_value'" if _py_type(field) == "str" else "123"
                            example_params.append(f"{field.name}={example_val}")
                    if example_params:
                        desc_lines.append(f"1. {tool.name}({', '.join(example_params)})")
                elif tool.operation == "read":
                    desc_lines.append(f"1. {tool.name}(id='123e4567-e89b-12d3-a456-426614174000')")
                elif tool.operation == "search":
                    desc_lines.append(f"1. {tool.name}(limit=10)")
                desc_lines.append("")
                
                # Add returns
                desc_lines.append("RETURNS:")
                if tool.operation == "create":
                    desc_lines.append("- id: UUID of created record")
                elif tool.operation == "read":
                    desc_lines.append("- data: Record data as dict")
                elif tool.operation == "search":
                    desc_lines.append("- results: List of matching records")
                desc_lines.append("- display_markdown: User-friendly formatted output")
                desc_lines.append("")
                
                desc_lines.append("IMPORTANT: Always provide all required parameters. Do not call with empty values.")
                
                return "\\n    ".join(desc_lines)

            model_imports = ", ".join(sorted({e.name for e in app_spec.entities}))
            lines = [
                '"""',
                f"Auto-generated tools for {app_spec.display_name}.",
                '"""',
                "from core.decorators import agent_tool",
                "from asgiref.sync import sync_to_async",
                f"from .models import {model_imports}",
                "",
                "def _to_dict(obj):",
                "    data = {}",
                "    for field in obj._meta.fields:",
                "        data[field.name] = getattr(obj, field.name)",
                "    return data",
                "",
            ]

            for tool in app_spec.tools:
                model_name = tool.entity
                model_var = model_name
                tool_name = tool.name
                secrets = tool.secrets or []
                secrets_arg = f", secrets={secrets}" if secrets else ""
                
                # Get entity for parameter info
                entity = next((e for e in app_spec.entities if e.name == model_name), None)
                
                # Build comprehensive description
                comprehensive_desc = _build_comprehensive_description(tool, entity)

                params = []
                if tool.operation in {"read", "update", "delete"}:
                    params.append("id: str")
                if tool.operation in {"create", "update"}:
                    if entity:
                        required_params = []
                        optional_params = []
                        for field in entity.fields:
                            param_type = _py_type(field)
                            if field.required:
                                required_params.append(f"{field.name}: {param_type}")
                            else:
                                optional_params.append(f"{field.name}: {param_type} = None")
                        params.extend(required_params + optional_params)
                if tool.operation == "search":
                    params.append("limit: int = 20")

                params_str = ", ".join(params)
                lines.extend([
                    "@agent_tool(",
                    f"    name=\"{tool_name}\",",
                    f"    description=\"\"\"{ comprehensive_desc}\"\"\",",
                    "    log_response_to_orm=True,",
                    f"    category=\"{app_spec.name}\"{secrets_arg}",
                    ")",
                    f"async def {tool_name}({params_str}) -> dict:",
                ])

                if tool.operation == "create":
                    lines.append(indent(f"obj = await sync_to_async({model_var}.objects.create)(**{{k: v for k, v in locals().items() if k != 'obj'}})", "    "))
                    lines.append(indent("return {\"id\": str(obj.id), \"display_markdown\": f\"✅ Created {obj}\"}", "    "))
                elif tool.operation == "read":
                    lines.append(indent(f"obj = await sync_to_async({model_var}.objects.get)(id=id)", "    "))
                    lines.append(indent("return {\"data\": _to_dict(obj), \"display_markdown\": f\"✅ Loaded {obj}\"}", "    "))
                elif tool.operation == "update":
                    lines.append(indent(f"obj = await sync_to_async({model_var}.objects.get)(id=id)", "    "))
                    lines.append(indent("for k, v in locals().items():\n        if k not in ('id', 'obj') and v is not None:\n            setattr(obj, k, v)", "    "))
                    lines.append(indent("await sync_to_async(obj.save)()", "    "))
                    lines.append(indent("return {\"id\": str(obj.id), \"display_markdown\": f\"✅ Updated {obj}\"}", "    "))
                elif tool.operation == "delete":
                    lines.append(indent(f"obj = await sync_to_async({model_var}.objects.get)(id=id)", "    "))
                    lines.append(indent("await sync_to_async(obj.delete)()", "    "))
                    lines.append(indent("return {\"status\": \"deleted\", \"display_markdown\": \"✅ Deleted\"}", "    "))
                elif tool.operation == "search":
                    lines.append(indent(f"qs = await sync_to_async(list)({model_var}.objects.all()[:limit])", "    "))
                    lines.append(indent("return {\"results\": [_to_dict(o) for o in qs], \"display_markdown\": f\"✅ Found {len(qs)}\"}", "    "))
                else:
                    lines.append(indent("return {\"status\": \"not_implemented\", \"display_markdown\": \"⚠️ Not implemented\"}", "    "))
                lines.append("")

            (app_dir / "tools.py").write_text("\n".join(lines))
            return True
        except Exception as e:
            logger.error(f"Failed to generate tools.py: {e}")
            return False
    
    async def _register_tools(self, app_spec: AppSpec) -> int:
        """Discover and register new tools from the created app."""
        try:
            from core.registry import capability_registry
            
            # Force re-discovery
            capability_registry.discover_tools()
            
            # Count tools in the new category
            registry = capability_registry.get_full_registry()
            if app_spec.name in registry:
                tools_count = len(registry[app_spec.name].get("tools", []))
                logger.info(f"Registered {tools_count} tools for {app_spec.name}")
                return tools_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Tool registration error: {e}")
            return 0

    def _validate_generated_app(self, app_spec: AppSpec) -> list[str]:
        """Return a list of validation issues for the generated app."""
        issues = []
        app_dir = Path(self.base_dir) / "apps" / app_spec.name
        required_files = ["apps.py", "models.py", "tools.py", "admin.py"]
        for filename in required_files:
            if not (app_dir / filename).exists():
                issues.append(f"missing_file:{filename}")

        tools_path = app_dir / "tools.py"
        if tools_path.exists():
            try:
                compile(tools_path.read_text(), str(tools_path), "exec")
            except SyntaxError as exc:
                issues.append(f"tools_syntax:{exc.msg}")
        return issues

    async def _validate_and_fix(self, app_spec: AppSpec, attempts: int = 3, model: Optional[str] = None) -> dict:
        """
        Validate the generated app and attempt to fix it if it fails.
        """
        for i in range(attempts):
            logger.info(f"Validation attempt {i+1} for {app_spec.name}")
            
            try:
                issues = self._validate_generated_app(app_spec)
                if issues:
                    logger.warning(f"Validation issues for {app_spec.name}: {issues}")
                    app_dir = Path(self.base_dir) / "apps" / app_spec.name
                    if any(issue.startswith("missing_file:tools.py") for issue in issues) or any(
                        issue.startswith("tools_syntax:") for issue in issues
                    ):
                        logger.info(f"Regenerating tools.py for {app_spec.name} due to validation issues.")
                        await self._generate_tools_file(app_spec, app_dir)
                        issues = self._validate_generated_app(app_spec)
                        if not issues:
                            logger.info(f"App {app_spec.name} validated successfully after tools.py regeneration.")
                            return {"success": True}

                # Attempt to import the tools module to trigger any syntax/import errors
                import importlib
                import sys
                
                # Force reload of the specific module if it was already loaded
                module_path = f"apps.{app_spec.name}.tools"
                if module_path in sys.modules:
                    del sys.modules[module_path]
                
                importlib.import_module(module_path)
                logger.info(f"App {app_spec.name} validated successfully.")
                return {"success": True}
                
            except (SyntaxError, ImportError, NameError, Exception) as e:
                import traceback
                error_trace = traceback.format_exc()
                logger.warning(f"Validation failed for {app_spec.name}:\n{error_trace}")
                
                if i == attempts - 1:
                    return {
                        "success": False, 
                        "error": f"Failed to fix app after {attempts} attempts.",
                        "traceback": error_trace
                    }
                
                # Attempt to fix using OpenCode
                logger.info(f"Attempting to fix {app_spec.name} using OpenCode CLI...")
                
                # Get current diff for context
                context_diff = git_service.get_last_diff()
                
                fix_prompt = f"""
The previously generated app '{app_spec.name}' has errors. 
Please FIX the code based on this traceback:

{error_trace}

=== RE-ENFORCE RULES ===
1. Ensure all imports are correct.
2. Ensure @agent_tool is imported from `core.decorators`.
3. Check for indentation or basic Python syntax errors.
4. REQUIRED FILES: apps.py, models.py, tools.py, admin.py must all exist.
5. Function signatures MUST place required params BEFORE optional params.

=== CURRENT CHANGES (for context) ===
{context_diff[:5000]}
"""
                await opencode_executor.generate_django_app(
                    app_name=app_spec.name,
                    app_spec=fix_prompt,
                    base_dir=self.base_dir,
                    model=model
                )
                
                # Hot-reload again after fix
                await app_reloader.reload_app(app_spec.name)
        
        return {"success": False, "error": "Exhausted attempts"}

    async def recover_app(self, app_spec: AppSpec, model: Optional[str] = None) -> dict:
        """Attempt to recover a partially generated app."""
        try:
            validation = await self._validate_and_fix(app_spec, model=model)
            if not validation["success"]:
                return validation

            await self._run_migrations(app_spec.name)
            await app_reloader.reload_app(app_spec.name)
            tools_registered = await self._register_tools(app_spec)
            return {"success": True, "tools_registered": tools_registered}
        except Exception as e:
            logger.error(f"Recovery failed for {app_spec.name}: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
developer_agent = DeveloperAgent()
