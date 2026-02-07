"""
Knowledge Graph & OS Tools - Agent-callable tools for cross-app intelligence.
"""
import logging
from core.decorators import agent_tool
from core.services.knowledge_graph import knowledge_graph_service

logger = logging.getLogger(__name__)

@agent_tool(
    name="link_knowledge_nodes",
    description="Create a semantic link between two items (e.g., a document and a contact).",
    category="system"
)
async def link_knowledge_nodes(
    source_id: str,
    source_type: str,
    target_id: str,
    target_type: str,
    relation: str = "related_to",
    _user_id: str = None,
    _session_id: str = None
):
    """Creates a link in the knowledge graph."""
    rel = await knowledge_graph_service.link(
        user_id=_user_id,
        source_id=source_id,
        source_type=source_type,
        target_id=target_id,
        target_type=target_type,
        relation_type=relation
    )
    return {
        "status": "linked",
        "relation": relation,
        "source": source_id,
        "target": target_id
    }

@agent_tool(
    name="query_knowledge_graph",
    description="Find all relations for a specific node in the knowledge graph.",
    category="system"
)
async def query_knowledge_graph(node_id: str, _user_id: str = None, _session_id: str = None):
    """Queries the knowledge graph for relations."""
    relations = await knowledge_graph_service.get_relations(_user_id, node_id)
    return {"node_id": node_id, "relations": relations}
