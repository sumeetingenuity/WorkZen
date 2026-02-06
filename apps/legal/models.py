import uuid
from django.db import models


class UUIDTimestampModel(models.Model):
    """Abstract base model with UUID primary key and timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Client(UUIDTimestampModel):
    """Client entity for domain management."""

    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Case(UUIDTimestampModel):
    """Case entity for domain management."""

    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="cases")
    court_date = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Document(UUIDTimestampModel):
    """Document entity for domain management."""

    title = models.CharField(max_length=300)
    file = models.FileField(upload_to="legal/documents/")
    document_type = models.CharField(max_length=50)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Contract(UUIDTimestampModel):
    """Contract entity for domain management."""

    title = models.CharField(max_length=300)
    template = models.TextField(blank=True, null=True)
    generated_text = models.TextField(blank=True, null=True)
    signed = models.BooleanField(default=False)
    signed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class CourtDate(UUIDTimestampModel):
    """CourtDate entity for domain management."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Invoice(UUIDTimestampModel):
    """Invoice entity for domain management."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
