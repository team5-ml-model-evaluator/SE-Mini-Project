"""Baseline training workflow for supported classification and regression models."""

from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

import math


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


HYPERPARAMETER_SPECS = {
    "logistic_regression": {
        "C": {"type": "float", "default": 1.0, "min": 0.0001, "max": 1000.0},
        "max_iter": {"type": "int", "default": 1000, "min": 100, "max": 5000},
    },
    "decision_tree": {
        "max_depth": {"type": "optional_int", "default": None, "min": 1, "max": 100},
        "min_samples_split": {"type": "int", "default": 2, "min": 2, "max": 100},
        "criterion": {
            "type": "choice", "default": "gini",
            "choices": ["gini", "entropy", "log_loss"],
        },
    },
    "random_forest": {
        "n_estimators": {"type": "int", "default": 100, "min": 10, "max": 500},
        "max_depth": {"type": "optional_int", "default": None, "min": 1, "max": 100},
        "min_samples_split": {"type": "int", "default": 2, "min": 2, "max": 100},
    },
    "knn": {
        "n_neighbors": {"type": "int", "default": 5, "min": 1, "max": 100},
        "weights": {
            "type": "choice", "default": "uniform",
            "choices": ["uniform", "distance"],
        },
    },
    "svm": {
        "C": {"type": "float", "default": 1.0, "min": 0.0001, "max": 1000.0},
        "kernel": {
            "type": "choice", "default": "rbf",
            "choices": ["linear", "poly", "rbf", "sigmoid"],
        },
    },
    "linear_regression": {
        "fit_intercept": {"type": "bool", "default": True},
    },
    "decision_tree_regressor": {
        "max_depth": {"type": "optional_int", "default": None, "min": 1, "max": 100},
        "min_samples_split": {"type": "int", "default": 2, "min": 2, "max": 100},
        "criterion": {
            "type": "choice", "default": "squared_error",
            "choices": ["squared_error", "friedman_mse", "absolute_error", "poisson"],
        },
    },
    "random_forest_regressor": {
        "n_estimators": {"type": "int", "default": 100, "min": 10, "max": 500},
        "max_depth": {"type": "optional_int", "default": None, "min": 1, "max": 100},
        "min_samples_split": {"type": "int", "default": 2, "min": 2, "max": 100},
    },
}

def default_hyperparameters(model_name: str) -> dict:
    """Return the documented default hyperparameters for a model."""
    if model_name not in HYPERPARAMETER_SPECS:
        raise ValueError(f"Unsupported model '{model_name}'.")

    return {
        name: spec["default"]
        for name, spec in HYPERPARAMETER_SPECS[model_name].items()
    }


def validate_hyperparameters(
    model_name: str, hyperparameters: dict | None = None
) -> dict:
    """Validate supplied values and fill unspecified values with defaults."""
    if model_name not in HYPERPARAMETER_SPECS:
        raise ValueError(f"Unsupported model '{model_name}'.")

    if hyperparameters is not None and not isinstance(hyperparameters, dict):
        raise ValueError("Hyperparameters must be provided as a dictionary.")

    supplied = hyperparameters or {}
    specs = HYPERPARAMETER_SPECS[model_name]

    unknown = set(supplied) - set(specs)
    if unknown:
        raise ValueError(
            f"Unsupported hyperparameter(s): {', '.join(sorted(unknown))}."
        )

    values = default_hyperparameters(model_name)

    for name, raw in supplied.items():
        spec = specs[name]
        kind = spec["type"]

        if kind == "optional_int" and raw is None:
            value = None

        elif kind == "choice":
            value = raw
            if value not in spec["choices"]:
                raise ValueError(
                    f"{name} must be one of: {', '.join(spec['choices'])}."
                )

        elif kind == "bool":
            if isinstance(raw, bool):
                value = raw
            elif isinstance(raw, str) and raw.lower() in {"true", "false"}:
                value = raw.lower() == "true"
            else:
                raise ValueError(f"{name} must be true or false.")

        elif kind in {"int", "optional_int"}:
            if isinstance(raw, bool) or not str(raw).strip():
                raise ValueError(f"{name} must be an integer.")

            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be an integer.") from exc

            if str(value) != str(raw).strip():
                raise ValueError(f"{name} must be an integer.")

        else:
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a number.") from exc

            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number.")

        if value is not None and kind in {"int", "optional_int", "float"}:
            if not spec["min"] <= value <= spec["max"]:
                raise ValueError(
                    f"{name} must be between {spec['min']} and {spec['max']}."
                )

        values[name] = value

    return values



def available_models(task: str) -> list[str]:
    """Return the supported model names for a task."""
    if task == "classification":
        return list(CLASSIFICATION_MODELS)
    if task == "regression":
        return list(REGRESSION_MODELS)
    raise ValueError("task must be 'classification' or 'regression'")


def create_model(task: str, model_name: str, random_state: int = 42, hyperparameters: dict | None = None,) -> BaseEstimator:
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

    params = validate_hyperparameters(model_name , hyperparameters)

    if model_name in {
        "decision_tree" ,
        "random_forest" ,
        "decision_tree_regressor" ,
        "random_forest_regressor" ,
        "logistic_regression" ,
    }:
        params["random_state"] = random_state

    return catalogue[model_name](**params)


def run_baseline(
    task: str,
    model_name: str,
    X_train,
    y_train,
    X_test,
    random_state: int = 42,
    hyperparameters: dict | None = None ,
) -> dict:
    """Fit the selected estimator and return it with test-set predictions.

    Evaluation metrics are intentionally left to the metrics component.
    """
    model = create_model(task, model_name, random_state=random_state, hyperparameters=hyperparameters,)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)

    return {
        "task": task,
        "model_name": model_name,
        "model": model,
        "predictions": predictions,
    }
