"""Regression and Hardening Tests for Dataset Isolation & Pipeline Edge Cases (Issue #6).

Covers all 14 isolation and robustness criteria:
1. Cross-user access to datasets (403 Forbidden).
2. Unauthorized dataset modification or deletion (401/403).
3. Unknown and malformed dataset identifiers (404 Not Found, no 500 crashes).
4. Missing or corrupted stored files (CorruptedDatasetError, safe cleanup).
5. Invalid feature or target selections (InvalidTargetError, InvalidFeatureError).
6. Empty or entirely missing columns (descriptive errors).
7. Numeric/categorical type mismatches (InvalidImputationError).
8. Invalid imputation choices (InvalidImputationError).
9. Invalid split ratios (InvalidSplitRatioError for <0.5 and >0.9).
10. Tiny datasets and insufficient rows after deletion (InsufficientRowsError).
11. Unseen categorical values (safe non-crashing encoding).
12. Repeatability across identical seeds (bitwise reproducible).
13. Zero data leakage from test to train partitions.
14. Safe failure without corrupting existing datasets or records.
"""
import io
import os
import uuid
import numpy as np
import pandas as pd
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from datasets.catalogue import delete_catalogue_dataset
from datasets.exceptions import DatasetRejected
from datasets.ownership import get_owned_dataset
from datasets.validation import validate_csv
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
from pipeline.preprocessing import prepare_data, validate_pipeline_config
from webui.models import Dataset


class DatasetIsolationAndEdgeCasesTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        # Users
        self.user_alice = User.objects.create_user(username="alice", password="alicepassword123")
        self.user_bob = User.objects.create_user(username="bob", password="bobpassword123")
        self.user_admin = User.objects.create_superuser(username="superadmin", password="adminpassword123")

        # Clients
        self.client_alice = Client()
        self.client_alice.force_login(self.user_alice)

        self.client_bob = Client()
        self.client_bob.force_login(self.user_bob)

        self.client_anon = Client()

        # Alice's dataset
        csv_alice = (
            "feature_x,feature_y,cat_col,label\n"
            + "\n".join(f"{i},{i*2},{'A' if i%2==0 else 'B'},{i%2}" for i in range(25))
        ).encode("utf-8")
        self.ds_alice = Dataset.objects.create(
            owner=self.user_alice,
            original_name="alice_data.csv",
            file=SimpleUploadedFile("alice_data.csv", csv_alice, content_type="text/csv"),
            rows=25,
            column_count=4,
            profile={"columns": [{"name": "feature_x"}, {"name": "feature_y"}, {"name": "cat_col"}, {"name": "label"}]},
        )

        # Bob's dataset
        csv_bob = (
            "col_1,col_2,col_target\n"
            + "\n".join(f"{i*10},{i*20},{i%2}" for i in range(22))
        ).encode("utf-8")
        self.ds_bob = Dataset.objects.create(
            owner=self.user_bob,
            original_name="bob_data.csv",
            file=SimpleUploadedFile("bob_data.csv", csv_bob, content_type="text/csv"),
            rows=22,
            column_count=3,
            profile={"columns": [{"name": "col_1"}, {"name": "col_2"}, {"name": "col_target"}]},
        )

    # =========================================================================
    # 1. Cross-User Access to Datasets (MLE-F-013, MLE-SR-003)
    # =========================================================================
    def test_cross_user_dataset_detail_is_403(self):
        """Alice cannot view Bob's dataset detail page."""
        resp = self.client_alice.get(reverse("dataset_detail", kwargs={"pk": self.ds_bob.id}))
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_pipeline_step_is_403(self):
        """Alice cannot access pipeline configuration for Bob's dataset."""
        resp = self.client_alice.get(reverse("pipeline_step", kwargs={"pk": self.ds_bob.id}))
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_model_step_is_403(self):
        """Alice cannot access model step for Bob's dataset."""
        resp = self.client_alice.get(reverse("model_step", kwargs={"pk": self.ds_bob.id}))
        self.assertEqual(resp.status_code, 403)

    def test_cross_user_settings_summary_is_403(self):
        """Alice cannot access settings summary for Bob's dataset."""
        resp = self.client_alice.get(reverse("settings_summary", kwargs={"pk": self.ds_bob.id}))
        self.assertEqual(resp.status_code, 403)

    def test_get_owned_dataset_raises_permission_denied_for_other_user(self):
        """get_owned_dataset raises PermissionDenied when user is not owner."""
        req = self.factory.get("/")
        req.user = self.user_alice
        with self.assertRaises(PermissionDenied):
            get_owned_dataset(req, self.ds_bob.id)

    def test_dataset_list_only_contains_own_datasets(self):
        """Alice's dataset list contains alice_data.csv and never bob_data.csv."""
        resp = self.client_alice.get(reverse("dataset_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "alice_data.csv")
        self.assertNotContains(resp, "bob_data.csv")

    # =========================================================================
    # 2. Unauthorized Dataset Modification or Deletion
    # =========================================================================
    def test_anonymous_user_redirected_to_login(self):
        """Anonymous user is redirected to login for protected endpoints."""
        for url_name, kwargs in [
            ("dataset_list", {}),
            ("dataset_new", {}),
            ("dataset_detail", {"pk": self.ds_alice.id}),
            ("pipeline_step", {"pk": self.ds_alice.id}),
        ]:
            resp = self.client_anon.get(reverse(url_name, kwargs=kwargs))
            self.assertEqual(resp.status_code, 302)
            self.assertIn("login", resp.url)

    def test_ordinary_user_cannot_delete_via_catalogue_endpoint(self):
        """Ordinary user receives 403 when trying to delete any dataset."""
        resp = self.client_alice.post(reverse("catalogue_delete", kwargs={"pk": self.ds_bob.id}))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Dataset.objects.filter(pk=self.ds_bob.id).exists())

    # =========================================================================
    # 3. Unknown and Malformed Dataset Identifiers
    # =========================================================================
    def test_unknown_uuid_returns_404(self):
        """Non-existent UUID returns 404."""
        unknown_id = uuid.uuid4()
        resp = self.client_alice.get(reverse("dataset_detail", kwargs={"pk": unknown_id}))
        self.assertEqual(resp.status_code, 404)

    def test_malformed_uuid_in_get_owned_dataset_raises_404(self):
        """Malformed UUID string raises Http404 rather than unhandled 500 error."""
        req = self.factory.get("/")
        req.user = self.user_alice
        for bad_id in ["not-a-valid-uuid", "12345", "!@#$%^&*()", ""]:
            with self.assertRaises(Http404):
                get_owned_dataset(req, bad_id)

    def test_malformed_uuid_in_catalogue_delete_raises_404(self):
        """Malformed UUID string passed to delete_catalogue_dataset raises Http404."""
        with self.assertRaises(Http404):
            delete_catalogue_dataset("not-a-uuid", user=self.user_admin)

    # =========================================================================
    # 4. Missing or Corrupted Stored Files
    # =========================================================================
    def test_missing_stored_file_raises_corrupted_dataset_error(self):
        """If dataset file is deleted from disk, prepare_data raises CorruptedDatasetError."""
        file_path = self.ds_alice.file.path
        if os.path.exists(file_path):
            os.remove(file_path)

        config = {
            "target_column": "label",
            "feature_columns": ["feature_x", "feature_y"],
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        with self.assertRaises(CorruptedDatasetError):
            prepare_data(self.ds_alice, config)

    def test_missing_stored_file_catalogue_delete_still_removes_record(self):
        """If dataset file is missing from disk, catalogue deletion removes DB record safely."""
        file_path = self.ds_bob.file.path
        if os.path.exists(file_path):
            os.remove(file_path)

        res = delete_catalogue_dataset(self.ds_bob.id, user=self.user_admin)
        self.assertTrue(res["deleted"])
        self.assertFalse(Dataset.objects.filter(pk=self.ds_bob.id).exists())

    def test_corrupted_csv_validation_rejects_binary_and_bad_encoding(self):
        """validate_csv rejects binary content and bad UTF-8."""
        binary_file = SimpleUploadedFile("bad.csv", b"\x00\x01\x02\x03\x04", content_type="text/csv")
        with self.assertRaises(DatasetRejected):
            validate_csv(binary_file)

        non_utf8 = SimpleUploadedFile("latin.csv", "name,val\nété,1".encode("latin-1"), content_type="text/csv")
        with self.assertRaises(DatasetRejected):
            validate_csv(non_utf8)

    # =========================================================================
    # 5. Invalid Feature or Target Selections
    # =========================================================================
    def test_target_not_in_dataset_raises_invalid_target_error(self):
        """Non-existent target column raises InvalidTargetError."""
        config = {
            "target_column": "non_existent_target",
            "feature_columns": ["feature_x"],
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidTargetError):
            prepare_data(self.ds_alice, config)

    def test_target_in_feature_columns_raises_invalid_target_error(self):
        """Target column included in feature_columns raises InvalidTargetError."""
        config = {
            "target_column": "label",
            "feature_columns": ["label", "feature_x"],
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidTargetError):
            validate_pipeline_config(config)

    def test_feature_not_in_dataset_raises_invalid_feature_error(self):
        """Non-existent feature column raises InvalidFeatureError."""
        config = {
            "target_column": "label",
            "feature_columns": ["feature_x", "imaginary_col"],
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidFeatureError):
            prepare_data(self.ds_alice, config)

    def test_empty_feature_columns_raises_invalid_feature_error(self):
        """Empty feature columns list raises InvalidFeatureError."""
        with self.assertRaises(InvalidFeatureError):
            validate_pipeline_config({"target_column": "label", "feature_columns": []})

    def test_all_nan_target_raises_insufficient_rows_error(self):
        """Dataset with 100% NaN target values raises InsufficientRowsError."""
        df_nan_target = pd.DataFrame({
            "feat": [1.0, 2.0, 3.0, 4.0] * 5,
            "target": [np.nan] * 20,
        })
        config = {
            "target_column": "target",
            "feature_columns": ["feat"],
            "split_ratio": 0.8,
        }
        with self.assertRaises(InsufficientRowsError):
            prepare_data(df_nan_target, config)

    # =========================================================================
    # 6. Empty or Entirely Missing Columns
    # =========================================================================
    def test_column_with_all_nan_values_fails_imputation_safely(self):
        """Column with 100% NaNs raises InvalidImputationError with descriptive message."""
        df_all_nan = pd.DataFrame({
            "feat_num": [np.nan] * 25,
            "feat_valid": list(range(25)),
            "target": [0, 1] * 12 + [0],
        })
        config = {
            "target_column": "target",
            "feature_columns": ["feat_num", "feat_valid"],
            "imputation": {"feat_num": "mean"},
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidImputationError):
            prepare_data(df_all_nan, config)

    # =========================================================================
    # 7. Numeric / Categorical Type Mismatches
    # =========================================================================
    def test_mean_imputation_on_categorical_column_raises_error(self):
        """Applying mean imputation to string column raises InvalidImputationError."""
        config = {
            "target_column": "label",
            "feature_columns": ["cat_col"],
            "imputation": {"cat_col": "mean"},
            "encoding": "one_hot",
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidImputationError):
            prepare_data(self.ds_alice, config)

    def test_median_imputation_on_categorical_column_raises_error(self):
        """Applying median imputation to string column raises InvalidImputationError."""
        config = {
            "target_column": "label",
            "feature_columns": ["cat_col"],
            "imputation": {"cat_col": "median"},
            "encoding": "one_hot",
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidImputationError):
            prepare_data(self.ds_alice, config)

    # =========================================================================
    # 8. Invalid Imputation Choices
    # =========================================================================
    def test_invalid_imputation_strategy_name_raises_error(self):
        """Unknown imputation strategy raises InvalidImputationError."""
        for bad_strat in ["random_guess", "forward_fill", "zero", 123]:
            with self.assertRaises(InvalidImputationError):
                validate_pipeline_config({
                    "target_column": "label",
                    "feature_columns": ["feature_x"],
                    "imputation": {"feature_x": bad_strat},
                })

    # =========================================================================
    # 9. Invalid Split Ratios
    # =========================================================================
    def test_invalid_split_ratios_are_rejected(self):
        """Split ratios outside [0.5, 0.9] raise InvalidSplitRatioError."""
        for bad_ratio in [0.49, 0.2, 0.0, -0.5, 0.91, 1.0, 1.5, "fifty_percent"]:
            with self.assertRaises(InvalidSplitRatioError):
                validate_pipeline_config({
                    "target_column": "label",
                    "feature_columns": ["feature_x"],
                    "split_ratio": bad_ratio,
                })

    # =========================================================================
    # 10. Tiny Datasets & Insufficient Rows After Deletion
    # =========================================================================
    def test_insufficient_rows_after_row_deletion_raises_error(self):
        """Row deletion leaving < 2 rows raises InsufficientRowsError."""
        df_sparse = pd.DataFrame({
            "col_a": [1.0, np.nan, np.nan, np.nan, np.nan] * 4,
            "target": [0, 1, 0, 1, 0] * 4,
        })
        config = {
            "target_column": "target",
            "feature_columns": ["col_a"],
            "imputation": {"col_a": "row_deletion"},
            "split_ratio": 0.8,
        }
        # Only 4 rows remain, split ratio 0.8 on 4 rows leaves 1 test row
        # If we have 2 rows with NaN, only 1 valid row remains
        df_tiny = pd.DataFrame({
            "col_a": [1.0, np.nan, np.nan],
            "target": [0, 1, 0],
        })
        with self.assertRaises(InsufficientRowsError):
            prepare_data(df_tiny, config)

    # =========================================================================
    # 11. Unseen Categorical Values
    # =========================================================================
    def test_unseen_categories_in_test_set_handled_safely(self):
        """Test partition with categories never seen in train partition transforms safely."""
        df_unseen = pd.DataFrame({
            "category": ["A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "B", "B", "B", "B", "C", "C", "NEW_CATEGORY", "ANOTHER_NEW"],
            "target": [0, 1] * 9,
        })
        # Test one-hot encoding
        config_ohe = {
            "target_column": "target",
            "feature_columns": ["category"],
            "encoding": "one_hot",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data_ohe = prepare_data(df_unseen, config_ohe)
        self.assertEqual(data_ohe.X_train.shape[1], data_ohe.X_test.shape[1])
        self.assertFalse(np.isnan(data_ohe.X_test).any())

        # Test label encoding
        config_label = {
            "target_column": "target",
            "feature_columns": ["category"],
            "encoding": "label",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        data_label = prepare_data(df_unseen, config_label)
        self.assertEqual(data_label.X_train.shape[1], data_label.X_test.shape[1])
        self.assertFalse(np.isnan(data_label.X_test).any())

    # =========================================================================
    # 12. Repeatability Across Identical Seeds
    # =========================================================================
    def test_repeatability_across_identical_seeds(self):
        """Preprocessing twice with the exact same seed returns bitwise identical outputs."""
        config = {
            "target_column": "label",
            "feature_columns": ["feature_x", "feature_y", "cat_col"],
            "imputation": {"feature_x": "mean", "feature_y": "median"},
            "encoding": "one_hot",
            "scaling": "standard",
            "split_ratio": 0.8,
            "random_seed": 9999,
        }
        run1 = prepare_data(self.ds_alice, config)
        run2 = prepare_data(self.ds_alice, config)

        self.assertEqual(run1.train_indices, run2.train_indices)
        self.assertEqual(run1.test_indices, run2.test_indices)
        np.testing.assert_array_equal(run1.X_train, run2.X_train)
        np.testing.assert_array_equal(run1.X_test, run2.X_test)
        np.testing.assert_array_equal(run1.y_train, run2.y_train)
        np.testing.assert_array_equal(run1.y_test, run2.y_test)

    # =========================================================================
    # 13. No Training / Test Preprocessing Leakage
    # =========================================================================
    def test_zero_preprocessing_leakage_from_test_into_train(self):
        """Transformers fit ONLY on train split; test distribution does not shift train parameters."""
        df_base = pd.DataFrame({
            "num": [10.0, 11.0, 12.0, 10.0, 11.0, 12.0, 10.0, 11.0, 10.0, 10.0],
            "target": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        })
        config = {
            "target_column": "target",
            "feature_columns": ["num"],
            "scaling": "standard",
            "split_ratio": 0.8,
            "random_seed": 42,
        }
        res_normal = prepare_data(df_base, config)

        # Inject extreme outlier into a row that falls in the test partition
        df_corrupted_test = df_base.copy()
        test_idx = res_normal.test_indices[0]
        df_corrupted_test.loc[test_idx, "num"] = 10_000_000.0

        res_outlier = prepare_data(df_corrupted_test, config)

        # Train statistics and matrix must be 100% IDENTICAL despite outlier in test partition
        np.testing.assert_array_equal(res_normal.X_train, res_outlier.X_train)
        self.assertEqual(res_normal.train_indices, res_outlier.train_indices)

    # =========================================================================
    # 14. Safe Failure Without Corrupting Existing Data
    # =========================================================================
    def test_safe_failure_leaves_underlying_dataset_intact(self):
        """A pipeline failure does not mutate or corrupt the original dataset file or DB record."""
        initial_file_size = self.ds_alice.file.size
        initial_rows = self.ds_alice.rows
        bad_config = {
            "target_column": "non_existent_column",
            "feature_columns": ["feature_x"],
            "split_ratio": 0.8,
        }
        with self.assertRaises(InvalidTargetError):
            prepare_data(self.ds_alice, bad_config)

        # Reload from database and verify integrity
        self.ds_alice.refresh_from_db()
        self.assertEqual(self.ds_alice.rows, initial_rows)
        self.assertEqual(self.ds_alice.file.size, initial_file_size)
