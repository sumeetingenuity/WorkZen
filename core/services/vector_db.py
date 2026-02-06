"""
VectorDB Service - Provides semantic search and storage for agent memory.

Uses LanceDB (serverless, disk-based) and cloud embeddings via ModelRouter.
"""
import logging
import os
import asyncio
from typing import List, Dict, Any, Optional
import lancedb
import pyarrow as pa
from django.conf import settings
from agents.model_router import model_router

logger = logging.getLogger(__name__)

class VectorDBService:
    """
    Service for semantic storage and retrieval.
    
    Used for:
    1. Long-term conversation memory
    2. Tool result recall
    3. Document semantic search
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize LanceDB."""
        self.db_path = os.path.join(settings.BASE_DIR, "data", "vector_db")
        os.makedirs(self.db_path, exist_ok=True)
        
        self.db = lancedb.connect(self.db_path)
        self.tables = {}
        logger.info(f"VectorDB Service initialized at {self.db_path}")
    
    async def _get_table(self, table_name: str):
        """Get or create a LanceDB table."""
        if table_name not in self.tables:
            if table_name in self.db.table_names():
                self.tables[table_name] = self.db.open_table(table_name)
            else:
                # Use a dummy embedding to determine dimension on first create
                # Standard OpenAI small is 1536
                dim = 1536 
                schema = pa.schema([
                    pa.field("vector", pa.list_(pa.float32(), dim)),
                    pa.field("text", pa.string()),
                    pa.field("metadata", pa.string()),
                    pa.field("id", pa.string())
                ])
                self.tables[table_name] = self.db.create_table(table_name, schema=schema)
        return self.tables[table_name]

    async def add_to_memory(
        self, 
        collection_name: str, 
        text: str, 
        metadata: Dict[str, Any], 
        id: str
    ):
        """Add a text segment to the specified collection."""
        try:
            # 1. Get embedding (with mock fallback for testing)
            if os.environ.get("MOCK_EMBEDDING") == "true":
                import numpy as np
                vector = np.random.rand(1536).tolist()
            else:
                vector = await model_router.embed(text)
            
            # 2. Add to table
            table = await self._get_table(collection_name)
            
            import json
            data = [{
                "vector": vector,
                "text": text,
                "metadata": json.dumps(metadata),
                "id": id
            }]
            
            # LanceDB add is synchronous in the client, but we'll wrap it for consistency
            table.add(data)
            logger.debug(f"Added item {id} to {collection_name}")
        except Exception as e:
            logger.error(f"Failed to add to VectorDB: {e}")
    
    async def search(
        self, 
        collection_name: str, 
        query: str, 
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for semantically similar items."""
        try:
            # 1. Get embedding for query (with mock fallback)
            if os.environ.get("MOCK_EMBEDDING") == "true":
                import numpy as np
                vector = np.random.rand(1536).tolist()
            else:
                vector = await model_router.embed(query)
            
            # 2. Search table
            table = await self._get_table(collection_name)
            
            # LanceDB search
            query_builder = table.search(vector).limit(n_results)
            
            # Note: LanceDB filtering uses SQL strings, for now we skip complex filters 
            # or map them if needed.
            
            results = query_builder.to_pandas()
            
            import json
            formatted = []
            for _, row in results.iterrows():
                # Filter by metadata session_id if provided in 'where' (manual fallback)
                meta = json.loads(row['metadata'])
                if where:
                    match = True
                    for k, v in where.items():
                        if meta.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                        
                formatted.append({
                    "content": row['text'],
                    "metadata": meta,
                    "id": row['id'],
                    "distance": row['_distance'] if '_distance' in row else None
                })
            
            return formatted
        except Exception as e:
            logger.error(f"VectorDB search failed: {e}")
            return []

# Singleton instance
vector_db = VectorDBService()
