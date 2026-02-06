"""
Intelligent Storage Service - Manages document organization and lifecycle.
"""
import os
import shutil
import logging
from pathlib import Path
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class StorageService:
    """
    Handles file uploads, organization, and retrieval.
    Automatically categorizes documents into a structured directory tree.
    """
    
    def __init__(self):
        self.base_path = Path(settings.BASE_DIR) / "data" / "documents"
        os.makedirs(self.base_path, exist_ok=True)

    def organize_file(self, file_path: str, category: str, project: Optional[str] = "general") -> str:
        """
        Moves a file into a structured directory: data/documents/{category}/{project}/
        """
        source = Path(file_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file {file_path} not found.")

        target_dir = self.base_path / category / project
        os.makedirs(target_dir, exist_ok=True)
        
        target_path = target_dir / source.name
        
        # Move or Copy (here we move to keep workspace clean)
        shutil.move(str(source), str(target_path))
        logger.info(f"File organized: {source.name} -> {category}/{project}")
        
        return str(target_path)

    def list_documents(self, category: Optional[str] = None, project: Optional[str] = None):
        """List documents in the managed storage."""
        docs = []
        search_path = self.base_path
        if category:
            search_path = search_path / category
            if project:
                search_path = search_path / project

        if not search_path.exists():
            return []

        for root, dirs, files in os.walk(search_path):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(self.base_path)
                docs.append({
                    "name": file,
                    "rel_path": str(rel_path),
                    "full_path": str(full_path),
                    "size": full_path.stat().st_size
                })
        return docs

storage_service = StorageService()
