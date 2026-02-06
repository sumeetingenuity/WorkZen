
import os
import django
import asyncio
import uuid
import json

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'secureassist.settings')
django.setup()

from core.models import AgentSkill, AgentPlugin, CustomAgent, Webhook, Session
from core.registry import capability_registry
from core.services.mcp import mcp_service
from core.services.webhooks import webhook_service
from asgiref.sync import sync_to_async

async def verify_models():
    print("--- 🧪 Verifying Models ---")
    
    # 1. Create a Skill
    skill = await sync_to_async(AgentSkill.objects.create)(
        name="Test Skill",
        description="A skill for testing",
        tool_names=["search_web", "send_email"]
    )
    print(f"✅ Created Skill: {skill.name}")
    
    # 2. Create a Plugin
    plugin = await sync_to_async(AgentPlugin.objects.create)(
        name="Test Plugin",
        description="A plugin for testing"
    )
    await sync_to_async(plugin.skills.add)(skill)
    print(f"✅ Created Plugin: {plugin.name}")
    
    # 3. Create a Custom Agent
    agent = await sync_to_async(CustomAgent.objects.create)(
        user_id="test_user",
        name="Test Agent",
        persona="Testing persona"
    )
    await sync_to_async(agent.skills.add)(skill)
    print(f"✅ Created Custom Agent: {agent.name}")
    
    # 4. Create a Webhook
    webhook = await sync_to_async(Webhook.objects.create)(
        user_id="test_user",
        name="Test Webhook",
        url="https://example.com/webhook",
        event_types=["tool_execution_success"]
    )
    print(f"✅ Created Webhook: {webhook.name}")
    
    return agent, skill, webhook

async def verify_registry():
    print("\n--- 🧪 Verifying Registry Filtering ---")
    tool_names = ["search_web", "send_email"]
    tools = capability_registry.get_tools_by_names(tool_names)
    print(f"✅ Fetched tools by names: {list(tools.keys())}")
    
    schemas = capability_registry.list_tools_schema(tool_names)
    print(f"✅ Fetched schemas for {len(schemas)} tools")

async def verify_mcp():
    print("\n--- 🧪 Verifying MCP Service ---")
    tools = await mcp_service.list_tools("test_user")
    print(f"✅ MCP Tool List length: {len(tools)}")
    
    session_id = str(uuid.uuid4())
    session = await sync_to_async(Session.objects.create)(
        id=session_id,
        user_id="test_user",
        session_summary="Test context summary"
    )
    context = await mcp_service.get_context(session_id)
    print(f"✅ MCP Context Summary: {context.get('summary')}")

async def verify_webhooks():
    print("\n--- 🧪 Verifying Webhook Trigger ---")
    # This won't actually hit example.com in a blocking way if implemented correctly
    # but we can verify it runs without error.
    await webhook_service.trigger(
        user_id="test_user",
        event_type="tool_execution_success",
        payload={"test": "data"}
    )
    print("✅ Webhook trigger executed (check logs for delivery status)")

async def main():
    try:
        agent, skill, webhook = await verify_models()
        await verify_registry()
        await verify_mcp()
        await verify_webhooks()
        
        # Cleanup
        await sync_to_async(CustomAgent.objects.filter(id=agent.id).delete)()
        await sync_to_async(AgentPlugin.objects.filter(name="Test Plugin").delete)()
        await sync_to_async(AgentSkill.objects.filter(id=skill.id).delete)()
        await sync_to_async(Webhook.objects.filter(id=webhook.id).delete)()
        print("\n✨ Verification Complete! Cleaned up test data.")
        
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
