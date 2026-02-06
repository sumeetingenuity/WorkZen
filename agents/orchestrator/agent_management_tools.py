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
    secrets=["OPENCODE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
)
async def run_opencode_command(
    instruction: str, 
    model: Optional[str] = None, 
    _secret_OPENCODE_API_KEY: str = None,
    _secret_OPENAI_API_KEY: str = None,
    _secret_ANTHROPIC_API_KEY: str = None,
    _secret_GEMINI_API_KEY: str = None
) -> dict:
    import subprocess
    import os
    import json
    
    # Construct OpenCode configuration JSON
    # Documentation: https://opencode.ai/docs/config/
    opencode_config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {}
    }
    
    # Add Anthropic
    if _secret_ANTHROPIC_API_KEY:
        opencode_config["provider"]["anthropic"] = {
            "options": {"apiKey": _secret_ANTHROPIC_API_KEY}
        }
    
    # Add OpenAI
    if _secret_OPENAI_API_KEY:
        opencode_config["provider"]["openai"] = {
            "options": {"apiKey": _secret_OPENAI_API_KEY}
        }
        
    # Add Google
    if _secret_GEMINI_API_KEY:
        opencode_config["provider"]["google-vertex"] = {
            "options": {"apiKey": _secret_GEMINI_API_KEY}
        }
        
    # Add OpenCode Zen
    if _secret_OPENCODE_API_KEY:
        opencode_config["provider"]["opencode-zen"] = {
            "options": {"apiKey": _secret_OPENCODE_API_KEY}
        }

    # Set default model if provided or in env
    from django.conf import settings
    # Dynamic model logic:
    # 1. Provided 'model' argument
    # 2. Provided 'agent_name' lookup (if we added it to the tool)
    # 3. Environment variable
    # 4. Hardcoded default
    default_model = model or os.environ.get("OPENCODE_MODEL", "anthropic/claude-3-5-sonnet")
    opencode_config["model"] = default_model
    
    env = os.environ.copy()
    # Inject config via environment variable as per user request and docs
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(opencode_config)
    
    # Support for systems where opencode might not be in PATH yet
    opencode_bin = os.path.expanduser("~/.opencode/bin/opencode")
    cmd_path = "opencode" if subprocess.run(["which", "opencode"], capture_output=True).returncode == 0 else opencode_bin

    cmd = [cmd_path, "run", instruction]
        
    try:
        # Run in a subshell to capture output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )
        stdout, stderr = process.communicate(timeout=300) # 5 min timeout for coding tasks
        
        if process.returncode == 0:
            return {"status": "success", "output": stdout}
        else:
            return {"status": "error", "error": stderr or "Unknown error"}
            
    except subprocess.TimeoutExpired:
        process.kill()
        return {"status": "error", "error": "OpenCode task timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
