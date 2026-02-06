"""
Agent Management Tools.

Allows the orchestrator to create and configure custom agents, skills, and plugins.
"""
from typing import List, Optional, Dict, Any
from core.decorators import agent_tool
from core.models import CustomAgent, AgentSkill, AgentPlugin
from asgiref.sync import sync_to_async

@agent_tool(
    name="create_agent_skill",
    description="Create a new logical skill grouping several tools.",
    category="agent_management"
)
async def create_agent_skill(name: str, description: str, tool_names: List[str]) -> dict:
    skill = await sync_to_async(AgentSkill.objects.create)(
        name=name,
        description=description,
        tool_names=tool_names
    )
    return {"status": "success", "skill_id": str(skill.id), "name": skill.name}

@agent_tool(
    name="create_custom_agent",
    description="Define a new custom agent with a specific persona and skills.",
    category="agent_management"
)
async def create_custom_agent(
    name: str, 
    persona: str, 
    skill_names: List[str], 
    voice_profile: str = "alloy",
    model: Optional[str] = None,
    _user_id: str = None
) -> dict:
    agent = await sync_to_async(CustomAgent.objects.create)(
        user_id=_user_id,
        name=name,
        persona=persona,
        voice_profile=voice_profile,
        model_id=model
    )
    
    # Associate skills
    for skill_name in skill_names:
        try:
            skill = await sync_to_async(AgentSkill.objects.get)(name=skill_name)
            await sync_to_async(agent.skills.add)(skill)
        except AgentSkill.DoesNotExist:
            pass
            
    return {"status": "success", "agent_id": str(agent.id), "name": agent.name}

