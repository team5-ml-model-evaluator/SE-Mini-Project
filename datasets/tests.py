"""Data Pipeline tests for issue #6: CSV validation, storage and ownership.

Covers the STP test cases:
  TC-DS-01  structural CSV validation rules and the message for each rejection
  TC-DS-02  a valid upload is profiled and stored; a rejection stores nothing
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

from .exceptions import DatasetRejected
from .ownership import get_owned_dataset
from .validation import validate_csv

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp(prefix="mle-ds6-test-")


def csv_bytes(header=("age", "city", "bought"), rows=25, missing=None):
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


def profile_for(content, name="data.csv"):
    return validate_csv(upload(content, name))


class ValidateCsvTests(TestCase):
    """TC-DS-01: the validator rejects bad uploads with an actionable message."""

    def test_valid_upload_returns_profile_shape(self):
        profile = validate_csv(upload(csv_bytes()))
        self.assertEqual(profile["rows"], 25)
        self.assertEqual(profile["column_count"], 3)
        self.assertEqual([c["name"] for c in profile["columns"]], ["age", "city", "bought"])
        self.assertEqual([c["dtype"] for c in profile["columns"]], ["integer", "text", "integer"])

    def test_missing_values_are_counted(self):
        age = validate_csv(upload(csv_bytes(missing={"age": 5})))["columns"][0]
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


@override_settings(MEDIA_ROOT=TMP_MEDIA, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OwnershipTests(TestCase):
    """TC-DS-02 / TC-DS-04: storage of a valid upload and server-side ownership."""

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
        profile = profile_for(content, name)
        return Dataset.objects.create(
            owner=owner,
            original_name=name,
            file=upload(content, name),
            rows=profile["rows"],
            column_count=profile["column_count"],
            profile=profile,
        )

    def _request(self, user):
        request = RequestFactory().get("/")
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

    def test_valid_upload_is_stored_and_invalid_is_not(self):
        bad = self.client.post(reverse("dataset_new"), {"file": upload(csv_bytes(rows=5))})
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(Dataset.objects.count(), 0)  # rejected uploads are never persisted
        self.client.post(reverse("dataset_new"), {"file": upload(csv_bytes(), name="customers.csv")})
        dataset = Dataset.objects.get()
        self.assertEqual((dataset.rows, dataset.column_count), (25, 3))
        self.assertEqual(dataset.file.name, f"user-{self.user.id}/{dataset.id}.csv")
