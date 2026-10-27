"""Integration tests using golden fixtures with the project's #12 and #13 APIs.

These tests intentionally import the production modules rather than testing
scikit-learn estimators/metrics in isolation. They run once baseline_model.py
and evaluation_metrics.py are present in the branch (after PRs #12 and #13
are merged or their changes are integrated).
"""
import numpy as np
import pytest

from baseline_model import run_baseline
from evaluation_metrics import (
    calculate_classification_metrics,
    calculate_regression_metrics,
)


def test_golden_classification_runs_through_model_and_evaluation(
    classification_data,
):
    X, y = classification_data
    result = run_baseline(
        "classification",
        "decision_tree",
        X,
        y,
        X,
        random_state=42,
    )

    assert result["task"] == "classification"
    assert result["model_name"] == "decision_tree"
    assert len(result["predictions"]) == len(y)

    metrics = calculate_classification_metrics(
        y.tolist(), np.asarray(result["predictions"]).tolist()
    )
    assert metrics["accuracy"] == pytest.approx(1.0, abs=1e-6)
    assert metrics["confusion_matrix"] == [[2, 0], [0, 4]]


def test_golden_regression_runs_through_model_and_evaluation(
    regression_data,
):
    X, y = regression_data
    result = run_baseline(
        "regression",
        "linear_regression",
        X,
        y,
        X,
        random_state=42,
    )

    assert result["task"] == "regression"
    assert result["model_name"] == "linear_regression"
    assert len(result["predictions"]) == len(y)

    metrics = calculate_regression_metrics(
        y.tolist(), np.asarray(result["predictions"]).tolist()
    )
    assert metrics["mae"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["mse"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["rmse"] == pytest.approx(0.0, abs=1e-6)
    assert metrics["r2"] == pytest.approx(1.0, abs=1e-6)


def test_classification_metric_output_is_json_friendly():
    result = calculate_classification_metrics(
        [0, 1, 1, 0],
        [0, 1, 0, 0],
    )

    assert isinstance(result["accuracy"], float)
    assert isinstance(result["precision"], float)
    assert isinstance(result["recall"], float)
    assert isinstance(result["f1_score"], float)
    assert isinstance(result["confusion_matrix"], list)


def test_regression_metric_output_is_json_friendly():
    result = calculate_regression_metrics(
        [3.0, -0.5, 2.0, 7.0],
        [2.5, 0.0, 2.0, 8.0],
    )

    for metric in ("mae", "mse", "rmse", "r2"):
        assert isinstance(result[metric], float)
