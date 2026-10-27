import numpy as np
import pytest
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

from evaluation_metrics import (
    calculate_classification_metrics,
    calculate_regression_metrics,
)


TOLERANCE = 1e-6


def test_classification_metrics_match_sklearn():
    actual = [0, 1, 1, 0, 1]
    predicted = [0, 1, 0, 0, 1]

    result = calculate_classification_metrics(actual, predicted)

    assert abs(result["accuracy"] - accuracy_score(actual, predicted)) <= TOLERANCE
    assert abs(
        result["precision"] - precision_score(
            actual, predicted, average="weighted", zero_division=0
        )
    ) <= TOLERANCE
    assert abs(
        result["recall"] - recall_score(
            actual, predicted, average="weighted", zero_division=0
        )
    ) <= TOLERANCE
    assert abs(
        result["f1_score"] - f1_score(
            actual, predicted, average="weighted", zero_division=0
        )
    ) <= TOLERANCE
    assert result["confusion_matrix"] == confusion_matrix(
        actual, predicted
    ).tolist()


def test_regression_metrics_match_sklearn():
    actual = [3.0, -0.5, 2.0, 7.0]
    predicted = [2.5, 0.0, 2.0, 8.0]

    result = calculate_regression_metrics(actual, predicted)

    assert abs(result["mae"] - mean_absolute_error(actual, predicted)) <= TOLERANCE
    assert abs(result["mse"] - mean_squared_error(actual, predicted)) <= TOLERANCE
    assert abs(
        result["rmse"] - mean_squared_error(actual, predicted) ** 0.5
    ) <= TOLERANCE
    assert abs(result["r2"] - r2_score(actual, predicted)) <= TOLERANCE


@pytest.mark.parametrize(
    "function",
    [calculate_classification_metrics, calculate_regression_metrics],
)
def test_metrics_reject_empty_inputs(function):
    with pytest.raises(ValueError, match="cannot be empty"):
        function([], [])


@pytest.mark.parametrize(
    ("function", "actual", "predicted"),
    [
        (calculate_classification_metrics, [0, 1], [0]),
        (calculate_regression_metrics, [1.0, 2.0], [1.0]),
    ],
)
def test_metrics_reject_mismatched_lengths(function, actual, predicted):
    with pytest.raises(ValueError, match="equal lengths"):
        function(actual, predicted)
