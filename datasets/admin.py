from django.contrib import admin

from webui.models import Dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ("original_name", "owner", "rows", "column_count", "created_at")
    list_filter = ("created_at", "owner")
    search_fields = ("original_name", "owner__username")
    readonly_fields = ("id", "created_at")
