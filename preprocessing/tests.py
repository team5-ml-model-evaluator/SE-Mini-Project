"""Data Pipeline tests for issue #8: target/feature selection and missing values.

Covers the STP test cases:
  TC-PP-01  the feature matrix X and target vector y are built correctly and
            safely (no target leakage, the source frame is never mutated)
  TC-PP-02  missing-value strategies (mean/median/mode/delete) fill as expected
            using training statistics only, and bad selections are refused
"""
import shutil
import tempfile

import pandas as pd
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from webui.models import Dataset

from .exceptions import PreprocessingError
from .models import PreprocessingConfig
from .service import Preprocessor, validate_selection

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp(prefix="mle-pp-test-")


def frame():
    return pd.DataFrame(
        {
            "age": [30, 40, None, 20, 50, 60, 25, 35, 45, 55],
            "city": ["a", "b", "a", "b", "a", "b", "a", "b", "a", "b"],
            "score": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
            "bought": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
        }
    )


class SelectionTests(TestCase):
    def test_target_is_never_a_feature(self):
        with self.assertRaises(PreprocessingError):
            validate_selection(["a", "b", "c"], "a", ["a", "b"])

    def test_at_least_one_feature(self):
        with self.assertRaises(PreprocessingError):
            validate_selection(["a", "b"], "a", [])

    def test_unknown_feature_rejected(self):
        with self.assertRaises(PreprocessingError):
            validate_selection(["a", "b"], "a", ["z"])

    def test_excluded_is_everything_else(self):
        features, excluded = validate_selection(["a", "b", "c", "d"], "d", ["a", "b"])
        self.assertEqual(features, ["a", "b"])
        self.assertEqual(excluded, ["c"])


class BuildFeatureMatrixTests(TestCase):
    """TC-PP-01: shape, ordering and safety of the X/y split."""

    def test_x_has_features_y_has_target_and_alignment(self):
        pre = Preprocessor(frame(), "bought", ["age", "city"])
        X, y = pre.fit_transform(frame())
        self.assertEqual(list(X.columns), ["age", "city"])
        self.assertNotIn("bought", X.columns)
        self.assertEqual(len(X), len(y))
        self.assertEqual(y.tolist(), [0, 1, 0, 1, 0, 1, 0, 1, 0, 1])

    def test_source_frame_is_not_mutated(self):
        source = frame()
        before = source.copy()
        Preprocessor(source, "bought", ["age", "city"]).fit_transform(source)
        pd.testing.assert_frame_equal(source, before)

    def test_must_fit_before_transform(self):
        pre = Preprocessor(frame(), "bought", ["age"])
        with self.assertRaises(PreprocessingError):
            pre.transform(frame())


class MissingValueTests(TestCase):
    """TC-PP-02: imputation strategies and their guard rails."""

    def test_mean_uses_training_statistics_only(self):
        source = frame()
        # A missing training value and a missing held-out value in 'score'.
        source.loc[0, "score"] = float("nan")
        source.loc[8, "score"] = float("nan")
        train = source.iloc[:8]
        test = source.iloc[8:]
        pre = Preprocessor(source, "bought", ["age", "score"], {"score": "mean"})
        pre.fit(train)
        X, _ = pre.transform(test)
        expected = train["score"].dropna().mean()  # 5.0 from the train rows only
        self.assertAlmostEqual(X.loc[8, "score"], expected)
        self.assertNotAlmostEqual(X.loc[8, "score"], 10.0)  # not filled from test data

    def test_median_and_mode_fill(self):
        source = frame()
        source.loc[0, "age"] = float("nan")
        source.loc[1, "city"] = float("nan")
        pre = Preprocessor(source, "bought", ["age", "city"], {"age": "median", "city": "mode"})
        X, _ = pre.fit_transform(source)
        self.assertFalse(X["age"].isna().any())
        self.assertFalse(X["city"].isna().any())

    def test_delete_drops_missing_rows(self):
        source = frame()
        source.loc[2, "age"] = float("nan")
        pre = Preprocessor(source, "bought", ["age", "score"], {"age": "delete"})
        X, y = pre.fit_transform(source)
        self.assertEqual(len(X), len(source) - 1)
        self.assertNotIn(2, list(X.index))

    def test_mean_on_text_column_is_rejected(self):
        pre = Preprocessor(frame(), "bought", ["age", "city"], {"city": "mean"})
        with self.assertRaises(PreprocessingError):
            pre.fit(frame())

    def test_all_missing_column_is_rejected(self):
        source = frame()
        source["age"] = float("nan")
        pre = Preprocessor(source, "bought", ["age"], {"age": "mean"})
        with self.assertRaises(PreprocessingError):
            pre.fit(source)

    def test_missing_target_after_preprocessing_is_rejected(self):
        source = frame()
        source.loc[0, "bought"] = float("nan")
        pre = Preprocessor(source, "bought", ["age", "score"])  # no strategy for the target
        with self.assertRaises(PreprocessingError):
            pre.fit_transform(source)

    def test_delete_leaving_no_rows_is_rejected(self):
        source = frame()
        source["age"] = float("nan")
        pre = Preprocessor(source, "bought", ["age"], {"age": "delete"})
        with self.assertRaises(PreprocessingError):
            pre.fit_transform(source)


