
from pathlib import Path

import pandas as pd
import pytest


TEST_DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture
def classification_frame():
    """Load a deterministic binary-classification dataset."""
    return pd.read_csv(TEST_DATA_DIR / "classification_golden.csv")


@pytest.fixture
def regression_frame():
    """Load a deterministic regression dataset."""
    return pd.read_csv(TEST_DATA_DIR / "regression_golden.csv")


@pytest.fixture
def classification_data(classification_frame):
    """Provide features and target for classification tests."""
    return (
        classification_frame.drop(columns=["target"]),
        classification_frame["target"],
    )


@pytest.fixture
def regression_data(regression_frame):
    """Provide features and target for regression tests."""
    return (
        regression_frame.drop(columns=["target"]),
        regression_frame["target"],
    )


@pytest.fixture
def preprocessing_data():
    """Provide fixed input and expected output for median imputation."""
    return {
        "X": [[1.0, float("nan")], [3.0, 4.0], [5.0, 6.0]],
        "expected_imputed": [
            [1.0, 5.0],
            [3.0, 4.0],
            [5.0, 6.0],
        ],
    }


@pytest.fixture
def performance_dataset():
    """Generate the SRS reference dataset: 50,000 rows and 30 columns."""
    import numpy as np

    rng = np.random.default_rng(42)
    X = rng.normal(size=(50_000, 29))
    target = (X[:, 0] + X[:, 1] > 0).astype(int)
    data = np.column_stack([X, target])

    columns = [f"feature_{i}" for i in range(29)] + ["target"]
    return pd.DataFrame(data, columns=columns)
