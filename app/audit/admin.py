from django.contrib import admin

from .models import SecurityAuditLog


@admin.register(SecurityAuditLog)
class SecurityAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "actor",
        "resource_type",
        "resource_id",
        "target_user",
        "created_at",
    )
    list_filter = ("event_type", "resource_type")
    readonly_fields = (
        "actor",
        "event_type",
        "resource_type",
        "resource_id",
        "target_user",
        "metadata_json",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
