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
