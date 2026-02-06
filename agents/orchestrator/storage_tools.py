"""
Document Management & Briefing Tools - Agent-callable tools for organization and status.
"""
import logging
from core.decorators import agent_tool
from core.services.storage.intelligent_storage import storage_service
from core.services.briefing import briefing_service

logger = logging.getLogger(__name__)

@agent_tool(
    name="organize_document",
    description="Categorize and move a document to structured storage. Categories: legal, medical, finance, technical, custom.",
    category="storage"
)
async def organize_document(file_path: str, category: str, project: str = "general"):
    """Organizes a file into the document management system."""
    try:
        new_path = storage_service.organize_file(file_path, category, project)
        return {
            "status": "organized",
            "category": category,
            "project": project,
            "new_location": new_path
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@agent_tool(
    name="list_documents",
    description="List all organized documents. Can filter by category or project.",
    category="storage"
)
async def list_documents(category: str = None, project: str = None):
    """Lists documents in managed storage."""
    docs = storage_service.list_documents(category, project)
    return {"documents": docs}

@agent_tool(
    name="generate_daily_briefing",
    description="Run a 'Sweeper' to summarize all activity from today and generate a briefing report.",
    category="system"
)
async def generate_daily_briefing(_user_id: str = None):
    """Generates the AI-synthesized daily briefing."""
    report = await briefing_service.generate_daily_report(_user_id)
    return {"briefing_report": report}
