"""
Knowledge Graph Service - Manages relations between entities, documents, and sessions.
"""
import logging
from core.models import EntityRelation
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class KnowledgeGraphService:
    """
    Manages the Knowledge Graph infrastructure.
    Allows for linking disparate data points into a meaningful web.
    """
    
    async def link(
        self,
        user_id: str,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        relation_type: str = "related_to",
        strength: float = 1.0,
        metadata: Dict[str, Any] = None
    ):
        """Creates or updates a link between two entities."""
        relation, created = await EntityRelation.objects.aupdate_or_create(
            user_id=user_id,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            defaults={
                "source_type": source_type,
                "target_type": target_type,
                "strength": strength,
                "metadata": metadata or {}
            }
        )
        logger.info(f"Knowledge Link: {source_id} --({relation_type})--> {target_id} [{'created' if created else 'updated'}]")
        return relation

    async def get_relations(self, user_id: str, node_id: str) -> List[Dict[str, Any]]:
        """Gets all outgoing and incoming relations for a node."""
        from django.db.models import Q
        
        qs = EntityRelation.objects.filter(
            Q(source_id=node_id) | Q(target_id=node_id),
            user_id=user_id
        )
        
        relations = []
        async for r in qs:
            relations.append({
                "id": str(r.id),
                "source": {"id": r.source_id, "type": r.source_type},
                "target": {"id": r.target_id, "type": r.target_type},
                "relation": r.relation_type,
                "strength": r.strength,
                "metadata": r.metadata
            })
        return relations

knowledge_graph_service = KnowledgeGraphService()
