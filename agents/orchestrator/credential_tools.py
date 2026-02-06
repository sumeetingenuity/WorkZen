"""
Credential Management Tools for SecureAssist.
"""
from core.decorators import agent_tool
from core.services.secrets import SecretEngine
from asgiref.sync import sync_to_async

secret_engine = SecretEngine()

@agent_tool(
    name="request_secure_credential",
    description="Check if a specific API key or credential exists. If missing, this tool will trigger a secure input request from the user. Use this when a third-party service requires auth.",
    category="security"
)
async def request_secure_credential(name: str, description: str = "Required for third-party integration") -> dict:
    """
    Check for a credential. If missing, signal the runtime to prompt the user.
    """
    value = await secret_engine.get(name)
    if value:
        return {
            "status": "exists", 
            "message": f"Credential '{name}' is already configured and ready for use."
        }
    else:
        # Special signal intercepted by the Bot/Runtime
        return {
            "status": "missing",
            "signal": "WAITING_FOR_SECRET",
            "secret_name": name,
            "description": description,
            "instructions": f"The '{name}' credential is missing. I've sent a secure prompt to your interface. Please provide it there."
        }
