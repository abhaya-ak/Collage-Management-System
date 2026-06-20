"""Read-only admin for AuditLog (records must never be edited or deleted)."""

from django.contrib import admin

from apps.core.audit import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "model_name", "object_id", "actor")
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("model_name", "object_id", "object_repr", "action")
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