@agent_tool(
    name="run_opencode_command",
    description="Run an autonomous coding task using the OpenCode CLI.",
    category="coding",
    secrets=["OPENCODE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "LITELLM_LOCAL_BASE_URL"]
)
async def run_opencode_command(
    instruction: str, 
    model: Optional[str] = None, 
    provider: Optional[str] = None,
    _secret_OPENCODE_API_KEY: str = None,
    _secret_OPENAI_API_KEY: str = None,
    _secret_ANTHROPIC_API_KEY: str = None,
    _secret_GEMINI_API_KEY: str = None,
    _secret_OPENROUTER_API_KEY: str = None,
    _secret_TOGETHER_API_KEY: str = None,
    _secret_LITELLM_LOCAL_BASE_URL: str = None
) -> dict:
    """
    Run an autonomous coding task using the OpenCode CLI.
    
    Uses environment variable substitution format: {env:VARIABLE_NAME}
    to securely load API keys from the secure vault.
    """
    import subprocess
    import os
    import json
    
    # Get provider and model from vault/env, or use provided values
    vault_provider = os.environ.get("OPENCODE_PROVIDER", "anthropic")
    vault_model = os.environ.get("OPENCODE_MODEL", "anthropic/claude-3-5-sonnet")
    
    # Use provided values, fall back to vault/env settings
    selected_provider = provider or vault_provider
    selected_model = model or vault_model

    def _strip_provider_prefix(model_id: str) -> str:
        for prefix in ("openrouter/", "together_ai/", "together/"):
            if model_id.startswith(prefix):
                return model_id.split("/", 1)[1]
        return model_id

    model_for_config = selected_model
    model_for_run = selected_model
    model_name = _strip_provider_prefix(selected_model)
    if selected_provider in {"openrouter", "together_ai"}:
        provider_key = "openrouter_compat" if selected_provider == "openrouter" else "together_compat"
        model_for_config = f"{provider_key}/{model_name}"
        model_for_run = model_for_config
    
    # Build OpenCode configuration JSON with provider support
    opencode_config = {
        "$schema": "https://opencode.ai/config.json",
        "model": model_for_config,
        "provider": {}
    }
    
    # Add provider configurations using env var substitution format
    # This allows OpenCode to load secrets securely from the vault
    provider_configs = {
        'anthropic': {
            'anthropic': {
                'options': {'apiKey': '{env:ANTHROPIC_API_KEY}'}
            }
        },
        'openai': {
            'openai': {
                'options': {'apiKey': '{env:OPENAI_API_KEY}'}
            }
        },
        'gemini': {
            'gemini': {
                'options': {'apiKey': '{env:GEMINI_API_KEY}'}
            }
        },
        'openrouter': {
            'openrouter_compat': {
                'npm': '@ai-sdk/openai-compatible',
                'name': 'OpenRouter (OpenAI Compatible)',
                'options': {
                    'baseURL': 'https://openrouter.ai/api/v1',
                    'apiKey': _secret_OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY"),
                },
                'models': {
                    model_name: {
                        'name': model_name
                    }
                }
            }
        },
        'together_ai': {
            'together_compat': {
                'npm': '@ai-sdk/openai-compatible',
                'name': 'Together AI (OpenAI Compatible)',
                'options': {
                    'baseURL': 'https://api.together.xyz/v1',
                    'apiKey': _secret_TOGETHER_API_KEY or os.environ.get("TOGETHER_API_KEY")
                },
                'models': {
                    model_name: {
                        'name': model_name
                    }
                }
            }
        },
        'local': {
            'local': {
                'options': {'baseURL': '{env:LITELLM_LOCAL_BASE_URL}'}
            }
        }
    }
    
    if selected_provider in provider_configs:
        opencode_config["provider"] = provider_configs[selected_provider]
    
    # Set environment variables from secrets (these will be substituted by OpenCode)
    env = os.environ.copy()
    
    # Inject all potential API keys into environment for OpenCode to use
    if _secret_ANTHROPIC_API_KEY:
        env["ANTHROPIC_API_KEY"] = _secret_ANTHROPIC_API_KEY
    if _secret_OPENAI_API_KEY:
        env["OPENAI_API_KEY"] = _secret_OPENAI_API_KEY
    if _secret_GEMINI_API_KEY:
        env["GEMINI_API_KEY"] = _secret_GEMINI_API_KEY
    if _secret_OPENROUTER_API_KEY:
        env["OPENROUTER_API_KEY"] = _secret_OPENROUTER_API_KEY
    if _secret_TOGETHER_API_KEY:
        env["TOGETHER_API_KEY"] = _secret_TOGETHER_API_KEY
    if _secret_LITELLM_LOCAL_BASE_URL:
        env["LITELLM_LOCAL_BASE_URL"] = _secret_LITELLM_LOCAL_BASE_URL

    # Optional base URLs / headers for OpenAI-compatible providers
    env.setdefault("OPENROUTER_BASE_URL", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    env.setdefault("TOGETHER_BASE_URL", os.environ.get("TOGETHER_BASE_URL", "https://api.together.xyz/v1"))
    
    # Inject config via environment variable
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(opencode_config)
    env["OPENCODE_NON_INTERACTIVE"] = "true"
    
    def _is_parse_entity_error(text: Optional[str]) -> bool:
        lowered = (text or "").lower()
        return (
            "parse entity" in lowered
            or "can't parse entities" in lowered
            or "cannot find end of entity" in lowered
            or "byte offset" in lowered
            or "xml" in lowered
        )

    def _run_cmd(command: list[str]) -> tuple[int, str, str]:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(timeout=300) # 5 min timeout for coding tasks
        return process.returncode, stdout, stderr

    # Support for systems where opencode might not be in PATH yet
    opencode_bin = os.path.expanduser("~/.opencode/bin/opencode")
    cmd_path = "opencode" if subprocess.run(["which", "opencode"], capture_output=True).returncode == 0 else opencode_bin

    primary_cmd = [cmd_path, "run", "-m", model_for_run, instruction]
    fallback_cmd = [cmd_path, "--non-interactive", instruction]
        
    try:
        # Run in a subshell to capture output
        returncode, stdout, stderr = _run_cmd(primary_cmd)
        if returncode == 0:
            return {"status": "success", "output": stdout}

        # Retry using non-interactive flag for known XML/entity parsing issues
        if _is_parse_entity_error(stderr):
            retry_returncode, retry_stdout, retry_stderr = _run_cmd(fallback_cmd)
            if retry_returncode == 0:
                return {"status": "success", "output": retry_stdout}

            friendly = (
                "OpenCode returned a parsing error from the model output. "
                "This often indicates a malformed or truncated response. "
                "Try a different model/provider or update the OpenCode CLI. "
                "You can also check logs at ~/.local/share/opencode/log/."
            )
            return {
                "status": "error",
                "error": retry_stderr or stderr or "Unknown error",
                "hint": friendly
            }

        return {"status": "error", "error": stderr or "Unknown error"}
            
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "OpenCode task timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
