"""
Core models for SecureAssist.

Includes:
- ToolResponse: Direct-to-ORM response logging
- ToolPolicy: Access control policies
- AuditLog: Comprehensive audit trail
"""
import uuid
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class ToolResponse(models.Model):
    """
    Stores all tool responses for direct user display.
    
    This is the key optimization: API responses are logged directly
    to the database and shown to users, bypassing expensive LLM re-ingestion.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tool_name = models.CharField(max_length=100, db_index=True)
    session_id = models.UUIDField(db_index=True, null=True, blank=True)
    
    # Input tracking
    input_data = models.JSONField(default=dict)
    input_hash = models.CharField(max_length=64, db_index=True)  # For deduplication
    
    # Response data (full data for user, summary for LLM)
    response_data = models.JSONField(default=dict)
    response_summary = models.TextField(max_length=500)  # Short summary for LLM context
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    execution_time_ms = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('error', 'Error'),
            ('timeout', 'Timeout'),
            ('partial', 'Partial'),
        ],
        default='success'
    )
    
    # Link to typed response model (optional polymorphism)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    typed_response = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id', 'created_at']),
            models.Index(fields=['tool_name', 'input_hash']),
        ]
    
    def __str__(self):
        return f"{self.tool_name} @ {self.created_at}"


class ToolPolicy(models.Model):
    """
    Access control policies for tools.
    
    Each tool can have specific:
    - Allowed users
    - Rate limits
    - Approval requirements
    - Blocked input patterns
    """
    tool_name = models.CharField(max_length=100, unique=True, db_index=True)
    allowed_users = models.JSONField(
        default=list, 
        blank=True, 
        help_text="User IDs allowed. Empty = all users."
    )
    rate_limit = models.IntegerField(default=100, help_text="Max calls per hour")
    requires_approval = models.BooleanField(default=False)
    blocked_inputs = models.JSONField(
        default=list, 
        blank=True, 
        help_text="Regex patterns to block"
    )
    enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Tool Policies"
    
    def __str__(self):
        return f"Policy: {self.tool_name}"


class AuditLog(models.Model):
    """
    Comprehensive audit trail for all agent actions.
    
    Records tool executions, policy decisions, and agent actions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Action details
    action = models.CharField(max_length=50, db_index=True)
    tool = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    execution_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Actor
    user_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    agent = models.CharField(max_length=50, null=True, blank=True)
    session_id = models.UUIDField(null=True, blank=True, db_index=True)
    
    # Details (NEVER include secrets)
    input_summary = models.TextField(max_length=500, blank=True)
    output_summary = models.TextField(max_length=500, blank=True)
    error = models.TextField(blank=True)
    
    # Metadata
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('error', 'Error'),
            ('denied', 'Denied'),
            ('timeout', 'Timeout'),
            ('pending', 'Pending'),
        ],
        default='success'
    )
    execution_time_ms = models.IntegerField(null=True, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Additional context
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['user_id', 'created_at']),
            models.Index(fields=['tool', 'status']),
        ]
    
    def __str__(self):
        return f"{self.action}: {self.tool or 'N/A'} @ {self.created_at}"


class Session(models.Model):
    """
    Agent session for context management.
    
    Tracks conversation state, compressed context, and plans.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    # Context layers
    session_summary = models.TextField(blank=True)  # Compressed chat history
    daily_plan = models.JSONField(default=dict, blank=True)
    weekly_plan = models.JSONField(default=dict, blank=True)
    current_task = models.JSONField(default=dict, blank=True)
    
    # Raw history (last N turns before compression)
    raw_history = models.JSONField(default=list)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user_id', 'is_active']),
        ]
    
    def __str__(self):
        return f"Session {self.id} for {self.user_id}"


class PendingApproval(models.Model):
    """
    Pending tool executions waiting for user approval.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='pending_approvals')
    
    tool_name = models.CharField(max_length=100)
    input_data = models.JSONField(default=dict)
    description = models.TextField()
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('expired', 'Expired'),
        ],
        default='pending'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Approval: {self.tool_name} ({self.status})"


class CronJob(models.Model):
    """
    Tracks dynamic cron jobs scheduled by agents.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    session_id = models.UUIDField(null=True, blank=True)
    
    name = models.CharField(max_length=200, help_text="User-friendly name of the job")
    cron_expression = models.CharField(max_length=100, help_text="Standard crontab format (* * * * *)")
    
    # Task details
    task_type = models.CharField(max_length=50, default="tool_execution")
    tool_name = models.CharField(max_length=100, null=True, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', 'is_active']),
        ]
    
    def __str__(self):
        return f"Cron: {self.name} ({self.cron_expression})"


class GenericEntity(models.Model):
    """
    Schema-less storage for structured data (Contacts, Nodes, Leads, etc.)
    Allows agents to perform 'Data Entry' without generating specific models.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    entity_type = models.CharField(max_length=50, db_index=True, help_text="e.g., person, company, lead")
    name = models.CharField(max_length=200, db_index=True)
    
    # The actual data
    data = models.JSONField(default=dict)
    
    # Metadata for recall
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user_id', 'entity_type']),
            models.Index(fields=['name']),
        ]
        unique_together = ('user_id', 'entity_type', 'name')
    
    def __str__(self):
        return f"{self.entity_type.capitalize()}: {self.name}"


