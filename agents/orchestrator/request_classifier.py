"""
Request Classifier - Intelligent categorization and routing of user requests.

This module provides a structured approach to classifying user requests and determining
the appropriate execution strategy (immediate, background task, scheduled task, etc.)
"""
import logging
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from agents.model_router import model_router

logger = logging.getLogger(__name__)


class RequestCategory(str, Enum):
    """Categories of user requests with different execution strategies."""
    
    # Immediate execution (< 5 seconds)
    SIMPLE_QUERY = "simple_query"  # Questions, info retrieval
    QUICK_TOOL = "quick_tool"  # Fast tool calls (create_task, store_data, etc.)
    
    # Background execution (> 5 seconds, < 30 minutes)
    CODING_TASK = "coding_task"  # Code changes, bug fixes, refactoring
    RESEARCH_TASK = "research_task"  # Web research, data gathering
    APP_GENERATION = "app_generation"  # Full app creation
    
    # Scheduled execution (recurring)
    SCHEDULED_TASK = "scheduled_task"  # Cron-based recurring tasks
    REMINDER = "reminder"  # One-time future reminder
    
    # Special cases
    APPROVAL_REQUIRED = "approval_required"  # Needs user confirmation
    MULTI_STEP = "multi_step"  # Complex workflow with multiple phases


class ExecutionStrategy(str, Enum):
    """How to execute the request."""
    IMMEDIATE = "immediate"  # Execute now, return result
    BACKGROUND = "background"  # Start background task, return task_id
    SCHEDULED = "scheduled"  # Schedule for future execution
    INTERACTIVE = "interactive"  # Requires user interaction/approval


class ClassifiedRequest(BaseModel):
    """Result of request classification."""
    category: RequestCategory
    execution_strategy: ExecutionStrategy
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in classification")
    
    # Extracted information
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # Execution details
    estimated_duration: Optional[str] = None  # "< 5s", "5-30s", "1-5m", "5-30m"
    requires_approval: bool = False
    
    # Scheduling (if applicable)
    schedule_expression: Optional[str] = None  # Cron expression
    due_datetime: Optional[str] = None  # ISO datetime for one-time tasks
    
    # Reasoning
    reasoning: str = Field(description="Why this classification was chosen")


