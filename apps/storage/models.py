import uuid
from django.db import models


class StoredDocument(models.Model):
    """Metadata for stored documents/files."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    session_id = models.UUIDField(blank=True, null=True, db_index=True)
    original_name = models.CharField(max_length=255)
    stored_name = models.CharField(max_length=255)
    stored_path = models.TextField()
    file_type = models.CharField(max_length=50, db_index=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.original_name} ({self.file_type})"
