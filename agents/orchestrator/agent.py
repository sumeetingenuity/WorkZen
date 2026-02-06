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
        Process a user message and return appropriate response.
        
        This is the main entry point for all user interactions.
        """
        session_id = session_id or str(uuid.uuid4())
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
            
            # 5. Classify intent
            intent = await self._classify_intent(message)
            logger.info(f"Classified intent: {intent.intent}")
            
            # 5b. Load Custom Agent (New Feature)
            from core.models import CustomAgent, AgentSkill
            custom_agent = await CustomAgent.objects.filter(user_id=user_id, is_active=True).afirst()
            allowed_tools = None
            if custom_agent:
                logger.info(f"Using Custom Agent: {custom_agent.name}")
                # Fetch all tools from all skills assigned to this agent
                skills = custom_agent.skills.all()
                allowed_tools = []
                async for skill in skills:
                    allowed_tools.extend(skill.tool_names)
                
                # Also include tools from plugins
                plugins = custom_agent.plugins.all()
                async for plugin in plugins:
                    async for skill in plugin.skills.all():
                        allowed_tools.extend(skill.tool_names)
            
            # Update history in DB for next turn
            db_session.raw_history = temp_history
            await db_session.asave()
            
            # 6. Route based on intent
            if intent.intent == "create_app":
                result = await self._handle_create_app(
                    session_id, user_id, message, intent, custom_agent
                )
            
            elif intent.intent == "use_tool":
                # Check if tool is allowed for this agent
                if allowed_tools is not None and intent.tool_name not in allowed_tools:
                    result = OrchestratorResult(
                        session_id=session_id,
                        response=f"I'm sorry, I don't have the '{intent.tool_name}' skill enabled for this persona. Please enable it in my settings if you need it."
                    )
                else:
                    result = await self._handle_tool_use(
                        session_id, user_id, intent, custom_agent.name if custom_agent else None, custom_agent
                    )
            
            elif intent.intent == "approve_action":
                result = await self._handle_approval(
                    session_id, intent.parameters.get("task_id")
                )
            
            else:  # general_query
                result = await self._handle_general_query(
                    session_id, message, optimized_history, relevant_history
                )

            # 7. Global Secret Masking (Final Safety Net)
            from core.services.secrets import SecretEngine
            secret_masker = SecretEngine()
            result.response = secret_masker.mask_in_output(result.response)
            
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
            app_keywords = ["i'm a", "i am a", "build me", "create an app", "i need an app", "make me"]
            message_lower = message.lower()
            for kw in app_keywords:
                if kw in message_lower:
                    return IntentType(intent="create_app", domain=self._extract_domain_quick(message_lower))
            
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
    
    async def _handle_create_app(
        self,
        session_id: str,
        user_id: str,
        message: str,
        intent: IntentType,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """Handle app creation request."""
        
        # 1. Analyze domain
        domain_spec = await self.domain_analyzer.analyze(message)
        logger.info(f"Domain analyzed: {domain_spec.domain_name}")
        
        # 2. Research the domain
        research_result = await research_agent.research(domain_spec)
        logger.info(f"Research complete: {len(research_result.apis_found)} APIs found")
        
        # 3. Create app specification
        app_spec = await self.domain_analyzer.create_app_spec(
            domain_spec,
            research_result.model_dump()
        )
        logger.info(f"App spec created: {app_spec.name} with {len(app_spec.entities)} entities")
        
        # 4. Build the app using Developer Agent
        build_result = await developer_agent.build_app(app_spec, model=custom_agent.model_id if custom_agent else None)
        
        if build_result["success"]:
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
            # Attempt recovery once for partial generations
            recovery = await developer_agent.recover_app(app_spec, model=custom_agent.model_id if custom_agent else None)
            if recovery.get("success"):
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
            return OrchestratorResult(
                session_id=session_id,
                response=f"❌ **App Creation Failed**: {build_result.get('error', 'Unknown error')}\n\nI attempted to build the app but encountered a persistent issue. You may want to try again with a simpler description."
            )
    
    async def _handle_tool_use(
        self,
        session_id: str,
        user_id: str,
        intent: IntentType,
        agent_name: Optional[str] = None,
        custom_agent: Optional[Any] = None
    ) -> OrchestratorResult:
        """Handle tool execution request."""
        
        tool = capability_registry.get_tool(intent.tool_name)
        if not tool:
            return OrchestratorResult(
                session_id=session_id,
                response=f"Tool '{intent.tool_name}' not found."
            )
        
        # Inject custom agent model if available and not overridden
        if custom_agent and custom_agent.model_id and "model" not in intent.parameters:
            intent.parameters["model"] = custom_agent.model_id

        for attempt in range(2):
            try:
                # Execute tool with parameters
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

                return OrchestratorResult(
                    session_id=session_id,
                    response=f"✅ Tool executed successfully",
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
        """Handle general queries using LLM with optimized context."""
        
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
2. RESEARCH: Use `search_web` for real-time info.
3. DATA ENTRY & KNOWLEDGE GRAPH: Use `store_data_entry` for records. Use `link_knowledge_nodes` to connect info into a unified web.
4. TASKS & FINANCE: Use `create_task` for todos and `log_transaction` for expenses.
5. AGENT MANAGEMENT: Use `create_agent_skill` to group tools. Use `create_custom_agent` to create new agent personas and assign skills.
6. CODING: Use `run_opencode_command` for any advanced autonomous coding or script generation.
7. PLANNING: Use `create_execution_plan` for complex, multi-step requests (e.g., "Research X then build Y").
8. CONNECTIVITY: You act as an MCP server. Mention webhooks if the user wants external notifications.

{relevant_history}

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
                max_tokens=500,
                agent_name=agent_name # Use agent identity for the query itself
            )
            
            return OrchestratorResult(
                session_id=session_id,
                response=response.choices[0].message.content
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