class EntityRelation(models.Model):
    """
    Knowledge Graph Relations - Links entities, documents, or sessions.
    Allows for complex traversal (e.g., 'Draft linked to Client X').
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    source_type = models.CharField(max_length=50, help_text="e.g., document, contact, task")
    source_id = models.CharField(max_length=100, db_index=True)
    
    target_type = models.CharField(max_length=50, help_text="e.g., project, company, user")
    target_id = models.CharField(max_length=100, db_index=True)
    
    relation_type = models.CharField(max_length=50, help_text="e.g., belongs_to, mentioned_in, related_to")
    strength = models.FloatField(default=1.0)
    
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user_id', 'source_id']),
            models.Index(fields=['user_id', 'target_id']),
        ]
        unique_together = ('user_id', 'source_id', 'target_id', 'relation_type')

    def __str__(self):
        return f"{self.source_id} --({self.relation_type})--> {self.target_id}"


class TaskEntity(models.Model):
    """
    Proactive Task Engine - Tracks todo items and their lifecycle.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    priority = models.IntegerField(default=2, choices=[(1, 'High'), (2, 'Medium'), (3, 'Low')])
    status = models.CharField(
        max_length=20,
        choices=[('todo', 'Todo'), ('in_progress', 'In Progress'), ('done', 'Done'), ('cancelled', 'Cancelled')],
        default='todo'
    )
    
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    project = models.CharField(max_length=100, null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    
    # DAG / Automation Fields
    dependencies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='blocked_by')
    payload = models.JSONField(default=dict, blank=True, help_text="Input arguments for automated tasks")
    result = models.JSONField(default=dict, blank=True, help_text="Output result of the task")
    assigned_agent = models.CharField(max_length=100, null=True, blank=True, help_text="Agent responsible for execution")
    is_automated = models.BooleanField(default=False, help_text="True if managed by Task Engine")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['priority', '-created_at']
        indexes = [
            models.Index(fields=['user_id', 'status']),
            models.Index(fields=['user_id', 'due_date']),
        ]

    def __str__(self):
        return f"Task: {self.title} [{self.status}]"


class IntelligenceFeed(models.Model):
    """
    Intelligence Feeds - Automated web monitoring catchers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    topic = models.CharField(max_length=200)
    url_pattern = models.CharField(max_length=2000, null=True, blank=True)
    frequency = models.CharField(max_length=50, default="daily") # daily, hourly
    
    is_active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user_id', 'is_active']),
        ]

    def __str__(self):
        return f"Feed: {self.topic} ({self.frequency})"


class FinancialEntry(models.Model):
    """
    Simple Ledger & Financial Tracker.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")
    
    category = models.CharField(max_length=100, help_text="e.g., travel, software, hosting")
    description = models.CharField(max_length=255)
    
    project = models.CharField(max_length=100, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['user_id', 'category']),
            models.Index(fields=['user_id', 'transaction_date']),
        ]

    def __str__(self):
        return f"{self.transaction_date}: {self.amount} {self.currency} - {self.description}"


class AgentSkill(models.Model):
    """
    Groups tools into logical skills.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField()
    tool_names = models.JSONField(default=list, help_text="List of tool names in this skill")
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class AgentPlugin(models.Model):
    """
    Packages skills into plugins.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField()
    version = models.CharField(max_length=20, default="1.0.0")
    skills = models.ManyToManyField(AgentSkill, related_name='plugins')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} (v{self.version})"


class CustomAgent(models.Model):
    """
    Defines agents with specific personas and assigned skills.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    name = models.CharField(max_length=100)
    persona = models.TextField()
    voice_profile = models.CharField(max_length=50, default="alloy")
    model_id = models.CharField(max_length=100, null=True, blank=True, help_text="Specific model override for this agent")
    
    skills = models.ManyToManyField(AgentSkill, related_name='agents')
    plugins = models.ManyToManyField(AgentPlugin, related_name='agents')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user_id', 'name')
    
    def __str__(self):
        return f"{self.name} (Role: {self.user_id})"


class Webhook(models.Model):
    """
    Manages external notification endpoints.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=100, db_index=True)
    
    name = models.CharField(max_length=100)
    url = models.URLField()
    secret = models.CharField(max_length=255, blank=True, help_text="Secret for HMAC verification")
    
    event_types = models.JSONField(default=list, help_text="List of event types to trigger on")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
