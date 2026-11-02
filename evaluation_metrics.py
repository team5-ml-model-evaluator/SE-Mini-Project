
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


def calculate_classification_metrics(y_true, y_pred, labels=None):
    """Calculate standard classification evaluation metrics."""
    if len(y_true) == 0 or len(y_pred) == 0:
        raise ValueError("Actual and predicted values cannot be empty.")

    if len(y_true) != len(y_pred):
        raise ValueError(
            "Actual and predicted values must have equal lengths."
        )

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
        ),
        "recall": float(
            recall_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
        ),
        "f1_score": float(
            f1_score(
                y_true, y_pred, average="weighted", zero_division=0
            )
        ),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


def calculate_regression_metrics(y_true, y_pred):
    """Calculate standard regression evaluation metrics."""
    if len(y_true) == 0 or len(y_pred) == 0:
        raise ValueError("Actual and predicted values cannot be empty.")

    if len(y_true) != len(y_pred):
        raise ValueError(
            "Actual and predicted values must have equal lengths."
        )

    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "mse": float(mean_squared_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }
