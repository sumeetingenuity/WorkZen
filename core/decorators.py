"""
@agent_tool decorator - The core abstraction for creating agent-callable tools.

This decorator transforms regular functions into secure, validated, audited tools
that can be called by the LLM orchestrator.

Key features:
1. Auto-generates JSON schema from type hints
2. Handles secret injection at runtime (never exposed to LLM)
3. Logs responses directly to ORM (bypasses LLM token consumption)
4. Enforces policy checks before execution
5. Uses Django 6 built-in tasks for background execution
"""
from functools import wraps
from typing import TypeVar, Callable, Any, Optional, get_type_hints
from pydantic import BaseModel, create_model
import inspect
import asyncio
import hashlib
import time
import logging
import uuid

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


def agent_tool(
    name: str,
    description: str,
    secrets: list[str] = None,
    requires_approval: bool = False,
    timeout_seconds: int = 30,
    log_response_to_orm: bool = True,
    response_model: Optional[str] = None,
    category: str = "general",
    run_in_background: bool = False  # Use Django 6 tasks for background execution
) -> Callable[[F], F]:
    """
    Decorator that transforms a function into an agent-callable tool.
    
    Args:
        name: Unique identifier for the tool (used by LLM to call it)
        description: Human-readable description (shown to LLM for tool selection)
        secrets: List of secret names required (injected at runtime)
        requires_approval: If True, user must approve before execution
        timeout_seconds: Maximum execution time before timeout
        log_response_to_orm: If True, full response logged to database
        response_model: Django model name for typed response storage
        category: Category for capability registry grouping
        run_in_background: If True, use Django 6 tasks for async execution
    
    Usage:
        @agent_tool(
            name="search_web",
            description="Search the web for information",
            secrets=["TAVILY_API_KEY"],
            log_response_to_orm=True,
        )
        async def search_web(query: str, max_results: int = 5) -> dict:
            ...
    
    The LLM simply calls: @search_web(query="Django best practices")
    - Response is stored in DB and shown to user
    - LLM only gets a summary (saves tokens)
    """
    def decorator(func: F) -> F:
        # Extract function signature for auto-schema generation
        sig = inspect.signature(func)
        type_hints = get_type_hints(func) if hasattr(func, '__annotations__') else {}
        has_var_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )
        if secrets and not has_var_kwargs:
            missing_secret_params = [
                secret_name
                for secret_name in secrets
                if f"_secret_{secret_name}" not in sig.parameters
            ]
            if missing_secret_params:
                missing_list = ", ".join(missing_secret_params)
                raise ValueError(
                    f"Tool '{name}' declares secrets but is missing required "
                    f"parameters: {missing_list}. Add _secret_<NAME> args or "
                    f"accept **kwargs for secret injection."
                )
        
        # Build input fields for Pydantic model
        input_fields = {}
        for param_name, param in sig.parameters.items():
            if param_name in ['self', 'cls']:
                continue
            if param_name.startswith('_secret_'):
                continue
                
            field_type = type_hints.get(param_name, Any)
            if param.default is param.empty:
                default = ...  # Required field
            else:
                default = param.default
            input_fields[param_name] = (field_type, default)
        
        # Create Pydantic model for input validation
        InputModel = create_model(f'{name}_Input', **input_fields) if input_fields else None
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from core.services.policy import PolicyEngine
            from core.services.secrets import SecretEngine
            from core.services.audit import AuditLogger
            from core.services.orm_logger import ToolResponseLogger
            
            execution_id = str(uuid.uuid4())
            start_time = time.time()
            user_id = kwargs.pop('_user_id', None)
            session_id = kwargs.pop('_session_id', None)
            
            logger.info(f"Tool execution started: {name} (id={execution_id})")
            
            try:
                # 1. Policy Check
                policy_engine = PolicyEngine()
                if not await policy_engine.check_permission(name, kwargs, user_id):
                    logger.warning(f"Tool {name} denied for user {user_id}")
                    raise PermissionError(f"Tool '{name}' not permitted")
                
                # 2. Approval Check
                if requires_approval:
                    approval = kwargs.pop('_approved', False)
                    if not approval:
                        return {
                            "status": "pending_approval",
                            "task_id": execution_id,
                            "tool": name,
                            "description": description,
                            "input_summary": str(kwargs)[:200]
                        }
                
                # 3. Secret Injection (runtime only - NEVER in LLM context)
                secret_engine = SecretEngine()
                if secrets:
                    for secret_name in secrets:
                        secret_value = await secret_engine.get(secret_name)
                        if secret_value is None:
                            raise ValueError(f"Required secret '{secret_name}' not found")
                        kwargs[f'_secret_{secret_name}'] = secret_value
                
                # 4. Input Validation
                if InputModel:
                    validation_kwargs = {
                        k: v for k, v in kwargs.items() 
                        if not k.startswith('_secret_')
                    }
                    validated_input = InputModel(**validation_kwargs)
                    validated_dict = validated_input.model_dump()
                    for k, v in kwargs.items():
                        if k.startswith('_secret_'):
                            validated_dict[k] = v
                else:
                    validated_dict = kwargs
                
                # 5. Execute with timeout
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **validated_dict),
                        timeout=timeout_seconds
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: func(*args, **validated_dict)),
                        timeout=timeout_seconds
                    )
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # 6. Mask any leaked secrets
                if secrets:
                    result = secret_engine.mask_in_output(result)
                
                # 7. Log to ORM (bypass LLM token consumption)
                if log_response_to_orm:
                    logged_input = {
                        k: v for k, v in validated_dict.items()
                        if not k.startswith('_secret_')
                    }
                    await ToolResponseLogger.log(
                        tool_name=name,
                        model_name=response_model,
                        input_data=logged_input,
                        output_data=result,
                        session_id=session_id,
                        execution_time_ms=execution_time_ms
                    )
                
                # 8. Audit Log
                await AuditLogger.log(
                    action="tool_execution",
                    tool=name,
                    execution_id=execution_id,
                    user_id=user_id,
                    input_summary=str(kwargs)[:500],
                    output_summary=_summarize_output(result),
                    status="success",
                    execution_time_ms=execution_time_ms
                )
                
                logger.info(f"Tool completed: {name} (time={execution_time_ms}ms)")
                return result
                
            except asyncio.TimeoutError:
                logger.error(f"Tool {name} timed out")
                await AuditLogger.log(
                    action="tool_execution",
                    tool=name,
                    execution_id=execution_id,
                    status="timeout"
                )
                return {"error": f"Timed out after {timeout_seconds}s", "status": "timeout"}
                
            except PermissionError as e:
                await AuditLogger.log(
                    action="tool_execution",
                    tool=name,
                    execution_id=execution_id,
                    status="denied",
                    error=str(e)
                )
                raise
                
            except Exception as e:
                logger.exception(f"Tool {name} failed: {e}")
                await AuditLogger.log(
                    action="tool_execution",
                    tool=name,
                    execution_id=execution_id,
                    status="error",
                    error=str(e)
                )
                return {"error": str(e), "status": "error"}
        
        # Store metadata for registry
        wrapper._tool_meta = {
            "name": name,
            "description": description,
            "input_schema": InputModel.model_json_schema() if InputModel else {},
            "secrets": secrets or [],
            "requires_approval": requires_approval,
            "category": category,
            "timeout_seconds": timeout_seconds,
            "response_model": response_model,
            "run_in_background": run_in_background
        }
        
        # Auto-register with capability registry
        try:
            from core.registry import capability_registry
            capability_registry.register_tool(wrapper)
        except Exception as e:
            logger.debug(f"Could not auto-register tool: {e}")
        
        return wrapper
    
    return decorator


def _summarize_output(output: Any, max_length: int = 200) -> str:
    """Generate a concise summary of tool output."""
    if isinstance(output, dict):
        if 'error' in output:
            return f"Error: {output['error'][:max_length]}"
        if 'status' in output:
            return f"Status: {output['status']}"
        for key in ['results', 'items', 'data', 'records']:
            if key in output and isinstance(output[key], list):
                return f"Returned {len(output[key])} {key}"
        return str(output)[:max_length]
    elif isinstance(output, list):
        return f"Returned list with {len(output)} items"
    elif isinstance(output, str):
        return output[:max_length]
    else:
        return str(output)[:max_length]
