import numpy as np
import pytest
from sklearn.datasets import load_diabetes, load_iris
from sklearn.model_selection import train_test_split

from baseline_model import available_models, create_model, run_baseline, HYPERPARAMETER_SPECS, default_hyperparameters, validate_hyperparameters


CLASSIFICATION_MODELS = [
    "logistic_regression",
    "decision_tree",
    "random_forest",
    "knn",
    "svm",
]
REGRESSION_MODELS = [
    "linear_regression",
    "decision_tree_regressor",
    "random_forest_regressor",
]


def test_lists_all_required_classification_models():
    assert set(available_models("classification")) == set(CLASSIFICATION_MODELS)


def test_lists_all_required_regression_models():
    assert set(available_models("regression")) == set(REGRESSION_MODELS)


def test_rejects_unknown_task():
    with pytest.raises(ValueError, match="task must be"):
        available_models("clustering")


def test_rejects_unknown_model():
    with pytest.raises(ValueError, match="Unsupported classification model"):
        create_model("classification", "made_up_model")


def test_rejects_regression_model_for_classification_task():
    with pytest.raises(ValueError, match="Unsupported classification model"):
        create_model("classification", "linear_regression")


@pytest.mark.parametrize("model_name", CLASSIFICATION_MODELS)
def test_classification_model_trains_and_predicts(model_name):
    """Each supported classifier must fit and return valid test predictions."""
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
    predictions = np.asarray(result["predictions"])

    assert result["task"] == "classification"
    assert result["model_name"] == model_name
    assert result["model"] is not None
    assert hasattr(result["model"], "n_features_in_")  # fitted estimator
    assert predictions.shape == (len(X_test),)
    assert np.isfinite(predictions).all()
    assert set(np.unique(predictions)).issubset(set(dataset.target))


@pytest.mark.parametrize("model_name", REGRESSION_MODELS)
def test_regression_model_trains_and_predicts(model_name):
    """Each supported regressor must fit and return finite test predictions."""
    dataset = load_diabetes()
    X_train, X_test, y_train, _ = train_test_split(
        dataset.data,
        dataset.target,
        test_size=0.25,
        random_state=42,
    )

    result = run_baseline("regression", model_name, X_train, y_train, X_test)
    predictions = np.asarray(result["predictions"])

    assert result["task"] == "regression"
    assert result["model_name"] == model_name
    assert result["model"] is not None
    assert hasattr(result["model"], "n_features_in_")  # fitted estimator
    assert predictions.shape == (len(X_test),)
    assert np.isfinite(predictions).all()


def test_catalogue_has_hyperparameter_specs_for_all_models():
    assert set(HYPERPARAMETER_SPECS) == (
        set(CLASSIFICATION_MODELS) | set(REGRESSION_MODELS)
    )


@pytest.mark.parametrize(
    "model_name",
    CLASSIFICATION_MODELS + REGRESSION_MODELS,
)
def test_default_hyperparameters_are_valid(model_name):
    defaults = default_hyperparameters(model_name)
    assert validate_hyperparameters(model_name, defaults) == defaults


def test_valid_custom_random_forest_parameters():
    params = validate_hyperparameters(
        "random_forest",
        {"n_estimators": 150, "max_depth": 12},
    )
    assert params["n_estimators"] == 150
    assert params["max_depth"] == 12
    assert params["min_samples_split"] == 2


def test_custom_parameters_reach_model():
    model = create_model(
        "classification",
        "random_forest",
        hyperparameters={"n_estimators": 150, "max_depth": 12},
    )
    assert model.n_estimators == 150
    assert model.max_depth == 12


@pytest.mark.parametrize(
    ("model_name", "params"),
    [
        ("random_forest", {"n_estimators": 0}),
        ("knn", {"n_neighbors": 101}),
        ("logistic_regression", {"C": -1}),
        ("decision_tree", {"criterion": "invalid"}),
        ("svm", {"unknown_parameter": 1}),
        ("linear_regression", {"fit_intercept": "maybe"}),
        ("random_forest", {"n_estimators": 2.5}),
    ],
)
def test_invalid_hyperparameters_are_rejected(model_name, params):
    with pytest.raises(ValueError):
        validate_hyperparameters(model_name, params)


def test_unknown_model_has_no_hyperparameter_defaults():
    with pytest.raises(ValueError, match="Unsupported model"):
        default_hyperparameters("unknown_model")
