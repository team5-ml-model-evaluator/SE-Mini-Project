
import pytest
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from evaluation_metrics import (
    calculate_classification_metrics,
    calculate_regression_metrics,
)


def test_classification_metrics_match_sklearn():
    actual = [0, 1, 1, 0, 1]
    predicted = [0, 1, 0, 0, 1]

    result = calculate_classification_metrics(actual, predicted)

    assert abs(result["accuracy"] - accuracy_score(
        actual, predicted
    )) <= 1e-6

    assert result["confusion_matrix"] == [[2, 0], [1, 2]]
    assert 0 <= result["precision"] <= 1
    assert 0 <= result["recall"] <= 1
    assert 0 <= result["f1_score"] <= 1


def test_regression_metrics_match_sklearn():
    actual = [3.0, -0.5, 2.0, 7.0]
    predicted = [2.5, 0.0, 2.0, 8.0]

    result = calculate_regression_metrics(actual, predicted)

    assert abs(result["mae"] - mean_absolute_error(
        actual, predicted
    )) <= 1e-6

    assert abs(result["mse"] - mean_squared_error(
        actual, predicted
    )) <= 1e-6

    assert abs(result["rmse"] - mean_squared_error(
        actual, predicted
    ) ** 0.5) <= 1e-6

    assert abs(result["r2"] - r2_score(
        actual, predicted
    )) <= 1e-6


def test_classification_rejects_empty_inputs():
    with pytest.raises(ValueError):
        calculate_classification_metrics([], [])


def test_regression_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        calculate_regression_metrics([1, 2], [1])


def test_regression_rejects_empty_inputs():
    with pytest.raises(ValueError):
        calculate_regression_metrics([], [])
