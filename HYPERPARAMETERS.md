# Supported Models and Hyperparameters

This document describes the supported machine-learning models, their default hyperparameter values, and accepted ranges.

## Classification Models

| Model | Hyperparameter | Default | Accepted values |
|---|---|---|---|
| Logistic Regression | `C` | `1.0` | 0.0001–1000.0 |
| Logistic Regression | `max_iter` | `1000` | 100–5000 |
| Decision Tree | `max_depth` | `None` | `None` or 1–100 |
| Decision Tree | `min_samples_split` | `2` | 2–100 |
| Decision Tree | `criterion` | `gini` | `gini`, `entropy`, `log_loss` |
| Random Forest | `n_estimators` | `100` | 10–500 |
| Random Forest | `max_depth` | `None` | `None` or 1–100 |
| Random Forest | `min_samples_split` | `2` | 2–100 |
| K-Nearest Neighbors | `n_neighbors` | `5` | 1–100 |
| K-Nearest Neighbors | `weights` | `uniform` | `uniform`, `distance` |
| Support Vector Machine | `C` | `1.0` | 0.0001–1000.0 |
| Support Vector Machine | `kernel` | `rbf` | `linear`, `poly`, `rbf`, `sigmoid` |

## Regression Models

| Model | Hyperparameter | Default | Accepted values |
|---|---|---|---|
| Linear Regression | `fit_intercept` | `True` | `True`, `False` |
| Decision Tree Regressor | `max_depth` | `None` | `None` or 1–100 |
| Decision Tree Regressor | `min_samples_split` | `2` | 2–100 |
| Decision Tree Regressor | `criterion` | `squared_error` | `squared_error`, `friedman_mse`, `absolute_error`, `poisson` |
| Random Forest Regressor | `n_estimators` | `100` | 10–500 |
| Random Forest Regressor | `max_depth` | `None` | `None` or 1–100 |
| Random Forest Regressor | `min_samples_split` | `2` | 2–100 |

## Validation Rules

- Unknown model names and unsupported hyperparameter names are rejected.
- Numeric values must be within the documented ranges.
- Integer parameters must contain whole numbers.
- Categorical parameters must match one of the documented choices.
- Boolean parameters accept only valid boolean values.
- Unspecified hyperparameters use their documented defaults.
- Invalid values must be rejected before the training job is queued.
- Validation errors should explain which parameter is invalid and what values are accepted.

## Implementation

The specifications and validation logic are maintained in `baseline_model.py`. Tests are maintained in `tests/test_baseline_model.py`.
