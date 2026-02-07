"""
Universal Productivity Tools - Core essentials for everyday computer tasks.
"""
import logging
from typing import Optional, Dict, Any, List
from core.decorators import agent_tool
from core.models import GenericEntity

logger = logging.getLogger(__name__)

# --- Structured Data Entry Tools ---

@agent_tool(
    name="store_data_entry",
    description="""Store structured information like contact details, company info, notes, or custom records.
    
    REQUIRED PARAMETERS:
    - entry_type (str): Type of entry (e.g., 'contact', 'note', 'company', 'image_caption', 'document')
    - name (str): Name or title of the entry (e.g., person's name, document title)
    - details (dict): The actual data to store as key-value pairs
    
    OPTIONAL:
    - tags (list): List of tags for categorization
    
    EXAMPLES:
    1. Store contact: entry_type='contact', name='John Doe', details={'phone': '555-1234', 'email': 'john@example.com'}
    2. Store note: entry_type='note', name='Meeting Notes', details={'content': 'Discussed project timeline', 'date': '2026-02-07'}
    3. Store image caption: entry_type='image_caption', name='Photo Description', details={'caption': 'Sunset at the beach', 'file_id': '123'}
    
    IMPORTANT: Always provide ALL required parameters. Do not call with empty dict.""",
    category="productivity"
)
async def store_data_entry(
    entry_type: str,
    name: str,
    details: Dict[str, Any],
    tags: Optional[List[str]] = None,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """
    Stores a generic entity for persistent structured memory.
    Useful for 'Data Entry' tasks.
    """
    entity, created = await GenericEntity.objects.aupdate_or_create(
        user_id=_user_id,
        entity_type=entry_type.lower(),
        name=name,
        defaults={
            "data": details,
            "tags": tags or []
        }
    )
    
    return {
        "status": "created" if created else "updated",
        "entity_id": str(entity.id),
        "type": entry_type,
        "name": name
    }

@agent_tool(
    name="search_data_entry",
    description="Search for stored structured information (contacts, companies, etc.).",
    category="productivity"
)
async def search_data_entry(
    query: str,
    entry_type: Optional[str] = None,
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """Searches the GenericEntity registry."""
    from django.db.models import Q
    
    qs = GenericEntity.objects.filter(user_id=_user_id)
    if entry_type:
        qs = qs.filter(entity_type=entry_type.lower())
        
    qs = qs.filter(Q(name__icontains=query) | Q(data__icontains=query))
    
    results = []
    async for item in qs[:10]:
        results.append({
            "type": item.entity_type,
            "name": item.name,
            "data": item.data,
            "tags": item.tags
        })
        
    return {"results": results}

# --- Calendar / Timeline Tools ---

@agent_tool(
    name="manage_calendar_event",
    description="Create or update a calendar event (appointment, meeting, reminder).",
    category="productivity"
)
async def manage_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    description: Optional[str] = "",
    _user_id: str = None,
    _session_id: str = None
) -> dict:
    """
    Core calendar management tool. 
    In this version, we use the CronJob model to also handle 'Reminders' 
    but for pure calendar events, we use the GenericEntity with type='calendar_event'.
    """
    data = {
        "start_time": start_time,
        "end_time": end_time,
        "description": description
    }
    
    entity, created = await GenericEntity.objects.aupdate_or_create(
        user_id=_user_id,
        entity_type="calendar_event",
        name=title,
        defaults={"data": data}
    )
    
    return {
        "status": "event_created" if created else "event_updated",
        "title": title,
        "start": start_time
    }

@agent_tool(
    name="list_calendar",
    description="List upcoming calendar events.",
    category="productivity"
)
async def list_calendar(_user_id: str = None, _session_id: str = None) -> dict:
    """Lists all calendar events from the generic repository."""
    qs = GenericEntity.objects.filter(user_id=_user_id, entity_type="calendar_event")
    
    events = []
    async for item in qs:
        events.append({
            "title": item.name,
            "start": item.data.get("start_time"),
            "end": item.data.get("end_time"),
            "description": item.data.get("description")
        })
        
    return {"calendar_events": events}


# --- Communication Extension Tools ---

@agent_tool(
    name="check_inbox",
    description="Check for new or recent communications (emails, messages).",
    category="communication",
    secrets=["EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD"]
)
async def check_inbox(
    limit: int = 5,
    _user_id: str = None,
    _session_id: str = None,
    _secret_EMAIL_HOST_USER: str = None,
    _secret_EMAIL_HOST_PASSWORD: str = None
) -> dict:
    """
    Checks the inbox for recent activity.
    In this version, we provide a placeholder that interacts with the user's
    configured notification streams.
    """
    # Placeholder for IMAP logic
    # In a full implementation, this uses imaplib with secrets from vault
    
    return {
        "status": "checked",
        "recent_messages": [
            {"from": "system@secureassist.io", "subject": "Welcome to your new HQ", "preview": "Your digital fortress is ready..."},
            {"from": "noreply@github.com", "subject": "[SecureAssist] New feature push", "preview": "A new version of the platform has been deployed..."}
        ],
        "note": "IMAP integration pending user credential verification in onboard.py"
    }
