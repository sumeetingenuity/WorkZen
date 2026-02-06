from django.contrib import admin
from .models import Client, Case, Document, Contract, CourtDate, Invoice


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("name", "email", "phone", "address", "notes")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "status", "court_date", "created_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "created_at", "updated_at")
    list_filter = ("document_type", "created_at", "updated_at")
    search_fields = ("title", "notes")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("title", "signed", "signed_at", "created_at")
    list_filter = ("signed", "created_at", "updated_at")
    search_fields = ("title", "template", "generated_text")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CourtDate)
class CourtDateAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("id", "created_at", "updated_at")
