"""
Tools for the agents app.

This module imports and re-exports tools from the orchestrator subpackage
so they can be discovered by the capability registry.
"""

# Import orchestrator tools to register them with the capability registry
from agents.orchestrator.agent_management_tools import (
    create_agent_skill,
    create_custom_agent,
    run_opencode_command,
)

from agents.orchestrator.task_tools import (
    create_task,
    list_tasks,
    complete_task,
)

from agents.orchestrator.task_status_tools import (
    check_task_status,
    list_my_tasks,
    cancel_task as cancel_tracked_task,
)

from agents.orchestrator.planning_tools import (
    create_execution_plan,
    execute_plan,
)

from agents.orchestrator.feed_tools import (
    subscribe_to_intelligence_feed,
    list_intelligence_feeds,
    unsubscribe_from_feed,
)

from agents.orchestrator.credential_tools import (
    request_secure_credential,
)

from agents.orchestrator.finance_tools import (
    log_transaction,
    get_financial_report,
)

from agents.orchestrator.kg_tools import (
    link_knowledge_nodes,
    query_knowledge_graph,
)

from agents.orchestrator.scheduling_tools import (
    schedule_task,
    list_scheduled_tasks,
    cancel_task as cancel_scheduled_task,
)

from agents.orchestrator.storage_tools import (
    organize_document,
    list_documents,
    generate_daily_briefing,
)

__all__ = [
    "create_agent_skill",
    "create_custom_agent",
    "run_opencode_command",
    "create_task",
    "list_tasks",
    "complete_task",
    "check_task_status",
    "list_my_tasks",
    "cancel_tracked_task",
    "create_execution_plan",
    "execute_plan",
    "subscribe_to_intelligence_feed",
    "list_intelligence_feeds",
    "unsubscribe_from_feed",
    "request_secure_credential",
    "log_transaction",
    "get_financial_report",
    "link_knowledge_nodes",
    "query_knowledge_graph",
    "schedule_task",
    "list_scheduled_tasks",
    "cancel_scheduled_task",
    "organize_document",
    "list_documents",
    "generate_daily_briefing",
]