@override_settings(MEDIA_ROOT=TMP_MEDIA, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ConfigureViewTests(TestCase):
    """The preprocessing step over HTTP: auth, ownership, persistence."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.other = User.objects.create_user("bob", password="pw")
        self.client.force_login(self.user)
        content = b"age,city,score,bought\n" + b"".join(
            b"%d,City%d,%d,%d\n" % (20 + i, i % 3, 10 + i, i % 2) for i in range(22)
        )
        profile = {"rows": 22, "column_count": 4, "columns": [
            {"name": "age", "dtype": "integer", "missing_count": 0, "missing_pct": 0.0},
            {"name": "city", "dtype": "text", "missing_count": 0, "missing_pct": 0.0},
            {"name": "score", "dtype": "integer", "missing_count": 0, "missing_pct": 0.0},
            {"name": "bought", "dtype": "integer", "missing_count": 0, "missing_pct": 0.0},
        ]}
        self.dataset = Dataset.objects.create(
            owner=self.user,
            original_name="data.csv",
            file=SimpleUploadedFile("data.csv", content),
            rows=22,
            column_count=4,
            profile=profile,
        )
        self.url = reverse("preprocessing_configure", args=[self.dataset.pk])

    def test_login_is_required(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_cross_user_is_403(self):
        bob = self.client_class()
        bob.force_login(self.other)
        self.assertEqual(bob.get(self.url).status_code, 403)

    def test_unknown_dataset_is_404(self):
        self.assertEqual(self.client.get(reverse("preprocessing_configure", args=["00000000-0000-0000-0000-000000000000"])).status_code, 404)

    def _post(self, target="bought", features=("age", "city", "score"), strategies=None):
        strategies = strategies or {}
        columns = ["age", "city", "score", "bought"]
        data = {"target": target}
        data["features"] = [f for f in features]
        for i, col in enumerate(columns):
            data[f"strategy_{i}"] = strategies.get(col, "")
        return self.client.post(self.url, data)

    def test_valid_post_saves_config_and_previews(self):
        response = self._post(target="bought", features=("age", "score"), strategies={"score": "mean"})
        self.assertEqual(response.status_code, 200)
        config = PreprocessingConfig.objects.get()
        self.assertEqual(config.target_column, "bought")
        self.assertEqual(config.feature_columns, ["age", "score"])
        self.assertEqual(config.excluded_columns, ["city"])
        self.assertEqual(config.missing_strategies, {"score": "mean"})
        self.assertContains(response, "Feature matrix preview")

    def test_no_features_is_rejected_and_not_persisted(self):
        response = self._post(target="bought", features=())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "feature")  # the form explains what is wrong
        self.assertEqual(PreprocessingConfig.objects.count(), 0)
