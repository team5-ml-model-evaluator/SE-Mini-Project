import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


def upload_path(instance, filename):
    # Random name in a per-user directory; the original name is kept only as text.
    return f"user-{instance.owner_id}/{instance.id}.csv"


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="datasets")
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


class RunBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="run_batches")
    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="run_batches")
    task = models.CharField(max_length=14, choices=[("classification", "Classification"), ("regression", "Regression")])
    run_config = models.JSONField()
    active = models.BooleanField(default=True)
    heartbeat_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["owner"], condition=models.Q(active=True),
                                               name="one_active_batch_per_owner")]


class Run(models.Model):
    """One training run, its persisted configuration, result and worker state.

    The heartbeat is refreshed by the supervisor while the isolated training process is alive.
    """

    QUEUED, RUNNING, COMPLETED, FAILED = "Queued", "Running", "Completed", "Failed"
    STATES = [QUEUED, RUNNING, COMPLETED, FAILED]

    job_key = models.CharField(max_length=20, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="runs")
    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT, related_name="runs")
    batch = models.ForeignKey(RunBatch, on_delete=models.SET_NULL, related_name="runs", null=True, blank=True)
    run_config = models.JSONField()
    state = models.CharField(max_length=10, default=QUEUED)
    created_at = models.DateTimeField(auto_now_add=True)
    heartbeat_at = models.DateTimeField(default=timezone.now)
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
        secs = (end - self.started_at).total_seconds()
        if 0 < secs < 0.1:
            return round(max(secs, 0.01), 2)
        return round(secs, 1)

class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError("Audit records cannot be modified.")

    def delete(self):
        raise ValueError("Audit records cannot be deleted.")


class AuditLogManager(models.Manager.from_queryset(AuditLogQuerySet)):
    pass

class AuditLog(models.Model):
    objects = AuditLogManager()

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=50)
    resource = models.CharField(max_length=255)
    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    outcome = models.CharField(max_length=20)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["timestamp"]


    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError("Audit records cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit records cannot be deleted.")

    def __str__(self):
        return f"{self.action}: {self.resource} ({self.outcome})"