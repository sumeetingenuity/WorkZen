"""
Context Manager - Handles conversation pruning, summarization, and vector recall.

Ensures the agent stays within token limits while maintaining long-term memory.
"""
import logging
import json
from typing import List, Dict, Any, Optional
from django.conf import settings
from core.services.vector_db import vector_db
import tiktoken

logger = logging.getLogger(__name__)

class ContextManager:
    """
    Service for managing LLM context.
    
    Strategies:
    1. Sliding window: prune old messages.
    2. Summarization: replace pruned messages with a summary.
    3. Vector search: retrieve relevant context from history.
    """
    
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except Exception:
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in a string."""
        return len(self.encoding.encode(text))
    
    def get_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Estimate tokens in a list of messages."""
        num_tokens = 0
        for message in messages:
            num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
            for key, value in message.items():
                num_tokens += self.count_tokens(value)
                if key == "name":  # if there's a name, the role is omitted
                    num_tokens += -1  # role is always 1 token
        num_tokens += 2  # every reply is primed with <im_start>assistant
        return num_tokens

    async def prepare_context(
        self, 
        session_id: str, 
        current_messages: List[Dict[str, str]], 
        max_tokens: int = 10000
    ) -> List[Dict[str, str]]:
        """
        Prepare the context for the LLM.
        
        If tokens exceed max_tokens:
        1. Summarize old messages.
        2. Store raw messages in VectorDB.
        3. Prepend summary to the window.
        """
        tokens = self.get_messages_tokens(current_messages)
        
        if tokens <= max_tokens:
            return current_messages
            
        logger.info(f"Context tokens ({tokens}) exceed threshold ({max_tokens}). Pruning...")
        
        # Keep the system message and the last N messages
        system_msg = None
        other_msgs = []
        
        for msg in current_messages:
            if msg.get("role") == "system":
                system_msg = msg
            else:
                other_msgs.append(msg)
        
        # Split into "to prune" and "to keep"
        # For simplicity, keep the last 10 messages
        keep_count = min(10, len(other_msgs))
        to_prune = other_msgs[:-keep_count]
        to_keep = other_msgs[-keep_count:]
        
        if not to_prune:
            return current_messages
            
        # Store pruned messages in VectorDB before they're "lost"
        pruned_text = "\n".join([f"{m['role']}: {m['content']}" for m in to_prune])
        await vector_db.add_to_memory(
            collection_name="conversation",
            text=pruned_text,
            metadata={"session_id": session_id, "type": "history_pruned"},
            id=f"prune_{session_id}_{len(to_prune)}"
        )
        
        # For now, we'll just return the system msg + last 10 messages
        # In the next step, we'll add a Summarizer Agent to create the "summary head"
        result = []
        if system_msg:
            result.append(system_msg)
        
        result.extend(to_keep)
        return result

    async def get_relevant_history(self, session_id: str, query: str) -> str:
        """Retrieve relevant past context using semantic search."""
        results = await vector_db.search(
            collection_name="conversation",
            query=query,
            where={"session_id": session_id},
            n_results=3
        )
        
        if not results:
            return ""
            
        context = "\n--- RELEVANT PAST CONTEXT ---\n"
        for res in results:
            context += f"{res['content']}\n"
        context += "----------------------------\n"
        
        return context

# Singleton instance
context_service = ContextManager()
