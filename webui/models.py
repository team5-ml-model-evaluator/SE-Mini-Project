import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


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


class Run(models.Model):
    """One training run and its state.

    STAND-IN: RunsApp owns this record in the SAD (TrainingJob). The WebUI only reads it.
    The fields match the status interface: job_key, state, started_at, elapsed_s, error.
    """

    QUEUED, RUNNING, COMPLETED, FAILED = "Queued", "Running", "Completed", "Failed"
    STATES = [QUEUED, RUNNING, COMPLETED, FAILED]

    job_key = models.CharField(max_length=20, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="runs")
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="runs")
    run_config = models.JSONField()
    state = models.CharField(max_length=10, default=QUEUED)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    result = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.job_key

    @property
    def elapsed_s(self):
        """Seconds since the run started; None while it is still queued."""
        if self.started_at is None:
            return None
        end = self.finished_at or timezone.now()
        return round((end - self.started_at).total_seconds(), 1)
