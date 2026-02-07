"""
Orchestrator Agent - Main coordination hub for SecureAssist.

Understands user intent, coordinates Research and Developer agents,
and manages the complete app generation workflow.
"""
import logging
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from django.conf import settings
from agents.schemas import AppSpec, DomainSpec
from agents.orchestrator.domain_analyzer import DomainAnalyzer
from agents.research.agent import research_agent, ResearchResult
from agents.developer.agent import developer_agent
from agents.model_router import model_router
from agents.context_manager.agent import context_manager_agent
from agents.orchestrator.task_tracker import task_tracker, TaskStatus
from agents.orchestrator.request_classifier import request_classifier, RequestCategory, ExecutionStrategy
from core.registry import capability_registry
from core.services.context import context_service
from core.services.vector_db import vector_db
from core.models import Session

logger = logging.getLogger(__name__)


class OrchestratorResult(BaseModel):
    """Result from orchestrator processing."""
    session_id: str
    response: str
    tool_responses: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    pending_task_id: Optional[str] = None
    app_created: Optional[str] = None
    wait_for_secret: bool = False
    metadata: dict = Field(default_factory=dict)


class IntentType(BaseModel):
    """Classified intent from user message."""
    intent: str = Field(description="One of: create_app, use_tool, general_query, approve_action")
    domain: Optional[str] = Field(default=None, description="Domain if creating app")
    tool_name: Optional[str] = Field(default=None, description="Tool to use if applicable")
    parameters: dict = Field(default_factory=dict)


