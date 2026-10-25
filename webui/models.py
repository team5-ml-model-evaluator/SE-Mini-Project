import uuid

from django.conf import settings
from django.db import models


def upload_path(instance, filename):
    # Random name in a per-user directory; the original name is kept only as text.
    return f"user-{instance.owner_id}/{instance.id}.csv"


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="datasets")
    original_name = models.CharField(max_length=255)
    file = models.FileField(upload_to=upload_path)
    rows = models.PositiveIntegerField()
    column_count = models.PositiveIntegerField()
    profile = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_name

    @property
    def column_names(self):
        return [c["name"] for c in self.profile["columns"]]
