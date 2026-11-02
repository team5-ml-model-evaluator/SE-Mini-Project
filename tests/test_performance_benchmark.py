
"""NFR benchmark: 50,000 rows x 30 columns, five repetitions."""

import statistics
import time

import pytest
from sklearn.model_selection import train_test_split

from baseline_model import run_baseline


@pytest.mark.performance
def test_reference_model_performance(performance_dataset):
    X = performance_dataset.drop(columns=["target"])
    y = performance_dataset["target"]

    X_train, X_test, y_train, _ = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    execution_times = []

    for run_number in range(1, 6):
        start_time = time.perf_counter()

        run_baseline(
            "classification",
            "random_forest",
            X_train,
            y_train,
            X_test,
            random_state=42,
        )

        elapsed = time.perf_counter() - start_time
        execution_times.append(elapsed)

        print(
            f"Run {run_number}: {elapsed:.2f} seconds"
        )

    median_time = statistics.median(execution_times)

    print(f"\nExecution times: {execution_times}")
    print(f"Median execution time: {median_time:.2f} seconds")
    print(f"Requirement: <= 120 seconds")

    assert median_time <= 120, (
        f"Performance requirement failed: "
        f"median was {median_time:.2f} seconds"
    )
