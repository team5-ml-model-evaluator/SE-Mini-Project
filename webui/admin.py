from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("actor", "action", "resource", "timestamp", "outcome")
    list_filter = ("action", "outcome", "timestamp")
    search_fields = ("resource", "action")
    readonly_fields = (
        "actor",
        "action",
        "resource",
        "timestamp",
        "outcome",
        "details",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False