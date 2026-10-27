# Baseline Model Execution

Small Python component for the `Implement baseline model execution` task.

## Scope

- Supports five classification estimators and three regression estimators.
- Creates a model from a task/model name.
- Fits it on training data and predicts on test data.
- Leaves evaluation metrics to the separate metrics component.

## Setup

Use Python 3.10 or newer.

```bash
python -m venv .venv
```

Activate the environment, then install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Run the tests

```bash
python -m pytest -q
```

## Example

```python
from sklearn.datasets import load_iris
from sklearn.model_selection import train_test_split
from baseline_model import run_baseline

data = load_iris()
X_train, X_test, y_train, _ = train_test_split(
    data.data, data.target, test_size=0.25, random_state=42, stratify=data.target
)

result = run_baseline(
    "classification", "random_forest", X_train, y_train, X_test
)
print(result["predictions"])
```

## Supported model names

Classification: `logistic_regression`, `decision_tree`, `random_forest`, `knn`, `svm`

Regression: `linear_regression`, `decision_tree_regressor`, `random_forest_regressor`

## Integration note

This is a starter implementation for the baseline-execution task. Coordinate the
function signature and returned values with teammates implementing the model
catalogue, metrics, UI, and security/audit components before merging.
