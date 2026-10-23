import numpy as np
import pytest
from sklearn.datasets import load_diabetes, load_iris
from sklearn.model_selection import train_test_split

from baseline_model import available_models, create_model, run_baseline


def test_lists_all_required_classification_models():
    assert set(available_models("classification")) == {
        "logistic_regression",
        "decision_tree",
        "random_forest",
        "knn",
        "svm",
    }


def test_lists_all_required_regression_models():
    assert set(available_models("regression")) == {
        "linear_regression",
        "decision_tree_regressor",
        "random_forest_regressor",
    }


def test_rejects_unknown_task():
    with pytest.raises(ValueError, match="task must be"):
        available_models("clustering")


def test_rejects_unknown_model():
    with pytest.raises(ValueError, match="Unsupported classification model"):
        create_model("classification", "made_up_model")


@pytest.mark.parametrize(
    "model_name",
    [
        "logistic_regression",
        "decision_tree",
        "random_forest",
        "knn",
        "svm",
    ],
)
def test_classification_model_runs(model_name):
    dataset = load_iris()
    X_train, X_test, y_train, _ = train_test_split(
        dataset.data,
        dataset.target,
        test_size=0.25,
        random_state=42,
        stratify=dataset.target,
    )

    result = run_baseline(
        "classification", model_name, X_train, y_train, X_test
    )

    assert result["model_name"] == model_name
    assert len(result["predictions"]) == len(X_test)
    assert set(np.unique(result["predictions"])).issubset(set(dataset.target))


@pytest.mark.parametrize(
    "model_name",
    [
        "linear_regression",
        "decision_tree_regressor",
        "random_forest_regressor",
    ],
)
def test_regression_model_runs(model_name):
    dataset = load_diabetes()
    X_train, X_test, y_train, _ = train_test_split(
        dataset.data,
        dataset.target,
        test_size=0.25,
        random_state=42,
    )

    result = run_baseline("regression", model_name, X_train, y_train, X_test)

    assert result["model_name"] == model_name
    assert len(result["predictions"]) == len(X_test)
    assert np.isfinite(result["predictions"]).all()
