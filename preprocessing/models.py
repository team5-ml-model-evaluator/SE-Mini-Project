from django.conf import settings
from django.db import models

from webui.models import Dataset


class MissingStrategy(models.TextChoices):
    """Per-column missing-value handling options (MLE-F-021)."""

    MEAN = "mean", "Mean"
    MEDIAN = "median", "Median"
    MODE = "mode", "Mode"
    DELETE = "delete", "Delete row"


class PreprocessingConfig(models.Model):
    """Stored target/feature + missing-value configuration for a dataset.

    Persisted (MLE-F-020/021) so later ML/training components can reconstruct
    the same feature matrix, target vector and imputation plan.
    """

    dataset = models.ForeignKey(
        Dataset,
        on_delete=models.CASCADE,
        related_name="preprocessing_configs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="preprocessing_configs",
    )
    target_column = models.CharField(max_length=255)
    feature_columns = models.JSONField(default=list)
    excluded_columns = models.JSONField(default=list)
    # {column_name: strategy} for the columns actually in play (target + features).
    missing_strategies = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PreprocessingConfig(dataset={self.dataset_id}, target={self.target_column})"
