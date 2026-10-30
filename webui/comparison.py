"""Read-only presentation of stored evaluation results (MLE-F-052).

Kept separate from training and views so reports/CSV can use the same values.
"""
import math
from decimal import Decimal

from django.core.exceptions import ValidationError

from .matrices import matrix_window
from .models import Run
from .standins.catalogue import BY_KEY


METRICS = {
    "classification": [("accuracy", "Accuracy"), ("precision", "Precision"),
                       ("recall", "Recall"), ("f1_score", "F1-score")],
    "regression": [("mae", "MAE"), ("mse", "MSE"), ("rmse", "RMSE"), ("r2", "R²")],
}


def format_metric(task, value):
    number = Decimal(str(value))
    return f"{number * 100:.2f}%" if task == "classification" else f"{number:.2f}"


def describe_run(run):
    """Validate one stored completed result for comparisons and reports."""
    if run.state != Run.COMPLETED:
        raise ValidationError("Reports are available only for completed runs.")
    config, result = run.run_config, run.result
    invalid = "One or more selected runs have incomplete or invalid evaluation results. Choose other runs."
    if not isinstance(config, dict) or not isinstance(result, dict):
        raise ValidationError(invalid)
    algorithm_key = config.get("algorithm")
    algorithm = BY_KEY.get(algorithm_key) if isinstance(algorithm_key, str) else None
    task = result.get("task")
    target = config.get("target_column")
    if (algorithm is None or task != algorithm.task
            or not isinstance(target, str) or not target):
        raise ValidationError(invalid)
    for key, _ in METRICS[task]:
        value = result.get(key)
        try:
            valid = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValidationError(invalid)

    matrix_rows = []
    labels = []
    matrix_preview = None
    if task == "classification":
        labels, matrix = result.get("labels"), result.get("confusion_matrix")
        if (not isinstance(labels, list) or not labels or not isinstance(matrix, list)
                or len(matrix) != len(labels)):
            raise ValidationError(invalid)
        for label, row in zip(labels, matrix):
            if (not isinstance(label, str) or not isinstance(row, list) or len(row) != len(labels)
                    or any(type(value) is not int or value < 0 for value in row)):
                raise ValidationError(invalid)
        matrix_preview = matrix_window(result)
        labels, matrix_rows = matrix_preview["labels"], matrix_preview["rows"]
    return {"run": run, "algorithm": algorithm, "target": target,
                    "task": task, "labels": labels, "matrix_rows": matrix_rows,
                    "matrix_preview": matrix_preview}


def build_comparison(selected_runs):
    """Validate compatibility and return columns/rows without rounding stored metrics."""
    runs = list(selected_runs)
    if len({run.pk for run in runs}) < 2:
        raise ValidationError("Select at least two different completed runs to compare.")
    if any(run.state != Run.COMPLETED for run in runs):
        raise ValidationError("Choose only completed runs to compare.")
    if len({run.dataset_id for run in runs}) != 1:
        raise ValidationError("Choose runs from the same dataset.")

    columns = [describe_run(run) for run in runs]

    if len({column["target"] for column in columns}) != 1:
        raise ValidationError("Choose runs with the same target column.")
    if len({column["task"] for column in columns}) != 1:
        raise ValidationError("Choose runs with the same task type (classification or regression).")
    task = columns[0]["task"]
    return {
        "columns": columns, "task": task, "target": columns[0]["target"],
        "rows": [{"key": key, "label": label, "values": [str(run.result[key]) for run in runs],
                  "display_values": [format_metric(task, run.result[key]) for run in runs]}
                 for key, label in METRICS[task]],
    }
