"""
Test script for Phase 7: Infinite Memory & VectorDB.

Simulates a long conversation to trigger:
1. Pruning
2. Summarization
3. Vector Retrieval
"""
import os
import asyncio
import uuid
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'secureassist.settings')
os.environ['MOCK_EMBEDDING'] = 'true'  # Enable mock for LanceDB
django.setup()

from agents.orchestrator.agent import orchestrator_agent
from core.models import Session
from core.services.vector_db import vector_db

async def run_test():
    session_id = str(uuid.uuid4())
    print(f"Starting test with session_id: {session_id}")
    
    # 1. Simulate a long sequence of messages to exceed the 2000 token threshold
    # We'll send messages that describe a legal case
    messages = [
        "I am a lawyer working on the Smith vs. Johnson case.",
        "The primary issue is a breach of contract regarding a commercial lease.",
        "The lease was signed on June 1st, 2023.",
        "The client, Mr. Smith, claims the landlord failed to provide necessary repairs.",
        "We need to draft a formal notice of breach.",
        "Also, we should look for similar precedents in New York state law.",
        "The landlord's name is Robert Johnson.",
        "Mr. Johnson owns 'Johnson Properties LLC'.",
        "The address is 123 Broadway, NY.",
        "Let's add 10 more messages about various legal details to trigger pruning..."
    ]
    
    for i, msg in enumerate(messages):
        print(f"Sending message {i+1}: {msg[:50]}...")
        await orchestrator_agent.process(
            user_id="test_user",
            message=msg,
            session_id=session_id
        )
    
    # 2. Add some "bloat" messages to definitely trigger pruning
    for i in range(15):
        await orchestrator_agent.process(
            user_id="test_user",
            message=f"This is unimportant legal filler message number {i}.",
            session_id=session_id
        )
    
    print("Simulated long conversation complete.")
    
    # 3. Verify history in DB
    session = await Session.objects.aget(id=session_id)
    print(f"Current history length in DB: {len(session.raw_history)}")
    
    # 4. Ask a question that requires recalling the very first thing we said
    # This should trigger Vector Recall if the first messages were pruned
    query = "Who is the primary client in the Smith vs. Johnson case?"
    print(f"Testing recall with query: {query}")
    
    result = await orchestrator_agent.process(
        user_id="test_user",
        message=query,
        session_id=session_id
    )
    
    print(f"\nAGENT RESPONSE:\n{result.response}\n")
    
    if "Smith" in result.response:
        print("✅ RECALL SUCCESSFUL!")
    else:
        print("❌ RECALL FAILED (or Smith not found in response)")

if __name__ == "__main__":
    asyncio.run(run_test())
