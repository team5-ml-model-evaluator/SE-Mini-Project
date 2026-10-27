"""Baseline training workflow for supported classification and regression models."""

from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


CLASSIFICATION_MODELS = {
    "logistic_regression": LogisticRegression,
    "decision_tree": DecisionTreeClassifier,
    "random_forest": RandomForestClassifier,
    "knn": KNeighborsClassifier,
    "svm": SVC,
}

REGRESSION_MODELS = {
    "linear_regression": LinearRegression,
    "decision_tree_regressor": DecisionTreeRegressor,
    "random_forest_regressor": RandomForestRegressor,
}


def available_models(task: str) -> list[str]:
    """Return the supported model names for a task."""
    if task == "classification":
        return list(CLASSIFICATION_MODELS)
    if task == "regression":
        return list(REGRESSION_MODELS)
    raise ValueError("task must be 'classification' or 'regression'")


def create_model(task: str, model_name: str, random_state: int = 42) -> BaseEstimator:
    """Create a fresh estimator for the requested task and model."""
    if task == "classification":
        catalogue = CLASSIFICATION_MODELS
    elif task == "regression":
        catalogue = REGRESSION_MODELS
    else:
        raise ValueError("task must be 'classification' or 'regression'")

    if model_name not in catalogue:
        supported = ", ".join(catalogue)
        raise ValueError(
            f"Unsupported {task} model '{model_name}'. Supported models: {supported}"
        )

    model_class = catalogue[model_name]
    # Pass deterministic random_state only to estimators that support it.
    if model_name in {
        "decision_tree",
        "random_forest",
        "decision_tree_regressor",
        "random_forest_regressor",
    }:
        return model_class(random_state=random_state)
    if model_name == "logistic_regression":
        return model_class(max_iter=1000, random_state=random_state)
    return model_class()


def run_baseline(
    task: str,
    model_name: str,
    X_train,
    y_train,
    X_test,
    random_state: int = 42,
) -> dict:
    """Fit the selected estimator and return it with test-set predictions.

    Evaluation metrics are intentionally left to the metrics component.
    """
    model = create_model(task, model_name, random_state=random_state)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    return {
        "task": task,
        "model_name": model_name,
        "model": model,
        "predictions": predictions,
    }
