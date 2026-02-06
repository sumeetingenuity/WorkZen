"""
Context Manager Agent - Summarizes conversation history to preserve memory.
"""
import logging
from typing import List, Dict, Any
from agents.model_router import model_router

logger = logging.getLogger(__name__)

class ContextManagerAgent:
    """
    Agent responsible for condensing conversation history.
    """
    
    async def summarize_history(self, messages: List[Dict[str, str]]) -> str:
        """
        Condense a list of messages into a single concise summary.
        """
        if not messages:
            return ""
            
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        prompt = f"""
Summarize the following conversation history concisely. 
Preserve key information, decisions made, and pending tasks.
Focus on what the user wants and what the agent has accomplished.

CONVERSATION:
{history_text}

SUMMARY:
"""
        
        try:
            response = await model_router.complete(
                task_type="orchestrate",  # Using orchestrate model for summary
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return "History summarized (Error during LLM call)."

# Singleton instance
context_manager_agent = ContextManagerAgent()
