"""Data Pipeline tests for issues #6 (validation/ownership) and #7 (profiling).

Covers the STP test cases:
  TC-DS-01  structural CSV validation rules and the message for each rejection
  TC-DS-02  an invalid upload is never persisted; a valid one is profiled/stored
  TC-DS-03  profiling: dtype inference (integer/decimal/text) and missing counts
  TC-DS-04  ownership: 404 unknown, 403 for another user, login required
"""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from webui.models import Dataset

from . import profiling
from .exceptions import DatasetRejected
from .ownership import get_owned_dataset
from .validation import validate_csv

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp(prefix="mle-ds-test-")


def csv_bytes(header=("age", "city", "bought"), rows=25, missing=None):
    """Build a small, well-formed CSV body (numeric/text/mixed by default)."""
    missing = missing or {}
    lines = [",".join(header)]
    for i in range(rows):
        values = {
            "age": "" if missing.get("age") and i % missing["age"] == 0 else str(20 + i),
            "city": "" if missing.get("city") and i % missing["city"] == 0 else f"City{i % 3}",
            "bought": "" if missing.get("bought") and i % missing["bought"] == 0 else str(i % 2),
        }
        lines.append(",".join(values.get(c, f"v{i}") for c in header))
    return ("\n".join(lines) + "\n").encode()


def upload(content, name="data.csv"):
    return SimpleUploadedFile(name, content)


@override_settings(MEDIA_ROOT=TMP_MEDIA, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class DatasetsTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw")
        self.other = User.objects.create_user("bob", password="pw")
        self.client.force_login(self.user)

    def store_dataset(self, owner=None, content=None, name="data.csv"):
        owner = owner or self.user
        content = content if content is not None else csv_bytes()
        profile = validate_csv(upload(content, name))
        return Dataset.objects.create(
            owner=owner,
            original_name=name,
            file=upload(content, name),
            rows=profile["rows"],
            column_count=profile["column_count"],
            profile=profile,
        )


class ValidateCsvTests(DatasetsTestCase):
    """TC-DS-01 / TC-DS-03: the validator and the profile it returns."""

    def test_valid_upload_returns_profile_shape(self):
        profile = validate_csv(upload(csv_bytes()))
        self.assertEqual(profile["rows"], 25)
        self.assertEqual(profile["column_count"], 3)
        self.assertEqual([c["name"] for c in profile["columns"]], ["age", "city", "bought"])
        self.assertEqual([c["dtype"] for c in profile["columns"]], ["integer", "text", "integer"])

    def test_missing_values_are_counted(self):
        profile = validate_csv(upload(csv_bytes(missing={"age": 5})))
        age = profile["columns"][0]
        self.assertEqual(age["dtype"], "integer")
        self.assertEqual(age["missing_count"], 5)
        self.assertEqual(age["missing_pct"], 20.0)

    def test_not_a_csv(self):
        with self.assertRaises(DatasetRejected) as ctx:
            validate_csv(upload(csv_bytes(), name="data.txt"))
        self.assertIn("name ends in .csv", str(ctx.exception))

    def test_binary_rejected(self):
        with self.assertRaises(DatasetRejected) as ctx:
            validate_csv(upload(b"MZ\x00\x00" * 40))
        self.assertIn("binary data", str(ctx.exception))

    def test_non_utf8_rejected(self):
        with self.assertRaises(DatasetRejected) as ctx:
            validate_csv(upload(b"a,b\n" + "é,1\n".encode("latin-1") * 25))
        self.assertIn("UTF-8", str(ctx.exception))

    def test_too_few_rows(self):
        with self.assertRaises(DatasetRejected) as ctx:
            validate_csv(upload(csv_bytes(rows=19)))
        self.assertIn("19 data rows", str(ctx.exception))

    def test_too_few_columns(self):
        with self.assertRaises(DatasetRejected) as ctx:
            validate_csv(upload(csv_bytes(header=("only",), rows=25)))
        self.assertIn("1 column", str(ctx.exception))

    def test_duplicate_and_blank_headers(self):
        with self.assertRaises(DatasetRejected):
            validate_csv(upload(b"a,a\n" + b"1,2\n" * 25))
        with self.assertRaises(DatasetRejected):
            validate_csv(upload(b"a,\n" + b"1,2\n" * 25))

    def test_uneven_row_names_the_row(self):
        with self.assertRaises(DatasetRejected) as ctx:
            validate_csv(upload(csv_bytes() + b"1,2\n"))
        self.assertIn("Row 27 has 2 values", str(ctx.exception))

    def test_size_limit_states_limit_and_size(self):
        content = csv_bytes()
        with override_settings(MAX_UPLOAD_BYTES=len(content) - 1):
            with self.assertRaises(DatasetRejected) as ctx:
                validate_csv(upload(content))
            self.assertIn("the limit is 0 MB", str(ctx.exception))


class ProfilingServiceTests(DatasetsTestCase):
    """TC-DS-03: the profiling service consumed by upload and preprocessing."""

    def test_profile_text_dtype_inference(self):
        text = "n,d,t\n1,1.5,x\n2,,y\n3,2.5,z\n"
        profile = profiling.profile_text(text)
        dtypes = [c["dtype"] for c in profile["columns"]]
        self.assertEqual(dtypes, ["integer", "decimal", "text"])
        self.assertEqual(profile["rows"], 3)

    def test_profile_text_ignores_missing_tokens_for_dtype(self):
        profile = profiling.profile_text("a,b\n1,NA\n2,\n3,n/a\n")
        by_name = {c["name"]: c for c in profile["columns"]}
        self.assertEqual(by_name["a"]["dtype"], "integer")
        self.assertEqual(by_name["a"]["missing_count"], 0)
        self.assertEqual(by_name["b"]["missing_count"], 3)

    def test_load_dataframe_returns_typed_frame(self):
        dataset = self.store_dataset(content=b"a,b\n" + b"1,2\n" * 20)
        df = profiling.load_dataframe(dataset)
        self.assertEqual(list(df.columns), ["a", "b"])
        self.assertTrue(df["a"].dtype.kind in "iuf", df["a"].dtype)  # numeric, not all-string

    def test_load_dataframe_missing_file_raises(self):
        dataset = self.store_dataset()
        dataset.file.delete()
        with self.assertRaises(profiling.ProfileError):
            profiling.load_dataframe(dataset)


class OwnershipTests(DatasetsTestCase):
    """TC-DS-04: server-side ownership checks."""

    def _request(self, user):
        rf = RequestFactory()
        request = rf.get("/")
        request.user = user
        return request

    def test_owner_gets_their_dataset(self):
        dataset = self.store_dataset(owner=self.user)
        self.assertEqual(get_owned_dataset(self._request(self.user), dataset.pk), dataset)

    def test_other_user_is_forbidden(self):
        dataset = self.store_dataset(owner=self.user)
        with self.assertRaises(PermissionDenied):
            get_owned_dataset(self._request(self.other), dataset.pk)

    def test_unknown_id_is_404(self):
        with self.assertRaises(Http404):
            get_owned_dataset(self._request(self.user), "00000000-0000-0000-0000-000000000000")

    def test_cross_user_is_403_through_the_view(self):
        dataset = self.store_dataset(owner=self.user)
        bob = Client()
        bob.force_login(self.other)
        self.assertEqual(bob.get(reverse("dataset_detail", args=[dataset.pk])).status_code, 403)

    def test_unknown_dataset_is_404_through_the_view(self):
        response = self.client.get(reverse("dataset_detail", args=["00000000-0000-0000-0000-000000000000"]))
        self.assertEqual(response.status_code, 404)
