"""
Storage Tools for SecureAssist.
"""
from core.decorators import agent_tool


@agent_tool(
    name="upload_file",
    description="Upload and store a file. Returns file ID for later retrieval.",
    log_response_to_orm=True,
    category="storage"
)
async def upload_file(file_path: str, description: str = "") -> dict:
    """
    Upload a file to storage.
    """
    import os
    import shutil
    import uuid
    from django.conf import settings
    
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    file_id = str(uuid.uuid4())
    filename = os.path.basename(file_path)
    dest_dir = settings.MEDIA_ROOT / 'uploads'
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = dest_dir / f"{file_id}_{filename}"
    shutil.copy2(file_path, dest_path)
    
    return {
        "file_id": file_id,
        "filename": filename,
        "path": str(dest_path),
        "description": description
    }


@agent_tool(
    name="store_document",
    description="Store a document and track metadata (type, user, session).",
    log_response_to_orm=True,
    category="storage"
)
async def store_document(
    file_path: str,
    file_type: str,
    original_name: str,
    mime_type: str = "",
    description: str = "",
    user_id: str = "",
    session_id: str = ""
) -> dict:
    import os
    import shutil
    import uuid
    from asgiref.sync import sync_to_async
    from django.conf import settings
    from apps.storage.models import StoredDocument

    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    file_id = str(uuid.uuid4())
    safe_type = (file_type or "document").lower()
    dest_dir = settings.MEDIA_ROOT / "uploads" / safe_type
    dest_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{file_id}_{original_name}"
    dest_path = dest_dir / stored_name
    shutil.copy2(file_path, dest_path)

    doc = await sync_to_async(StoredDocument.objects.create)(
        user_id=user_id or None,
        session_id=session_id or None,
        original_name=original_name,
        stored_name=stored_name,
        stored_path=str(dest_path),
        file_type=safe_type,
        mime_type=mime_type or None,
        description=description
    )

    return {
        "document_id": str(doc.id),
        "original_name": original_name,
        "stored_name": stored_name,
        "path": str(dest_path),
        "file_type": safe_type,
        "mime_type": mime_type,
        "description": description
    }


@agent_tool(
    name="search_documents",
    description="Search stored documents by filename or type.",
    log_response_to_orm=True,
    category="storage"
)
async def search_documents(query: str = "", file_type: str = "", limit: int = 20) -> dict:
    from asgiref.sync import sync_to_async
    from apps.storage.models import StoredDocument

    def _query():
        qs = StoredDocument.objects.all()
        if file_type:
            qs = qs.filter(file_type__iexact=file_type)
        if query:
            qs = qs.filter(original_name__icontains=query)
        return list(qs[:limit])

    rows = await sync_to_async(_query)()
    results = [
        {
            "id": str(d.id),
            "name": d.original_name,
            "path": d.stored_path,
            "file_type": d.file_type,
            "mime_type": d.mime_type,
            "description": d.description
        }
        for d in rows
    ]
    return {"results": results}


@agent_tool(
    name="get_last_document",
    description="Get the most recently stored document for a user.",
    log_response_to_orm=True,
    category="storage"
)
async def get_last_document(user_id: str) -> dict:
    from asgiref.sync import sync_to_async
    from apps.storage.models import StoredDocument

    def _get():
        return StoredDocument.objects.filter(user_id=user_id).order_by("-created_at").first()

    doc = await sync_to_async(_get)()
    if not doc:
        return {"error": "No stored documents found for this user."}
    return {
        "id": str(doc.id),
        "name": doc.original_name,
        "path": doc.stored_path,
        "file_type": doc.file_type,
        "mime_type": doc.mime_type,
        "description": doc.description
    }


@agent_tool(
    name="list_files",
    description="List all stored files.",
    log_response_to_orm=True,
    category="storage"
)
async def list_files() -> dict:
    """
    List files in storage.
    """
    import os
    from django.conf import settings
    
    upload_dir = settings.MEDIA_ROOT / 'uploads'
    
    if not upload_dir.exists():
        return {"files": []}
    
    files = []
    for f in os.listdir(upload_dir):
        path = upload_dir / f
        files.append({
            "filename": f,
            "size_bytes": os.path.getsize(path),
        })
    
    return {"files": files}
