"""
Admin configuration for core models.
"""
from django.contrib import admin
from core.models import ToolResponse, ToolPolicy, AuditLog, Session, PendingApproval


@admin.register(ToolResponse)
class ToolResponseAdmin(admin.ModelAdmin):
    list_display = ['tool_name', 'status', 'execution_time_ms', 'created_at']
    list_filter = ['tool_name', 'status', 'created_at']
    search_fields = ['tool_name', 'response_summary']
    readonly_fields = ['id', 'created_at', 'input_hash']
    ordering = ['-created_at']


@admin.register(ToolPolicy)
class ToolPolicyAdmin(admin.ModelAdmin):
    list_display = ['tool_name', 'rate_limit', 'requires_approval', 'enabled']
    list_filter = ['enabled', 'requires_approval']
    search_fields = ['tool_name']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'tool', 'status', 'user_id', 'created_at']
    list_filter = ['action', 'status', 'created_at']
    search_fields = ['tool', 'user_id', 'execution_id']
    readonly_fields = ['id', 'created_at']
    ordering = ['-created_at']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id', 'is_active', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user_id']
    readonly_fields = ['id', 'created_at']


@admin.register(PendingApproval)
class PendingApprovalAdmin(admin.ModelAdmin):
    list_display = ['tool_name', 'status', 'created_at', 'expires_at']
    list_filter = ['tool_name', 'status']
    readonly_fields = ['id', 'created_at']
