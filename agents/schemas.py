"""
App Specification Schema - Pydantic models for dynamic app generation.
"""
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class FieldType(str, Enum):
    """Supported Django field types."""
    STRING = "CharField"
    TEXT = "TextField"
    INTEGER = "IntegerField"
    FLOAT = "FloatField"
    BOOLEAN = "BooleanField"
    DATE = "DateField"
    DATETIME = "DateTimeField"
    EMAIL = "EmailField"
    URL = "URLField"
    FILE = "FileField"
    IMAGE = "ImageField"
    JSON = "JSONField"
    UUID = "UUIDField"
    FOREIGN_KEY = "ForeignKey"
    MANY_TO_MANY = "ManyToManyField"


class FieldSpec(BaseModel):
    """Specification for a model field."""
    name: str = Field(description="Field name in snake_case")
    field_type: FieldType = Field(description="Django field type")
    required: bool = Field(default=True)
    max_length: Optional[int] = Field(default=None, description="For CharField")
    related_model: Optional[str] = Field(default=None, description="For FK/M2M")
    default: Optional[str] = Field(default=None)
    help_text: Optional[str] = Field(default=None)
    choices: Optional[list[tuple[str, str]]] = Field(default=None)


class EntitySpec(BaseModel):
    """Specification for a Django model."""
    name: str = Field(description="Model name in PascalCase")
    description: str = Field(description="What this entity represents")
    fields: list[FieldSpec] = Field(default_factory=list)
    
    # Auto-generated fields
    include_timestamps: bool = Field(default=True, description="Add created_at/updated_at")
    include_uuid: bool = Field(default=True, description="Use UUID primary key")


class ToolSpec(BaseModel):
    """Specification for an @agent_tool function."""
    name: str = Field(description="Tool name in snake_case")
    description: str = Field(description="Tool description for LLM")
    entity: str = Field(description="Related entity name")
    operation: str = Field(description="create, read, update, delete, search, or custom")
    requires_approval: bool = Field(default=False)
    secrets: list[str] = Field(default_factory=list)


class IntegrationSpec(BaseModel):
    """Specification for external integrations."""
    name: str = Field(description="Integration name")
    provider: str = Field(description="API provider (e.g., google, docusign)")
    required_secrets: list[str] = Field(default_factory=list)
    endpoints_needed: list[str] = Field(default_factory=list)


class WorkflowSpec(BaseModel):
    """Specification for automated workflows."""
    name: str = Field(description="Workflow name")
    trigger: str = Field(description="What triggers this workflow")
    steps: list[str] = Field(description="Steps to execute")
    cron_schedule: Optional[str] = Field(default=None, description="Cron expression if scheduled")


class AppSpec(BaseModel):
    """Complete specification for generating a domain-specific Django app."""
    name: str = Field(description="App name in snake_case (e.g., 'legal')")
    display_name: str = Field(description="Human-readable name (e.g., 'Legal Practice Manager')")
    description: str = Field(description="App description")
    
    # Core components
    entities: list[EntitySpec] = Field(default_factory=list)
    tools: list[ToolSpec] = Field(default_factory=list)
    
    # Optional components
    integrations: list[IntegrationSpec] = Field(default_factory=list)
    workflows: list[WorkflowSpec] = Field(default_factory=list)
    
    # Libraries to install
    pip_dependencies: list[str] = Field(default_factory=list)
    
    def get_app_path(self, base_dir: str) -> str:
        """Get the path where this app should be created."""
        from pathlib import Path
        return str(Path(base_dir) / "apps" / self.name)


class DomainSpec(BaseModel):
    """Domain analysis result from user description."""
    domain_name: str = Field(description="Identified domain (e.g., 'legal', 'healthcare')")
    key_entities: list[str] = Field(description="Main entities in this domain")
    key_workflows: list[str] = Field(description="Common workflows")
    suggested_integrations: list[str] = Field(description="Useful integrations")
    
    # Research hints for Research Agent
    search_queries: list[str] = Field(description="Queries to find APIs/libraries")
