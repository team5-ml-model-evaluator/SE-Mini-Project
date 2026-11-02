"""Unit and integration tests for the Preprocessing Engine (MLE-F-020..023).

Verifies:
- TC-PP-01: Excluded columns are absent from training and test matrices.
- TC-PP-02: Missing value strategies (mean, median, mode, row deletion) match reference values.
- TC-PP-03: One-hot/label encoding and standard/min-max scaling match reference values within 1e-6.
- TC-PP-04: Seeded train/test split between 50:50 and 90:10 is deterministic and reproducible.
- Anti-leakage: Transformers fit strictly on training partitions.
- Safety: Graceful handling of unseen categories in test data.
- Validation: Descriptive error handling for malformed configs and edge cases.
"""
import io
import numpy as np
import pandas as pd
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder, OrdinalEncoder, StandardScaler

from pipeline.exceptions import (
    CorruptedDatasetError,
    DataLeakageError,
    InsufficientRowsError,
    InvalidConfigError,
    InvalidEncodingError,
    InvalidFeatureError,
    InvalidImputationError,
    InvalidScalingError,
    InvalidSplitRatioError,
    InvalidTargetError,
)
from pipeline.preprocessing import (
    PreprocessedData,
    Preprocessor,
    prepare_data,
    validate_pipeline_config,
)
from webui.models import Dataset


class PreprocessingEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testpipelineuser", password="password123")
        # Deterministic sample dataset with 24 rows
        np.random.seed(42)
        self.df = pd.DataFrame({
            "age": [20.0, 25.0, np.nan, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0] * 2,
            "salary": [30000.0, 35000.0, 40000.0, 45000.0, 50000.0, np.nan, 60000.0, 65000.0, 70000.0, 75000.0, 80000.0, 85000.0] * 2,
            "department": ["Sales", "Engineering", "Marketing", "HR", "Sales", "Engineering"] * 4,
            "notes": [f"Employee note {i}" for i in range(24)],  # will be excluded
            "purchased": [0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1] * 2,
        })

    # -------------------------------------------------------------------------
    # TC-PP-01: Excluded columns are absent from the training matrix (MLE-F-020)
    # -------------------------------------------------------------------------
    def test_tc_pp_01_excluded_columns_are_absent(self):
        """TC-PP-01: Verify that excluded columns are completely absent from the training matrix."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age", "salary"],
            "excluded_columns": ["notes", "department"],
            "imputation": {"age": "mean", "salary": "median"},
            "encoding": "none",
            "scaling": "standard",
            "split_ratio": 0.75,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        self.assertNotIn("notes", data.feature_names)
        self.assertNotIn("department", data.feature_names)
        self.assertEqual(data.feature_names, ["age", "salary"])
        self.assertEqual(data.X_train.shape[1], 2)
        self.assertEqual(data.X_test.shape[1], 2)

    # -------------------------------------------------------------------------
    # TC-PP-02: Missing-value strategies match reference implementation (MLE-F-021)
    # -------------------------------------------------------------------------
    def test_tc_pp_02_mean_imputation_matches_reference(self):
        """TC-PP-02 (mean): Mean strategy computes exact arithmetic mean on training partition."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age", "salary"],
            "imputation": {"age": "mean", "salary": "mean"},
            "encoding": "none",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        # Reference calculation on train split
        train_ages = self.df.loc[data.train_indices, "age"]
        expected_mean = float(train_ages.dropna().mean())
        self.assertAlmostEqual(data.metadata["imputers"]["age"]["fill_value"], expected_mean, places=6)
        self.assertFalse(np.isnan(data.X_train).any())
        self.assertFalse(np.isnan(data.X_test).any())

    def test_tc_pp_02_median_imputation_matches_reference(self):
        """TC-PP-02 (median): Median strategy computes exact median on training partition."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age", "salary"],
            "imputation": {"age": "median", "salary": "median"},
            "encoding": "none",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        train_salaries = self.df.loc[data.train_indices, "salary"]
        expected_median = float(train_salaries.dropna().median())
        self.assertAlmostEqual(data.metadata["imputers"]["salary"]["fill_value"], expected_median, places=6)
        self.assertFalse(np.isnan(data.X_train).any())
        self.assertFalse(np.isnan(data.X_test).any())

    def test_tc_pp_02_mode_imputation_matches_reference(self):
        """TC-PP-02 (mode): Mode strategy computes most frequent value on training partition."""
        df_mode = self.df.copy()
        df_mode.loc[0:3, "department"] = np.nan
        config = {
            "target_column": "purchased",
            "feature_columns": ["department"],
            "imputation": {"department": "mode"},
            "encoding": "label",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(df_mode, config)

        train_depts = df_mode.loc[data.train_indices, "department"].dropna()
        expected_mode = train_depts.mode().iloc[0]
        self.assertEqual(data.metadata["imputers"]["department"]["fill_value"], expected_mode)
        self.assertFalse(np.isnan(data.X_train).any())

    def test_tc_pp_02_row_deletion_drops_na_rows(self):
        """TC-PP-02 (row deletion): Rows with missing values in specified columns are dropped."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age", "salary"],
            "imputation": {"age": "row_deletion", "salary": "row_deletion"},
            "encoding": "none",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        expected_rows = len(self.df.dropna(subset=["age", "salary", "purchased"]))
        total_output_rows = len(data.X_train) + len(data.X_test)
        self.assertEqual(total_output_rows, expected_rows)
        self.assertFalse(np.isnan(data.X_train).any())
        self.assertFalse(np.isnan(data.X_test).any())

    # -------------------------------------------------------------------------
    # TC-PP-03: Encoded and scaled output matches reference values within 1e-6 (MLE-F-022)
    # -------------------------------------------------------------------------
    def test_tc_pp_03_standard_scaler_matches_reference(self):
        """TC-PP-03 (StandardScaler): Output matches sklearn reference within 1e-6."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age"],
            "imputation": {"age": "mean"},
            "encoding": "none",
            "scaling": "standard",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        # Reference StandardScaler fitted on imputed X_train
        mean_val = float(self.df.loc[data.train_indices, "age"].dropna().mean())
        raw_train = self.df.loc[data.train_indices, ["age"]].fillna(mean_val).to_numpy()
        raw_test = self.df.loc[data.test_indices, ["age"]].fillna(mean_val).to_numpy()

        ref_scaler = StandardScaler()
        ref_train_scaled = ref_scaler.fit_transform(raw_train)
        ref_test_scaled = ref_scaler.transform(raw_test)

        np.testing.assert_allclose(data.X_train, ref_train_scaled, atol=1e-6)
        np.testing.assert_allclose(data.X_test, ref_test_scaled, atol=1e-6)
        self.assertAlmostEqual(float(data.X_train.mean()), 0.0, places=5)
        self.assertAlmostEqual(float(data.X_train.std()), 1.0, places=5)

    def test_tc_pp_03_min_max_scaler_matches_reference(self):
        """TC-PP-03 (MinMaxScaler): Output matches sklearn reference within 1e-6."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age"],
            "imputation": {"age": "median"},
            "encoding": "none",
            "scaling": "minmax",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        med_val = float(self.df.loc[data.train_indices, "age"].dropna().median())
        raw_train = self.df.loc[data.train_indices, ["age"]].fillna(med_val).to_numpy()
        raw_test = self.df.loc[data.test_indices, ["age"]].fillna(med_val).to_numpy()

        ref_scaler = MinMaxScaler()
        ref_train_scaled = ref_scaler.fit_transform(raw_train)
        ref_test_scaled = ref_scaler.transform(raw_test)

        np.testing.assert_allclose(data.X_train, ref_train_scaled, atol=1e-6)
        np.testing.assert_allclose(data.X_test, ref_test_scaled, atol=1e-6)
        self.assertAlmostEqual(float(data.X_train.min()), 0.0, places=6)
        self.assertAlmostEqual(float(data.X_train.max()), 1.0, places=6)

    def test_tc_pp_03_one_hot_encoding_matches_reference(self):
        """TC-PP-03 (OneHot): One-hot encoding matches sklearn reference within 1e-6."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["department"],
            "imputation": {},
            "encoding": "one_hot",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        raw_train = self.df.loc[data.train_indices, ["department"]].astype(str)
        raw_test = self.df.loc[data.test_indices, ["department"]].astype(str)

        ref_ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        ref_train = ref_ohe.fit_transform(raw_train)
        ref_test = ref_ohe.transform(raw_test)

        np.testing.assert_allclose(data.X_train, ref_train, atol=1e-6)
        np.testing.assert_allclose(data.X_test, ref_test, atol=1e-6)

    def test_tc_pp_03_label_encoding_matches_reference(self):
        """TC-PP-03 (Label): Label/ordinal encoding matches sklearn reference within 1e-6."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["department"],
            "imputation": {},
            "encoding": "label",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(self.df, config)

        raw_train = self.df.loc[data.train_indices, ["department"]].astype(str)
        raw_test = self.df.loc[data.test_indices, ["department"]].astype(str)

        ref_enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        ref_train = ref_enc.fit_transform(raw_train)
        ref_test = ref_enc.transform(raw_test)

        np.testing.assert_allclose(data.X_train, ref_train, atol=1e-6)
        np.testing.assert_allclose(data.X_test, ref_test, atol=1e-6)

    # -------------------------------------------------------------------------
    # TC-PP-04: Seeded train/test split between 50:50 and 90:10 (MLE-F-023)
    # -------------------------------------------------------------------------
    def test_tc_pp_04_seeded_split_reproducibility(self):
        """TC-PP-04: Re-running with the exact same seed reproduces an identical split."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["age", "department"],
            "imputation": {"age": "mean"},
            "encoding": "one_hot",
            "scaling": "standard",
            "split_ratio": 0.8,
            "random_seed": 12345,
        }
        run1 = prepare_data(self.df, config)
        run2 = prepare_data(self.df, config)

        self.assertEqual(run1.train_indices, run2.train_indices)
        self.assertEqual(run1.test_indices, run2.test_indices)
        np.testing.assert_array_equal(run1.X_train, run2.X_train)
        np.testing.assert_array_equal(run1.X_test, run2.X_test)
        np.testing.assert_array_equal(run1.y_train, run2.y_train)
        np.testing.assert_array_equal(run1.y_test, run2.y_test)

    def test_tc_pp_04_different_seeds_produce_different_splits(self):
        """TC-PP-04: Different seeds produce different splits."""
        config1 = {
            "target_column": "purchased",
            "feature_columns": ["age"],
            "imputation": {"age": "mean"},
            "encoding": "none",
            "scaling": "none",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        config2 = dict(config1, random_seed=999)
        run1 = prepare_data(self.df, config1)
        run2 = prepare_data(self.df, config2)

        self.assertNotEqual(run1.train_indices, run2.train_indices)

    def test_tc_pp_04_split_ratio_boundary_50_50_and_90_10(self):
        """TC-PP-04: Ratios 0.5 (50:50) and 0.9 (90:10) are valid and respected."""
        for ratio in (0.5, 0.9):
            config = {
                "target_column": "purchased",
                "feature_columns": ["age"],
                "imputation": {"age": "mean"},
                "encoding": "none",
                "scaling": "none",
                "split_ratio": ratio,
                "random_seed": 42,
            }
            data = prepare_data(self.df, config)
            total = len(data.X_train) + len(data.X_test)
            self.assertEqual(total, len(self.df))
            actual_train_ratio = len(data.X_train) / total
            self.assertAlmostEqual(actual_train_ratio, ratio, delta=0.05)

    # -------------------------------------------------------------------------
    # Anti-Leakage & Safety Tests
    # -------------------------------------------------------------------------
    def test_no_data_leakage_transformers_fit_strictly_on_train(self):
        """Verify that transformers compute statistics ONLY on training data."""
        # Create dataset with an extreme outlier in test partition
        df_leak = pd.DataFrame({
            "val": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 1000000.0, 1000000.0],
            "target": [0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
        })
        # Use split where rows 0-7 are train and 8-9 (outliers) are test
        config = {
            "target_column": "target",
            "feature_columns": ["val"],
            "imputation": {"val": "mean"},
            "encoding": "none",
            "scaling": "standard",
            "split_ratio": 0.8,
            "random_seed": 0,
        }
        data = prepare_data(df_leak, config)
        train_raw = df_leak.loc[data.train_indices, "val"]
        expected_train_mean = float(train_raw.mean())

        # If leakage occurred, the scaler mean would include the 1000000.0 values from test
        preprocessor = Preprocessor(config)
        preprocessor.fit_transform(df_leak)
        self.assertAlmostEqual(preprocessor.scaler.mean_[0], expected_train_mean, places=5)

    def test_unseen_categories_in_test_handled_gracefully(self):
        """Unseen categories in test partition do not crash and encode safely."""
        df_unseen = pd.DataFrame({
            "city": ["Paris", "Paris", "Paris", "London", "London", "London", "Tokyo", "Tokyo"],
            "target": [1, 0, 1, 0, 1, 0, 1, 0],
        })
        config = {
            "target_column": "target",
            "feature_columns": ["city"],
            "encoding": "one_hot",
            "scaling": "none",
            "split_ratio": 0.75,
            "random_seed": 42,
        }
        data = prepare_data(df_unseen, config)
        # Test set contains rows transformed safely without exception
        self.assertEqual(data.X_train.shape[1], data.X_test.shape[1])
        self.assertFalse(np.isnan(data.X_test).any())

    # -------------------------------------------------------------------------
    # Validation & Error Handling
    # -------------------------------------------------------------------------
    def test_invalid_split_ratio_raises_error(self):
        """Split ratios below 0.5 or above 0.9 raise InvalidSplitRatioError."""
        for invalid_ratio in (0.49, 0.95, -0.1, 1.5, "invalid"):
            with self.assertRaises(InvalidSplitRatioError):
                validate_pipeline_config({
                    "target_column": "target",
                    "feature_columns": ["age"],
                    "split_ratio": invalid_ratio,
                })

    def test_target_in_feature_columns_raises_error(self):
        """Nominating target as a feature raises InvalidTargetError."""
        with self.assertRaises(InvalidTargetError):
            validate_pipeline_config({
                "target_column": "target",
                "feature_columns": ["target", "age"],
            })

    def test_empty_feature_columns_raises_error(self):
        """Empty feature list raises InvalidFeatureError."""
        with self.assertRaises(InvalidFeatureError):
            validate_pipeline_config({
                "target_column": "target",
                "feature_columns": [],
            })

    def test_unknown_imputation_strategy_raises_error(self):
        """Unrecognized imputation strategy raises InvalidImputationError."""
        with self.assertRaises(InvalidImputationError):
            validate_pipeline_config({
                "target_column": "target",
                "feature_columns": ["age"],
                "imputation": {"age": "magic_fill"},
            })

    def test_mean_imputation_on_text_column_raises_error(self):
        """Applying mean imputation to non-numeric column raises InvalidImputationError."""
        config = {
            "target_column": "purchased",
            "feature_columns": ["department"],
            "imputation": {"department": "mean"},
            "encoding": "one_hot",
            "scaling": "none",
        }
        with self.assertRaises(InvalidImputationError):
            prepare_data(self.df, config)

    def test_django_dataset_instance_input(self):
        """prepare_data works directly with a Django Dataset model instance."""
        csv_content = self.df.to_csv(index=False).encode("utf-8")
        uploaded = SimpleUploadedFile("sample.csv", csv_content, content_type="text/csv")
        dataset = Dataset.objects.create(
            owner=self.user,
            original_name="sample.csv",
            file=uploaded,
            rows=len(self.df),
            column_count=len(self.df.columns),
            profile={},
        )
        config = {
            "target_column": "purchased",
            "feature_columns": ["age", "salary"],
            "imputation": {"age": "mean", "salary": "median"},
            "encoding": "none",
            "scaling": "standard",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data = prepare_data(dataset, config)
        self.assertIsInstance(data, PreprocessedData)
        self.assertEqual(data.target_name, "purchased")
        self.assertEqual(len(data.X_train) + len(data.X_test), len(self.df))