class RequestClassifier:
    """
    Intelligent request classifier that determines:
    1. What category the request falls into
    2. How it should be executed (immediate, background, scheduled)
    3. What tools/agents are needed
    4. Estimated execution time
    """
    
    def __init__(self):
        self.classification_cache = {}  # Simple cache for repeated patterns
    
    async def classify(self, user_message: str, available_tools: list[str]) -> ClassifiedRequest:
        """
        Classify a user request and determine execution strategy.
        
        Args:
            user_message: The user's request
            available_tools: List of available tool names
            
        Returns:
            ClassifiedRequest with category, strategy, and extracted info
        """
        
        # Quick keyword-based pre-classification for common patterns
        quick_result = self._quick_classify(user_message, available_tools)
        if quick_result:
            logger.info(f"[CLASSIFIER] Quick classification: {quick_result.category}")
            return quick_result
        
        # Use LLM for complex classification
        logger.info("[CLASSIFIER] Using LLM for classification")
        return await self._llm_classify(user_message, available_tools)
    
    def _quick_classify(self, message: str, available_tools: list[str]) -> Optional[ClassifiedRequest]:
        """
        Fast keyword-based classification for common patterns.
        Returns None if pattern doesn't match clearly.
        """
        msg_lower = message.lower()
        
        # FILE STORED MESSAGES - Extract caption and store
        if "[file stored]" in msg_lower and "caption:" in msg_lower:
            # Extract file info from structured message
            import re
            
            file_type_match = re.search(r'type:\s*(\w+)', message, re.IGNORECASE)
            name_match = re.search(r'name:\s*([^\n]+)', message, re.IGNORECASE)
            path_match = re.search(r'path:\s*([^\n]+)', message, re.IGNORECASE)
            caption_match = re.search(r'caption:\s*([^\n]+)', message, re.IGNORECASE)
            
            if name_match and caption_match:
                file_type = file_type_match.group(1) if file_type_match else "file"
                name = name_match.group(1).strip()
                path = path_match.group(1).strip() if path_match else ""
                caption = caption_match.group(1).strip()
                
                # Build parameters for store_data_entry
                parameters = {
                    "entry_type": f"{file_type}_caption",
                    "name": name,
                    "details": {
                        "caption": caption,
                        "path": path,
                        "type": file_type
                    }
                }
                
                return ClassifiedRequest(
                    category=RequestCategory.QUICK_TOOL,
                    execution_strategy=ExecutionStrategy.IMMEDIATE,
                    confidence=0.95,
                    tool_name="store_data_entry",
                    parameters=parameters,
                    estimated_duration="< 5s",
                    reasoning="Detected file storage message with caption - storing metadata"
                )
        
        # REMINDERS - One-time future tasks
        reminder_keywords = ["remind me", "reminder", "notify me", "alert me"]
        time_keywords = ["in", "at", "tomorrow", "next", "minutes", "hours", "days"]
        if any(kw in msg_lower for kw in reminder_keywords) and any(kw in msg_lower for kw in time_keywords):
            return ClassifiedRequest(
                category=RequestCategory.REMINDER,
                execution_strategy=ExecutionStrategy.IMMEDIATE,  # Create reminder immediately
                confidence=0.95,
                tool_name="create_task",
                estimated_duration="< 5s",
                reasoning="Detected reminder request with time specification"
            )
        
        # SCHEDULED TASKS - Recurring tasks
        schedule_keywords = ["every day", "every week", "daily", "weekly", "monthly", "schedule", "recurring"]
        if any(kw in msg_lower for kw in schedule_keywords):
            return ClassifiedRequest(
                category=RequestCategory.SCHEDULED_TASK,
                execution_strategy=ExecutionStrategy.IMMEDIATE,  # Create schedule immediately
                confidence=0.9,
                tool_name="schedule_task",
                estimated_duration="< 5s",
                reasoning="Detected recurring/scheduled task request"
            )
        
        # CODING TASKS - Code modifications
        coding_keywords = [
            "fix", "debug", "refactor", "improve code", "add feature", "modify code",
            "update code", "change code", "bug", "error in", "implement", "create function",
            "add method", "update class", "fix the code", "code issue"
        ]
        code_indicators = [".py", "function", "class", "method", "file", "module", "code", "script"]
        
        has_coding_keyword = any(kw in msg_lower for kw in coding_keywords)
        has_code_indicator = any(ind in msg_lower for ind in code_indicators)
        
        if has_coding_keyword and has_code_indicator:
            return ClassifiedRequest(
                category=RequestCategory.CODING_TASK,
                execution_strategy=ExecutionStrategy.BACKGROUND,
                confidence=0.9,
                tool_name="run_opencode_command",
                estimated_duration="5-30m",
                reasoning="Detected code modification request - requires OpenCode CLI"
            )
        
        # RESEARCH TASKS - Web research
        research_keywords = ["research", "find information", "search for", "look up", "investigate"]
        if any(kw in msg_lower for kw in research_keywords):
            return ClassifiedRequest(
                category=RequestCategory.RESEARCH_TASK,
                execution_strategy=ExecutionStrategy.BACKGROUND,
                confidence=0.85,
                tool_name="search_web",
                estimated_duration="30s-2m",
                reasoning="Detected research/search request"
            )
        
        # APP GENERATION - Full app creation
        app_keywords = ["i'm a", "i am a", "build me an app", "create an app", "i need an app"]
        if any(kw in msg_lower for kw in app_keywords):
            return ClassifiedRequest(
                category=RequestCategory.APP_GENERATION,
                execution_strategy=ExecutionStrategy.BACKGROUND,
                confidence=0.95,
                tool_name="create_app",
                estimated_duration="10-30m",
                reasoning="Detected app generation request"
            )
        
        # SIMPLE QUERIES - Questions
        question_keywords = ["what", "how", "why", "when", "where", "who", "explain", "tell me"]
        if any(msg_lower.startswith(kw) for kw in question_keywords):
            return ClassifiedRequest(
                category=RequestCategory.SIMPLE_QUERY,
                execution_strategy=ExecutionStrategy.IMMEDIATE,
                confidence=0.8,
                estimated_duration="< 5s",
                reasoning="Detected informational question"
            )
        
        # QUICK TOOLS - Fast data operations
        quick_tool_patterns = {
            "store": "store_data_entry",
            "save": "store_data_entry",
            "log transaction": "log_transaction",
            "expense": "log_transaction",
            "link": "link_knowledge_nodes",
            "connect": "link_knowledge_nodes",
        }
        
        for pattern, tool in quick_tool_patterns.items():
            if pattern in msg_lower and tool in available_tools:
                return ClassifiedRequest(
                    category=RequestCategory.QUICK_TOOL,
                    execution_strategy=ExecutionStrategy.IMMEDIATE,
                    confidence=0.85,
                    tool_name=tool,
                    estimated_duration="< 5s",
                    reasoning=f"Detected quick tool usage: {tool}"
                )
        
        return None  # No clear pattern, use LLM
    
    async def _llm_classify(self, message: str, available_tools: list[str]) -> ClassifiedRequest:
        """
        Use LLM with structured output for complex classification.
        """
        
        tools_str = ", ".join(available_tools[:30])  # Limit to avoid token overflow
        
        system_prompt = f"""You are a request classifier for an AI agent system.

Your job is to analyze user requests and classify them into categories with execution strategies.

CATEGORIES & STRATEGIES:

1. SIMPLE_QUERY (immediate):
   - Questions, explanations, general info
   - Duration: < 5 seconds
   - Examples: "What is X?", "How does Y work?", "Explain Z"

2. QUICK_TOOL (immediate):
   - Fast tool calls that complete quickly
   - Duration: < 5 seconds
   - Tools: create_task, store_data_entry, log_transaction, link_knowledge_nodes
   - Examples: "Store this info", "Log expense", "Create a task"

3. REMINDER (immediate creation, future execution):
   - One-time future notifications
   - Duration: < 5 seconds to create
   - Examples: "Remind me in 15 minutes", "Alert me tomorrow at 3pm"

4. SCHEDULED_TASK (immediate creation, recurring execution):
   - Recurring tasks with cron expressions
   - Duration: < 5 seconds to create
   - Examples: "Every day at 9am", "Weekly on Monday", "Daily standup"

5. CODING_TASK (background):
   - Code modifications, bug fixes, refactoring
   - Duration: 5-30 minutes
   - Tool: run_opencode_command
   - Examples: "Fix the bug in X", "Add feature Y", "Refactor Z"

6. RESEARCH_TASK (background):
   - Web research, data gathering
   - Duration: 30 seconds - 5 minutes
   - Tool: search_web
   - Examples: "Research X", "Find information about Y"

7. APP_GENERATION (background):
   - Full application creation
   - Duration: 10-30 minutes
   - Examples: "I'm a lawyer", "Build me a CRM"

8. MULTI_STEP (background):
   - Complex workflows requiring multiple phases
   - Duration: varies
   - Examples: "Research X then build Y", "Analyze A and create B"

Available tools: {tools_str}

Analyze the request and provide:
- category: The request category
- execution_strategy: How to execute (immediate/background/scheduled)
- confidence: 0.0-1.0
- tool_name: Primary tool to use (if applicable)
- estimated_duration: Time estimate
- reasoning: Why this classification

CRITICAL RULES:
- Coding tasks ALWAYS use background execution with run_opencode_command
- Research tasks ALWAYS use background execution
- Simple datetime calculations for reminders are IMMEDIATE (just create the task)
- Don't confuse "create a reminder" (immediate) with "run code to calculate time" (wrong!)
"""

        try:
            result = await model_router.complete(
                task_type="tool",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Classify this request: {message}"}
                ],
                response_model=ClassifiedRequest
            )
            
            logger.info(f"[CLASSIFIER] LLM classified as: {result.category} ({result.confidence:.2f} confidence)")
            return result
            
        except Exception as e:
            logger.error(f"[CLASSIFIER] LLM classification failed: {e}")
            # Fallback to safe default
            return ClassifiedRequest(
                category=RequestCategory.SIMPLE_QUERY,
                execution_strategy=ExecutionStrategy.IMMEDIATE,
                confidence=0.5,
                estimated_duration="< 5s",
                reasoning=f"Fallback classification due to error: {e}"
            )


# Singleton instance
request_classifier = RequestClassifier()
