
import numpy as np
import pytest
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


def test_classification_fixture_shape(classification_frame):
    assert classification_frame.shape == (6, 3)
    assert list(classification_frame.columns) == [
        "feature_1", "feature_2", "target"
    ]
    assert set(classification_frame["target"]) == {0, 1}


def test_regression_fixture_shape(regression_frame):
    assert regression_frame.shape == (6, 3)
    assert list(regression_frame.columns) == [
        "feature_1", "feature_2", "target"
    ]
    assert regression_frame["target"].tolist() == [
        1.0, 3.0, 5.0, 7.0, 9.0, 11.0
    ]


def test_classification_golden_metrics():
    y_true = [0, 1, 1, 0]
    y_pred = [0, 1, 0, 0]

    assert accuracy_score(y_true, y_pred) == pytest.approx(0.75)
    assert precision_score(
        y_true, y_pred, average="weighted", zero_division=0
    ) == pytest.approx(5 / 6, abs=1e-6)
    assert recall_score(
        y_true, y_pred, average="weighted", zero_division=0
    ) == pytest.approx(0.75)
    assert f1_score(
        y_true, y_pred, average="weighted", zero_division=0
    ) == pytest.approx(11 / 15, abs=1e-6)
    assert confusion_matrix(y_true, y_pred).tolist() == [
        [2, 0],
        [1, 1],
    ]


def test_regression_golden_metrics():
    y_true = [3.0, -0.5, 2.0, 7.0]
    y_pred = [2.5, 0.0, 2.0, 8.0]

    assert mean_absolute_error(y_true, y_pred) == pytest.approx(0.5)
    assert mean_squared_error(y_true, y_pred) == pytest.approx(0.375)
    assert mean_squared_error(y_true, y_pred) ** 0.5 == pytest.approx(
        0.6123724356957945, abs=1e-6
    )
    assert r2_score(y_true, y_pred) == pytest.approx(
        0.9486081370449679, abs=1e-6
    )


def test_median_imputation_matches_golden_output(preprocessing_data):
    imputer = SimpleImputer(strategy="median")
    actual = imputer.fit_transform(preprocessing_data["X"])

    np.testing.assert_allclose(
        actual,
        preprocessing_data["expected_imputed"],
        atol=1e-6,
    )


def test_standard_scaler_has_expected_properties():
    X = np.array([[1.0], [2.0], [3.0]])
    transformed = StandardScaler().fit_transform(X)

    assert transformed.mean() == pytest.approx(0.0, abs=1e-6)
    assert transformed.std() == pytest.approx(1.0, abs=1e-6)


def test_regression_fixture_has_known_linear_relationship(regression_data):
    X, y = regression_data
    model = LinearRegression().fit(X, y)
    predictions = model.predict(X)

    np.testing.assert_allclose(predictions, y, atol=1e-6)


def test_seeded_train_test_split_is_reproducible(classification_data):
    X, y = classification_data

    first = train_test_split(
        X, y, test_size=0.33, random_state=42
    )
    second = train_test_split(
        X, y, test_size=0.33, random_state=42
    )

    for first_part, second_part in zip(first, second):
        np.testing.assert_array_equal(
            np.asarray(first_part), np.asarray(second_part)
        )


def test_performance_fixture_dimensions(performance_dataset):
    assert performance_dataset.shape == (50_000, 30)
    assert performance_dataset.isna().sum().sum() == 0