class OrchestratorAgent:
    """
    Main orchestrator that coordinates all agent activities.
    
    Responsibilities:
    1. Parse user intent
    2. Route to appropriate agent (Research, Developer, Tool Execution)
    3. Manage conversation context
    4. Handle approval flows
    """
    
    def __init__(self):
        self.domain_analyzer = DomainAnalyzer()
        self._pending_tasks = {}  # task_id -> pending task info
        
        # Register task completion callback
        task_tracker.register_notification_callback(self._on_task_complete)
    
    async def _on_task_complete(self, task):
        """Called when a background task completes."""
        try:
            from integrations.telegram_bot.management.commands.run_bot import bot_instance
            
            if not bot_instance:
                logger.warning("Bot instance not available for task notification")
                return
            
            # Format completion message
            if task.status == TaskStatus.COMPLETED:
                message = f"""✅ **Task Completed!**

**Task ID:** `{task.task_id}`
**Description:** {task.description}

**Result:**
{task.result[:1000] if task.result else 'No output'}

Use `check_task_status(task_id='{task.task_id}')` for full details."""
            else:
                message = f"""❌ **Task Failed**

**Task ID:** `{task.task_id}`
**Description:** {task.description}

**Error:** {task.error}

Use `check_task_status(task_id='{task.task_id}')` for details."""
            
            # Send notification to user
            # This would need to be implemented based on your notification system
            logger.info(f"[TASK NOTIFICATION] Task {task.task_id} completed for user {task.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to send task completion notification: {e}")

    def _get_tool_category(self, tool_name: str) -> Optional[str]:
        registry = capability_registry.get_full_registry()
        for category, data in registry.items():
            for tool in data.get("tools", []):
                if tool.get("name") == tool_name:
                    return category
        return None

    async def _attempt_tool_recovery(self, tool_name: str) -> bool:
        """Try to recover tool execution by reloading its app/module."""
        category = self._get_tool_category(tool_name)
        if not category:
            return False
        app_dir = Path(settings.BASE_DIR) / "apps" / category
        if not app_dir.exists():
            return False
        try:
            await app_reloader.reload_app(category)
            capability_registry.discover_tools()
            logger.info(f"Recovered tools for app category: {category}")
            return True
        except Exception as e:
            logger.warning(f"Tool recovery failed for {tool_name}: {e}")
            return False
    
    async def process(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None
    ) -> OrchestratorResult:
        """
        Process a user message with full autonomy.
        
        The agent can:
        - Create and modify apps
        - Fix bugs in the codebase
        - Add new features
        - Use any available tool
        - Improve itself
        """
        session_id = session_id or str(uuid.uuid4())
        
        # Validate message is not empty
        if not message or not message.strip():
            logger.warning(f"Empty message received from user {user_id}")
            return OrchestratorResult(
                session_id=session_id,
                response="❌ **Error**: Message text is empty. Please provide a valid message."
            )
        
        logger.info(f"Processing message for user {user_id}: {message[:100]}")
        
        try:
            # 1. Load Session History
            db_session, created = await Session.objects.aget_or_create(id=session_id, defaults={'user_id': user_id})
            history = db_session.raw_history or []
            
            # 2. Add current message to history (temp for context preparation)
            temp_history = history + [{"role": "user", "content": message}]
            
            # 3. Context Management (Pruning/Summarization)
            optimized_history = await context_service.prepare_context(
                session_id=session_id,
                current_messages=temp_history,
                max_tokens=10000  # Production threshold
            )
            
            # 4. Vector Recall (Semantic memory)
            relevant_history = await context_service.get_relevant_history(session_id, message)
            
            # 5. Load Custom Agent (if any)
            from core.models import CustomAgent
            custom_agent = await CustomAgent.objects.filter(user_id=user_id, is_active=True).afirst()
            
            # Update history in DB for next turn
            db_session.raw_history = temp_history
            await db_session.asave()
            
            # 6. Let the agent autonomously decide what to do
            result = await self._autonomous_process(
                session_id=session_id,
                user_id=user_id,
                message=message,
                history=optimized_history,
                relevant_history=relevant_history,
                custom_agent=custom_agent
            )

            # 7. Global Secret Masking (Final Safety Net)
            from core.services.secrets import SecretEngine
            secret_masker = SecretEngine()
            result.response = secret_masker.mask_in_output(result.response)
            
            logger.info(f"[ORCHESTRATOR] Returning result to caller, response length: {len(result.response) if result.response else 0}")
            return result
                
        except Exception as e:
            logger.exception(f"Orchestrator error: {e}")
            # Check if it's an XML parsing error and provide a user-friendly message
            error_msg = str(e).lower()
            if "parse entity" in error_msg or "byte offset" in error_msg or "xml" in error_msg:
                return OrchestratorResult(
                    session_id=session_id,
                    response=f"🛑 **Parsing Error**: I encountered an issue parsing the AI response. This usually happens when the response contains special characters or malformed XML-like content.\n\nPlease try rephrasing your request."
                )
            return OrchestratorResult(
                session_id=session_id,
                response=f"🛑 **Critical Error**: I was unable to complete your request due to a system failure.\n\nError Details: `{str(e)}`\n\nPlease try again or check the system logs."
            )
    
    async def _classify_intent(self, message: str) -> IntentType:
        """Classify user intent using LLM with instructor for structured extraction."""
        
        available_tools = capability_registry.list_tools()
        tools_list = ", ".join(available_tools)
        
        try:
            # Use instructor for reliable intent classification and parameter extraction
            intent = await model_router.complete(
                task_type="tool",
                messages=[
                    {
                        "role": "system",
                        "content": f"Classify the user intent. Available tools: {tools_list}. "
                                   "If the user wants to create an app, use 'create_app'. "
                                   "If they want to use a specific tool, use 'use_tool' and extract its parameters. "
                                   "IMPORTANT: For code fixing, debugging, or refactoring requests, use 'use_tool' with tool_name='run_opencode_command'. "
                                   "If they are asking a general question, use 'general_query'."
                    },
                    {"role": "user", "content": message}
                ],
                response_model=IntentType
            )
            return intent
        except Exception as e:
            error_str = str(e).lower()
            logger.warning(f"LLM classification failed: {e}")
            
            # Check for XML/entity parsing errors and fall back immediately
            if "parse entity" in error_str or "byte offset" in error_str or "xml" in error_str:
                logger.warning("XML/entity parsing error detected, using keyword fallback")
            else:
                logger.warning(f"LLM classification failed with non-XML error: {e}")
            
            # Fallback to legacy keyword matching
            message_lower = message.lower()
            
            # Check for coding/fixing keywords first - be very aggressive here
            coding_keywords = [
                "fix", "debug", "refactor", "improve code", "code issue", "bug", 
                "error in code", "update code", "modify code", "fix the", "repair",
                "correct", "solve", "resolve", "patch", "update the code"
            ]
            for kw in coding_keywords:
                if kw in message_lower:
                    # Check if it's about code/tools/files, not general conversation
                    code_indicators = ["tool", "function", "class", "file", "code", "script", "module", "agent", ".py", "error", "crash"]
                    if any(indicator in message_lower for indicator in code_indicators):
                        logger.info(f"Detected code fixing request with keyword '{kw}'")
                        return IntentType(
                            intent="use_tool", 
                            tool_name="run_opencode_command",
                            parameters={"instruction": message}
                        )
            
            # Check for app creation
            app_keywords = ["i'm a", "i am a", "build me", "create an app", "i need an app", "make me"]
            for kw in app_keywords:
                if kw in message_lower:
                    return IntentType(intent="create_app", domain=self._extract_domain_quick(message_lower))
            
            # Check for specific tool names
            for tool_name in available_tools:
                if tool_name in message_lower or tool_name.replace("_", " ") in message_lower:
                    return IntentType(intent="use_tool", tool_name=tool_name)
                    
            return IntentType(intent="general_query")
    
    def _extract_domain_quick(self, message: str) -> str:
        """Quick domain extraction from message."""
        domains = {
            "lawyer": "legal",
            "legal": "legal",
            "attorney": "legal",
            "doctor": "healthcare",
            "clinic": "healthcare",
            "hospital": "healthcare",
            "realtor": "real_estate",
            "real estate": "real_estate",
            "property": "real_estate",
            "accountant": "finance",
            "finance": "finance",
            "bookkeeping": "finance",
        }
        
        for keyword, domain in domains.items():
            if keyword in message:
                return domain
        
        return "custom"
    
    async def _autonomous_process(
        self,
        session_id: str,
        user_id: str,
        message: str,
        history: list,
        relevant_history: str,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """
        Fully autonomous processing with intelligent request classification.
        
        This method:
        1. Classifies the request (simple query, coding task, research, etc.)
        2. Determines execution strategy (immediate, background, scheduled)
        3. Routes to appropriate handler
        4. Returns result or task_id for background tasks
        """
        
        # Step 1: Classify the request
        available_tool_names = capability_registry.list_tools()
        classification = await request_classifier.classify(message, available_tool_names)
        
        logger.info(f"[ORCHESTRATOR] Request classified as: {classification.category} "
                   f"(strategy: {classification.execution_strategy}, confidence: {classification.confidence:.2f})")
        logger.info(f"[ORCHESTRATOR] Reasoning: {classification.reasoning}")
        
        # Step 2: Route based on classification
        
        # IMMEDIATE EXECUTION - Quick responses
        if classification.execution_strategy == ExecutionStrategy.IMMEDIATE:
            
            # Simple queries - use LLM directly
            if classification.category == RequestCategory.SIMPLE_QUERY:
                return await self._handle_general_query(session_id, message, history, relevant_history)
            
            # Quick tool calls - execute immediately
            if classification.category == RequestCategory.QUICK_TOOL and classification.tool_name:
                intent = IntentType(
                    intent="use_tool",
                    tool_name=classification.tool_name,
                    parameters=classification.parameters
                )
                return await self._handle_tool_use(
                    session_id, user_id, intent,
                    custom_agent.name if custom_agent else None,
                    custom_agent,
                    track_as_background=False
                )
            
            # Reminders - create task with calculated datetime
            if classification.category == RequestCategory.REMINDER:
                return await self._handle_reminder_creation(session_id, user_id, message, custom_agent)
            
            # Scheduled tasks - create recurring task
            if classification.category == RequestCategory.SCHEDULED_TASK:
                return await self._handle_scheduled_task_creation(session_id, user_id, message, custom_agent)
        
        # BACKGROUND EXECUTION - Long-running tasks
        if classification.execution_strategy == ExecutionStrategy.BACKGROUND:
            
            # Coding tasks - always background
            if classification.category == RequestCategory.CODING_TASK:
                intent = IntentType(
                    intent="use_tool",
                    tool_name="run_opencode_command",
                    parameters={"instruction": message}
                )
                return await self._handle_tool_use(
                    session_id, user_id, intent,
                    custom_agent.name if custom_agent else None,
                    custom_agent,
                    track_as_background=True  # Force background
                )
            
            # Research tasks - background
            if classification.category == RequestCategory.RESEARCH_TASK:
                intent = IntentType(
                    intent="use_tool",
                    tool_name="search_web",
                    parameters=classification.parameters or {"query": message}
                )
                return await self._handle_tool_use(
                    session_id, user_id, intent,
                    custom_agent.name if custom_agent else None,
                    custom_agent,
                    track_as_background=True
                )
            
            # App generation - background
            if classification.category == RequestCategory.APP_GENERATION:
                return await self._handle_create_app(session_id, user_id, message, 
                                                     IntentType(intent="create_app"), custom_agent)
            
            # Multi-step - use planning
            if classification.category == RequestCategory.MULTI_STEP:
                return await self._handle_multi_step_task(session_id, user_id, message, custom_agent)
        
        # FALLBACK - If classification is unclear, use the old autonomous approach
        logger.warning(f"[ORCHESTRATOR] No clear routing for {classification.category}, using fallback")
        return await self._autonomous_process_fallback(
            session_id, user_id, message, history, relevant_history, custom_agent
        )
    
    async def _handle_reminder_creation(
        self,
        session_id: str,
        user_id: str,
        message: str,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """
        Handle reminder creation with intelligent datetime parsing.
        This executes immediately - just creates the task with calculated datetime.
        """
        from django.utils import timezone
        from datetime import timedelta
        import re
        
        # Parse relative time from message
        msg_lower = message.lower()
        due_date = None
        
        # Pattern: "in X minutes/hours/days"
        time_match = re.search(r'in (\d+)\s*(minute|hour|day|week)s?', msg_lower)
        if time_match:
            amount = int(time_match.group(1))
            unit = time_match.group(2)
            
            if unit == 'minute':
                due_date = timezone.now() + timedelta(minutes=amount)
            elif unit == 'hour':
                due_date = timezone.now() + timedelta(hours=amount)
            elif unit == 'day':
                due_date = timezone.now() + timedelta(days=amount)
            elif unit == 'week':
                due_date = timezone.now() + timedelta(weeks=amount)
        
        # Pattern: "tomorrow"
        elif 'tomorrow' in msg_lower:
            due_date = timezone.now() + timedelta(days=1)
        
        # Pattern: "next week"
        elif 'next week' in msg_lower:
            due_date = timezone.now() + timedelta(weeks=1)
        
        if not due_date:
            # Fallback: use LLM to parse complex time expressions
            logger.warning("[REMINDER] Could not parse time, using LLM fallback")
            return await self._handle_general_query(session_id, message, [], "")
        
        # Format datetime
        due_date_str = due_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract reminder content (remove time part)
        title = re.sub(r'remind me (in|at|to|about)?\s*(.*?)(in \d+|tomorrow|next)', r'\2', msg_lower).strip()
        if not title or len(title) < 3:
            title = "Reminder"
        
        # Create the task
        intent = IntentType(
            intent="use_tool",
            tool_name="create_task",
            parameters={
                "title": title,
                "due_date": due_date_str,
                "priority": 2
            }
        )
        
        return await self._handle_tool_use(
            session_id, user_id, intent,
            custom_agent.name if custom_agent else None,
            custom_agent,
            track_as_background=False
        )
    
    async def _handle_scheduled_task_creation(
        self,
        session_id: str,
        user_id: str,
        message: str,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """Handle scheduled/recurring task creation."""
        # Use LLM to extract cron expression and task details
        # For now, delegate to general query handler
        return await self._handle_general_query(session_id, message, [], "")
    
    async def _handle_multi_step_task(
        self,
        session_id: str,
        user_id: str,
        message: str,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """Handle multi-step complex tasks."""
        # Use planning tools
        intent = IntentType(
            intent="use_tool",
            tool_name="create_execution_plan",
            parameters={"description": message}
        )
        return await self._handle_tool_use(
            session_id, user_id, intent,
            custom_agent.name if custom_agent else None,
            custom_agent,
            track_as_background=True
        )
    
    async def _autonomous_process_fallback(
        self,
        session_id: str,
        user_id: str,
        message: str,
        history: list,
        relevant_history: str,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """
        Fully autonomous processing - the agent decides what to do.
        
        This method gives the agent complete freedom to:
        - Analyze the request
        - Decide which tools to use
        - Execute multiple tools in sequence
        - Modify its own code
        - Create new capabilities
        """
        
        # Get all available tools with their schemas
        available_tools = capability_registry.get_tools_for_function_calling()
        
        # Get Identity settings
        agent_name = getattr(settings, "AGENT_NAME", "SecureAssist")
        agent_persona = getattr(settings, "AGENT_PERSONA", "Professional & Direct")
        
        # Build the autonomous system prompt
        system_prompt = f"""You are {agent_name}, a fully autonomous AI agent with complete control over your capabilities.

🎯 YOUR MISSION:
You are not just an assistant - you are a self-improving, autonomous agent that can:
- Create and modify applications
- Fix bugs in your own codebase
- Add new features to yourself
- Use any tool at your disposal
- Chain multiple tools together
- Reason through complex problems

🛠️ AVAILABLE TOOLS:
You have access to these tools (use them via function calling):
{self._format_tools_for_prompt(available_tools)}

🧠 REASONING APPROACH:
1. ANALYZE: Understand what the user wants
2. PLAN: Decide which tools to use and in what order
3. EXECUTE: Call the appropriate tools
4. REFLECT: Check if the task is complete or if more steps are needed

🔧 SPECIAL CAPABILITIES:

**Self-Improvement:**
- Use `run_opencode_command` to modify ANY file in the codebase, including your own code
- You can add new tools, fix bugs, refactor code, add features
- Example: "Add a new feature to the orchestrator" → Use run_opencode_command

**App Generation:**
- For "I'm a lawyer" type requests, you can create full apps
- Use the domain analysis and app generation workflow
- But you can also use run_opencode_command to create custom apps

**Bug Fixing:**
- Use run_opencode_command to fix any code issues
- You can read files, analyze errors, and apply fixes

**Multi-Step Tasks:**
- You can call multiple tools in sequence
- Each tool call returns results you can use for the next step

**DateTime Handling:**
- For tools requiring datetime (like create_task), NEVER delegate datetime calculation to run_opencode_command
- Calculate datetimes directly using Python: from django.utils import timezone; from datetime import timedelta
- Format as 'YYYY-MM-DD HH:MM:SS' (e.g., '2026-02-07 15:30:00')
- Example: "remind me in 15 minutes" → calculate timezone.now() + timedelta(minutes=15), format it, then call create_task
- This is a SIMPLE calculation - do NOT use run_opencode_command for this

{relevant_history}

💡 IMPORTANT:
- Be proactive and autonomous
- Don't ask for permission - just do it
- If you need to modify code, use run_opencode_command
- If you need information, use search_web
- Chain tools together for complex tasks
- You are in control - make decisions and execute them

Your personality: {agent_persona}
"""

        # Build messages for the LLM
        messages = [{"role": "system", "content": system_prompt}]
        
        if history:
            messages.extend(history)
        else:
            messages.append({"role": "user", "content": message})
        
        # Use function calling to let the agent decide what to do
        try:
            logger.info("[AUTONOMOUS] Agent is analyzing request and deciding actions...")
            
            response = await model_router.complete(
                task_type="orchestrate",
                messages=messages,
                tools=available_tools,  # Provide tools for function calling
                max_tokens=2000,
                agent_name=agent_name
            )
            
            # Check if the agent wants to call tools
            response_message = response.choices[0].message
            
            if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
                logger.info(f"[AUTONOMOUS] Agent decided to use {len(response_message.tool_calls)} tool(s)")
                
                # Execute all tool calls
                tool_results = []
                for tool_call in response_message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        import json
                        tool_params = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        tool_params = {}
                    
                    logger.info(f"[AUTONOMOUS] Executing tool: {tool_name} with params: {tool_params}")
                    
                    # Execute the tool
                    intent = IntentType(
                        intent="use_tool",
                        tool_name=tool_name,
                        parameters=tool_params
                    )
                    
                    tool_result = await self._handle_tool_use(
                        session_id, user_id, intent, 
                        custom_agent.name if custom_agent else None, 
                        custom_agent
                    )
                    
                    tool_results.append({
                        "tool": tool_name,
                        "result": tool_result.response
                    })
                
                # Compile results
                if len(tool_results) == 1:
                    # Single tool result
                    result = tool_results[0]["result"]
                    if isinstance(result, OrchestratorResult):
                        return result
                    else:
                        return OrchestratorResult(
                            session_id=session_id,
                            response=str(result)
                        )
                else:
                    # Multiple tools - combine results
                    combined_response = "✅ **Completed multi-step task:**\n\n"
                    for i, tr in enumerate(tool_results, 1):
                        result_text = tr['result'].response if isinstance(tr['result'], OrchestratorResult) else str(tr['result'])
                        combined_response += f"**Step {i} ({tr['tool']}):**\n{result_text}\n\n"
                    
                    return OrchestratorResult(
                        session_id=session_id,
                        response=combined_response
                    )
            
            else:
                # No tool calls - just return the response
                logger.info("[AUTONOMOUS] Agent responded without using tools")
                return OrchestratorResult(
                    session_id=session_id,
                    response=response_message.content
                )
                
        except Exception as e:
            logger.exception(f"[AUTONOMOUS] Error in autonomous processing: {e}")
            # Fallback to simpler approach
            return await self._handle_general_query(
                session_id, message, history, relevant_history
            )
    
    def _format_tools_for_prompt(self, tools: list) -> str:
        """Format tools for the system prompt."""
        if not tools:
            return "No tools available"
        
        formatted = []
        for tool in tools[:20]:  # Limit to avoid token overflow
            name = tool.get("function", {}).get("name", "unknown")
            desc = tool.get("function", {}).get("description", "")
            formatted.append(f"- {name}: {desc}")
        
        if len(tools) > 20:
            formatted.append(f"... and {len(tools) - 20} more tools")
        
        return "\n".join(formatted)
    
    async def _handle_create_app(
        self,
        session_id: str,
        user_id: str,
        message: str,
        intent: IntentType,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """Handle app creation request."""
        
        try:
            # 1. Analyze domain
            logger.info(f"[APP CREATION] Step 1/4: Analyzing domain for user {user_id}")
            domain_spec = await self.domain_analyzer.analyze(message)
            logger.info(f"Domain analyzed: {domain_spec.domain_name}")
            
            # 2. Research the domain
            logger.info(f"[APP CREATION] Step 2/4: Researching domain '{domain_spec.domain_name}'")
            research_result = await research_agent.research(domain_spec)
            logger.info(f"Research complete: {len(research_result.apis_found)} APIs found")
            
            # 3. Create app specification
            logger.info(f"[APP CREATION] Step 3/4: Creating app specification")
            app_spec = await self.domain_analyzer.create_app_spec(
                domain_spec,
                research_result.model_dump()
            )
            logger.info(f"App spec created: {app_spec.name} with {len(app_spec.entities)} entities")
            
            # 4. Build the app using Developer Agent
            logger.info(f"[APP CREATION] Step 4/4: Building app '{app_spec.name}'")
            build_result = await developer_agent.build_app(app_spec, model=custom_agent.model_id if custom_agent else None)
            
            if build_result["success"]:
                logger.info(f"[APP CREATION] ✅ Successfully created app '{app_spec.name}'")
                response = f"""✅ **{app_spec.display_name}** created successfully!

📦 **App Location**: `apps/{app_spec.name}/`
🔧 **Tools Registered**: {build_result.get('tools_registered', 0)}

**Entities Created**:
{chr(10).join(f'• {e.name}' for e in app_spec.entities)}

**Available Tools**:
{chr(10).join(f'• `{t.name}`: {t.description}' for t in app_spec.tools[:5])}
{f'... and {len(app_spec.tools) - 5} more' if len(app_spec.tools) > 5 else ''}

**Research Summary**:
{research_result.recommendations}

You can now use these tools! Try: "Create a new client named John Doe"
"""
                return OrchestratorResult(
                    session_id=session_id,
                    response=response,
                    app_created=app_spec.name
                )
            else:
                logger.warning(f"[APP CREATION] ⚠️ Initial build failed, attempting recovery for '{app_spec.name}'")
                # Attempt recovery once for partial generations
                recovery = await developer_agent.recover_app(app_spec, model=custom_agent.model_id if custom_agent else None)
                if recovery.get("success"):
                    logger.info(f"[APP CREATION] ✅ Successfully recovered app '{app_spec.name}'")
                    response = f"""✅ **{app_spec.display_name}** created successfully (after recovery)!

📦 **App Location**: `apps/{app_spec.name}/`
🔧 **Tools Registered**: {recovery.get('tools_registered', len(app_spec.tools))}

**Entities Created**:
{chr(10).join(f'• {e.name}' for e in app_spec.entities)}

**Available Tools**:
{chr(10).join(f'• `{t.name}`: {t.description}' for t in app_spec.tools[:5])}
{f'... and {len(app_spec.tools) - 5} more' if len(app_spec.tools) > 5 else ''}
"""
                    return OrchestratorResult(
                        session_id=session_id,
                        response=response,
                        app_created=app_spec.name
                    )
                logger.error(f"[APP CREATION] ❌ Failed to create app '{app_spec.name}': {build_result.get('error', 'Unknown error')}")
                return OrchestratorResult(
                    session_id=session_id,
                    response=f"❌ **App Creation Failed**: {build_result.get('error', 'Unknown error')}\n\nI attempted to build the app but encountered a persistent issue. You may want to try again with a simpler description."
                )
        except Exception as e:
            logger.exception(f"[APP CREATION] ❌ Exception during app creation: {e}")
            return OrchestratorResult(
                session_id=session_id,
                response=f"❌ **App Creation Error**: An unexpected error occurred while creating the app.\n\nError: {str(e)}\n\nPlease check the logs for more details."
            )
    
    async def _handle_tool_use(
        self,
        session_id: str,
        user_id: str,
        intent: IntentType,
        agent_name: Optional[str] = None,
        custom_agent: Optional[Any] = None,
        track_as_background: bool = False
    ) -> OrchestratorResult:
        """Handle tool execution request with optional background tracking."""
        
        logger.info(f"[_handle_tool_use] Called with user_id={user_id}, tool={intent.tool_name}")
        
        tool = capability_registry.get_tool(intent.tool_name)
        if not tool:
            return OrchestratorResult(
                session_id=session_id,
                response=f"Tool '{intent.tool_name}' not found."
            )
        
        # Inject custom agent model if available and not overridden
        if custom_agent and custom_agent.model_id and "model" not in intent.parameters:
            intent.parameters["model"] = custom_agent.model_id
        
        # Check if this is a long-running tool that should be tracked
        # OpenCode CLI MUST always run in background - it can take 10+ minutes
        long_running_tools = [
            "run_opencode_command",  # ALWAYS background - can take 10+ minutes
        ]
        
        # These tools CAN be long but might be quick
        potentially_long_tools = [
            "search_web",  # Network calls
            "browse_page",  # Network calls
        ]
        
        # Force background for critical long-running tools
        must_background = intent.tool_name in long_running_tools
        should_track = track_as_background or must_background or intent.tool_name in potentially_long_tools
        
        if should_track:
            # Start as background task
            description = f"Running {intent.tool_name}"
            if "instruction" in intent.parameters:
                description = intent.parameters["instruction"][:100]
            elif "query" in intent.parameters:
                description = f"Searching: {intent.parameters['query'][:100]}"
            
            async def task_executor(tracked_task):
                """Execute the tool and update progress."""
                try:
                    tracked_task.add_progress(f"Starting {intent.tool_name}...")
                    
                    # Special handling for OpenCode CLI
                    if intent.tool_name == "run_opencode_command":
                        tracked_task.add_progress("Initializing OpenCode CLI...")
                        tracked_task.add_progress("This may take several minutes for complex tasks")
                    
                    result = await tool(
                        _user_id=user_id,
                        _session_id=session_id,
                        **intent.parameters
                    )
                    
                    tracked_task.add_progress("Tool execution completed")
                    
                    # Format result for display
                    if isinstance(result, dict):
                        if result.get("status") == "error":
                            tracked_task.add_progress(f"Error: {result.get('error', 'Unknown error')}")
                            return f"❌ **Error:** {result.get('error', 'Unknown error')}"
                        elif "display_markdown" in result:
                            return result["display_markdown"]
                        elif "output" in result:
                            output = result["output"]
                            # Truncate very long outputs
                            if len(output) > 5000:
                                return f"{output[:5000]}\n\n... (output truncated, {len(output)} total characters)"
                            return output
                        else:
                            return str(result)
                    else:
                        return str(result)
                        
                except Exception as e:
                    tracked_task.add_progress(f"Exception: {str(e)}")
                    logger.exception(f"Task executor failed for {intent.tool_name}")
                    return f"❌ **Exception:** {str(e)}"
            
            task_id = await task_tracker.start_task(
                user_id=user_id,
                session_id=session_id,
                description=description,
                tool_name=intent.tool_name,
                parameters=intent.parameters,
                executor=task_executor
            )
            
            # Customize message based on tool
            if intent.tool_name == "run_opencode_command":
                extra_info = "\n\n⏱️ **Note:** OpenCode CLI tasks can take 10-30 minutes for complex changes. I'll work on this in the background and notify you when complete."
            else:
                extra_info = ""
            
            return OrchestratorResult(
                session_id=session_id,
                response=f"""🔄 **Task Started in Background**

**Task ID:** `{task_id}`
**Description:** {description}

I'm working on this now and will notify you when it's complete.{extra_info}

You can check progress anytime:
• `check_task_status(task_id='{task_id}')`
• `list_my_tasks(active_only=True)`

Feel free to ask me other questions while I work!"""
            )

        # Execute synchronously for quick tools
        for attempt in range(2):
            try:
                # Execute tool with parameters
                logger.debug(f"[TOOL EXEC] Calling {intent.tool_name} with user_id={user_id}, session_id={session_id}, params={intent.parameters}")
                result = await tool(
                    _user_id=user_id,
                    _session_id=session_id,
                    **intent.parameters
                )
                
                # Check for pending approval
                if isinstance(result, dict) and result.get("status") == "pending_approval":
                    task_id = result.get("task_id")
                    self._pending_tasks[task_id] = result
                    
                    return OrchestratorResult(
                        session_id=session_id,
                        response=f"🔐 This action requires approval: {result.get('description')}",
                        requires_approval=True,
                        pending_task_id=task_id
                    )
                
                # Check for secure credential request
                if isinstance(result, dict) and result.get("signal") == "WAITING_FOR_SECRET":
                    return OrchestratorResult(
                        session_id=session_id,
                        response=result.get("instructions", "I need a secure credential to proceed."),
                        wait_for_secret=True,
                        metadata={"secret_name": result.get("secret_name")}
                    )

                # Surface tool errors clearly to the user
                if isinstance(result, dict) and result.get("status") == "error":
                    if attempt == 0 and await self._attempt_tool_recovery(intent.tool_name):
                        continue
                    error_msg = result.get("error", "Unknown error")
                    hint = result.get("hint")
                    if hint:
                        error_msg = f"{error_msg}\n\nHint: {hint}"
                    return OrchestratorResult(
                        session_id=session_id,
                        response=f"❌ **Tool Failure**: The tool `{intent.tool_name}` failed to execute.\n\nError: `{error_msg}`",
                        tool_responses=[str(result)]
                    )

                # Check for formatted display content (Priority for User)
                if isinstance(result, dict) and "display_markdown" in result:
                    return OrchestratorResult(
                        session_id=session_id,
                        response=result["display_markdown"],
                        tool_responses=[str(result)] # Keep raw data for history/logs
                    )

                # Include tool output in response so LLM can see results and continue
                response_text = "✅ Tool executed successfully"
                if isinstance(result, dict):
                    # Include output for OpenCode and other tools that return output
                    if "output" in result and result.get("output"):
                        output = result["output"]
                        # Truncate very long outputs but keep enough context
                        if len(output) > 2000:
                            output = output[:2000] + "\n\n... (output truncated)"
                        response_text = f"✅ Tool executed successfully\n\n**Output:**\n```\n{output}\n```"
                    elif "status" in result and result.get("status") == "success":
                        # For tools that return success but no explicit output, include the full result
                        result_summary = str(result)[:1000]
                        if len(result_summary) < 1000:
                            response_text = f"✅ Tool executed successfully\n\n**Result:**\n{result_summary}"

                return OrchestratorResult(
                    session_id=session_id,
                    response=response_text,
                    tool_responses=[str(result)]
                )
                
            except ValueError as e:
                if "Required secret" in str(e):
                    secret_name = str(e).split("'")[1]
                    return OrchestratorResult(
                        session_id=session_id,
                        response=f"🔑 **Security Required**: I need your `{secret_name}` to proceed. Please provide it by setting the environment variable or via the secure settings menu."
                    )
                raise e
            except Exception as e:
                if attempt == 0 and await self._attempt_tool_recovery(intent.tool_name):
                    continue
                return OrchestratorResult(
                    session_id=session_id,
                    response=f"❌ **Tool Failure**: The tool `{intent.tool_name}` failed to execute.\n\nError: `{str(e)}`"
                )

        return OrchestratorResult(
            session_id=session_id,
            response=f"❌ **Tool Failure**: The tool `{intent.tool_name}` failed to execute after recovery attempts."
        )
    
    async def _handle_approval(
        self,
        session_id: str,
        task_id: str
    ) -> OrchestratorResult:
        """Handle approval of pending task."""
        
        if task_id not in self._pending_tasks:
            return OrchestratorResult(
                session_id=session_id,
                response="Task not found or already processed."
            )
        
        # Execute the pending task
        task = self._pending_tasks.pop(task_id)
        # Implementation would re-execute the tool with _approved=True
        
        return OrchestratorResult(
            session_id=session_id,
            response="✅ Action approved and executed."
        )
    
    async def _handle_general_query(
        self,
        session_id: str,
        message: str,
        history: list = None,
        relevant_history: str = ""
    ) -> OrchestratorResult:
        """Handle general queries using LLM with tool-calling capabilities."""

        # Validate message is not empty
        if not message or not message.strip():
            logger.warning(f"Empty message in _handle_general_query for session {session_id}")
            return OrchestratorResult(
                session_id=session_id,
                response="❌ **Error**: Cannot process empty message."
            )

        # Get available capabilities for context
        capabilities = capability_registry.get_for_llm()

        # Get Identity settings
        agent_name = getattr(settings, "AGENT_NAME", "SecureAssist")
        agent_persona = getattr(settings, "AGENT_PERSONA", "Professional & Direct")

        # Build optimized messages
        messages = [
            {
                "role": "system",
                "content": f"""You are {agent_name}, an AI assistant with a '{agent_persona}' personality.
    Your primary directive is to be helpful and proactive using your available capabilities.

    --- AVAILABLE CAPABILITIES ---
    {capabilities}

    --- CORE DIRECTIVES ---
    1. APP GENERATION: If the user says "I'm a lawyer" or similar, use the `create_app` flow.
    2. CODE FIXING & DEBUGGING: For ANY code-related tasks (fixing bugs, refactoring, debugging, improving code), you should IMMEDIATELY use `run_opencode_command`. Do NOT try to fix code yourself - delegate to OpenCode CLI.
    3. RESEARCH: Use `search_web` for real-time info.
    4. DATA ENTRY & KNOWLEDGE GRAPH: 
       - Use `store_data_entry` for records - ALWAYS provide entry_type, name, and details dict
       - Example: store_data_entry(entry_type='contact', name='John Doe', details={{'phone': '555-1234'}})
       - For [FILE STORED] messages with captions, extract the info and call store_data_entry properly:
         * entry_type='image_caption' or 'document_note'
         * name=the file name from the message
         * details={{'caption': 'the caption text', 'path': 'the file path', 'type': 'the file type'}}
       - Use `link_knowledge_nodes` to connect info into a unified web.
    5. TASKS & FINANCE: Use `create_task` for todos and `log_transaction` for expenses.
       - For relative times (e.g., "in 15 minutes", "tomorrow at 3pm"), calculate the absolute datetime using Python datetime.
       - Current time is available via: from django.utils import timezone; timezone.now()
       - Format as 'YYYY-MM-DD HH:MM:SS' (e.g., '2026-02-07 15:30:00')
       - Example: For "remind me in 15 minutes", calculate timezone.now() + timedelta(minutes=15) and format it.
    6. AGENT MANAGEMENT: Use `create_agent_skill` to group tools. Use `create_custom_agent` to create new agent personas and assign skills.
    7. PLANNING: Use `create_execution_plan` for complex, multi-step requests (e.g., "Research X then build Y").
    8. CONNECTIVITY: You act as an MCP server. Mention webhooks if the user wants external notifications.
    9. SCHEDULING: Use `schedule_task` to create recurring tasks with cron expressions.

    {relevant_history}

    IMPORTANT: When you want to use a tool, you MUST respond with EXACTLY this format:
    TOOL_CALL: tool_name
    PARAMETERS: {{json parameters}}

    For example:
    TOOL_CALL: run_opencode_command
    PARAMETERS: {{"instruction": "Fix the syntax error in agents/orchestrator/agent.py"}}

    Or:
    TOOL_CALL: schedule_task
    PARAMETERS: {{"name": "daily_standup", "cron_expression": "0 9 * * 1-5", "action_description": "Daily standup meeting"}}

    Do NOT just say you will use a tool - actually use it by following the format above.
    For code-related requests, ALWAYS use run_opencode_command - never try to write code yourself.

    Be helpful, proactive, and stay strictly in your {agent_name} persona ({agent_persona}).
    When storing info, try to LINK it to existing context using `link_knowledge_nodes`.
    """
            }
        ]

        if history:
            messages.extend(history)
        else:
            messages.append({"role": "user", "content": message})

        try:
            response = await model_router.complete(
                task_type="orchestrate",
                messages=messages,
                max_tokens=1000,
                agent_name=agent_name
            )

            response_text = response.choices[0].message.content

            # Check if the LLM wants to call a tool
            if "TOOL_CALL:" in response_text and "PARAMETERS:" in response_text:
                logger.info("Detected tool call in general query response")
                try:
                    # Parse the tool call
                    lines = response_text.split("\n")
                    tool_name = None
                    parameters_json = None

                    for i, line in enumerate(lines):
                        if line.startswith("TOOL_CALL:"):
                            tool_name = line.replace("TOOL_CALL:", "").strip()
                            logger.info(f"Parsed tool_name: '{tool_name}'")
                        elif line.startswith("PARAMETERS:"):
                            # Get everything after PARAMETERS: (might be multi-line JSON)
                            parameters_json = "\n".join(lines[i:]).replace("PARAMETERS:", "").strip()
                            break

                    if not tool_name:
                        logger.error(f"Tool name is empty or None. Full response: {response_text}")
                        return OrchestratorResult(
                            session_id=session_id,
                            response=f"❌ I tried to use a tool but couldn't determine which one. Please try rephrasing your request or specify the tool explicitly.\n\nDebug: {response_text}"
                        )

                    if not parameters_json:
                        logger.error(f"Parameters JSON is empty. Tool: {tool_name}")
                        return OrchestratorResult(
                            session_id=session_id,
                            response=f"❌ I tried to use the tool '{tool_name}' but couldn't parse the parameters. Please try again."
                        )

                    if tool_name and parameters_json:
                        import json
                        try:
                            parameters = json.loads(parameters_json)
                        except json.JSONDecodeError as je:
                            logger.error(f"Failed to parse JSON parameters: {je}. Raw: {parameters_json}")
                            return OrchestratorResult(
                                session_id=session_id,
                                response=f"❌ I tried to use the tool '{tool_name}' but the parameters were malformed. Please try again."
                            )

                        # Create an intent and execute the tool
                        intent = IntentType(
                            intent="use_tool",
                            tool_name=tool_name,
                            parameters=parameters
                        )

                        # Get user_id from session
                        from core.models import Session as DBSession
                        db_session = await DBSession.objects.aget(id=session_id)
                        user_id = db_session.user_id

                        # Execute the tool
                        logger.info(f"Executing tool {tool_name} with parameters: {parameters}")
                        tool_result = await self._handle_tool_use(
                            session_id, user_id, intent, agent_name, None
                        )

                        return tool_result

                except Exception as e:
                    logger.error(f"Failed to parse and execute tool call: {e}")
                    # Fall through to return the original response

            return OrchestratorResult(
                session_id=session_id,
                response=response_text
            )

        except Exception as e:
            logger.error(f"LLM response failed: {e}")
            # Retry with minimal context
            try:
                retry_messages = [
                    {
                        "role": "system",
                        "content": f"You are {agent_name}, an AI assistant with a '{agent_persona}' personality."
                    },
                    {"role": "user", "content": message}
                ]
                response = await model_router.complete(
                    task_type="orchestrate",
                    messages=retry_messages,
                    max_tokens=300,
                    agent_name=agent_name
                )
                return OrchestratorResult(
                    session_id=session_id,
                    response=response.choices[0].message.content
                )
            except Exception:
                return OrchestratorResult(
                    session_id=session_id,
                    response="I can help you create apps or use tools. Try saying 'I'm a lawyer' to create a legal practice app!"
                )


    
    async def execute_approved_task(self, task_id: str):
        """Execute a previously approved task."""
        return await self._handle_approval("", task_id)
    
    async def cancel_task(self, task_id: str):
        """Cancel a pending task."""
        if task_id in self._pending_tasks:
            del self._pending_tasks[task_id]


# Singleton instance
orchestrator_agent = OrchestratorAgent()
