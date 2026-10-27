
from django.contrib import admin

from .models import TrainingJob


@admin.register(TrainingJob)
class TrainingJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "dataset_name",
        "model_name",
        "status",
        "created_at",
    )

    list_filter = ("status", "created_at")
    search_fields = ("dataset_name", "model_name", "user__username")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "started_at",
        "finished_at",
    )
    ordering = ("-created_at",)
