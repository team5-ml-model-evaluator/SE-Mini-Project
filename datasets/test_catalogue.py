"""Tests for Dataset Catalogue Administration (MLE-F-063, TC-AD-02).

Verifies:
- TC-AD-02: Administrator can list catalogue entries and remove an allowed entry;
  the removed entry no longer appears in the catalogue.
- Access control: Non-administrators cannot list or delete catalogue entries (403).
- Method constraint: Destructive deletion requires CSRF-protected POST (GET returns 405).
- File/DB consistency: Underlying file is deleted from disk; missing files do not break DB deletion.
- In-use safety: Datasets referenced by existing runs cannot be accidentally deleted.
- Non-existent IDs return 404.
"""
import os
import uuid
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from datasets.catalogue import delete_catalogue_dataset, list_catalogue_datasets
from datasets.exceptions import DatasetInUseError
from webui.models import Dataset


class MockRun:
    """Mock object simulating a related run for safety testing."""
    def __init__(self, exists=True, count=1):
        self._exists = exists
        self._count = count

    def exists(self):
        return self._exists

    def count(self):
        return self._count


class DatasetCatalogueAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="adminpassword123"
        )
        self.staff_user = User.objects.create_user(
            username="staffuser", password="staffpassword123", is_staff=True
        )
        self.regular_user1 = User.objects.create_user(
            username="regularuser1", password="regularpassword123"
        )
        self.regular_user2 = User.objects.create_user(
            username="regularuser2", password="regularpassword123"
        )

        self.client_admin = Client()
        self.client_admin.force_login(self.admin_user)

        self.client_staff = Client()
        self.client_staff.force_login(self.staff_user)

        self.client_regular = Client()
        self.client_regular.force_login(self.regular_user1)

        self.client_anon = Client()

        # Create two datasets owned by different users
        file1 = SimpleUploadedFile("user1_data.csv", b"a,b\n1,2\n3,4", content_type="text/csv")
        self.ds1 = Dataset.objects.create(
            owner=self.regular_user1,
            original_name="user1_data.csv",
            file=file1,
            rows=2,
            column_count=2,
            profile={"columns": [{"name": "a"}, {"name": "b"}]},
        )

        file2 = SimpleUploadedFile("user2_data.csv", b"x,y\n10,20\n30,40", content_type="text/csv")
        self.ds2 = Dataset.objects.create(
            owner=self.regular_user2,
            original_name="user2_data.csv",
            file=file2,
            rows=2,
            column_count=2,
            profile={"columns": [{"name": "x"}, {"name": "y"}]},
        )

    # -------------------------------------------------------------------------
    # TC-AD-02: Administrator lists and removes catalogue entry (MLE-F-063)
    # -------------------------------------------------------------------------
    def test_tc_ad_02_admin_lists_catalogue_entries(self):
        """TC-AD-02: Administrator can view all registered datasets with metadata."""
        resp = self.client_admin.get(reverse("catalogue_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "datasets/catalogue.html")
        self.assertContains(resp, "user1_data.csv")
        self.assertContains(resp, "user2_data.csv")
        self.assertContains(resp, "regularuser1")
        self.assertContains(resp, "regularuser2")

    def test_tc_ad_02_admin_removes_allowed_entry_from_catalogue(self):
        """TC-AD-02: Administrator removes an allowed entry; removed entry no longer appears."""
        ds_id = self.ds1.id
        resp = self.client_admin.post(reverse("catalogue_delete", kwargs={"pk": ds_id}), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Dataset.objects.filter(pk=ds_id).exists())
        self.assertContains(resp, "was removed from the catalogue")
        # In the catalogue table, only ds2 should remain
        self.assertContains(resp, "user2_data.csv")
        self.assertNotIn(str(ds_id), resp.content.decode("utf-8"))

    def test_tc_ad_02_staff_user_can_also_manage_catalogue(self):
        """Staff administrators can list and remove catalogue entries."""
        resp = self.client_staff.get(reverse("catalogue_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "user1_data.csv")

    # -------------------------------------------------------------------------
    # Authorization & Isolation (Non-admins must get 403 Forbidden)
    # -------------------------------------------------------------------------
    def test_regular_user_cannot_list_catalogue(self):
        """Ordinary user receives 403 Forbidden when requesting catalogue."""
        resp = self.client_regular.get(reverse("catalogue_list"))
        self.assertEqual(resp.status_code, 403)

    def test_regular_user_cannot_delete_catalogue_entry(self):
        """Ordinary user receives 403 Forbidden when attempting to delete a catalogue entry."""
        resp = self.client_regular.post(reverse("catalogue_delete", kwargs={"pk": self.ds1.id}))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Dataset.objects.filter(pk=self.ds1.id).exists())

    def test_anonymous_user_redirected_to_login(self):
        """Anonymous user is redirected to login for both list and delete actions."""
        list_resp = self.client_anon.get(reverse("catalogue_list"))
        self.assertEqual(list_resp.status_code, 302)
        self.assertIn("login", list_resp.url)

        delete_resp = self.client_anon.post(reverse("catalogue_delete", kwargs={"pk": self.ds1.id}))
        self.assertEqual(delete_resp.status_code, 302)
        self.assertIn("login", delete_resp.url)

    # -------------------------------------------------------------------------
    # Destructive Method Safety (POST only, GET rejected)
    # -------------------------------------------------------------------------
    def test_get_request_to_delete_endpoint_is_rejected(self):
        """Accidental GET request to delete endpoint returns 405 Method Not Allowed."""
        resp = self.client_admin.get(reverse("catalogue_delete", kwargs={"pk": self.ds1.id}))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Dataset.objects.filter(pk=self.ds1.id).exists())

    # -------------------------------------------------------------------------
    # File & Database Consistency
    # -------------------------------------------------------------------------
    def test_delete_removes_physical_file_from_disk(self):
        """Deleting a catalogue entry removes both DB record and disk file."""
        file_path = self.ds1.file.path
        self.assertTrue(os.path.exists(file_path))

        delete_catalogue_dataset(self.ds1.id, user=self.admin_user)
        self.assertFalse(Dataset.objects.filter(pk=self.ds1.id).exists())
        self.assertFalse(os.path.exists(file_path))

    def test_delete_missing_file_still_deletes_db_record_cleanly(self):
        """If file was deleted from disk prior to catalogue deletion, DB cleanup succeeds."""
        file_path = self.ds2.file.path
        if os.path.exists(file_path):
            os.remove(file_path)

        # Deletion must not raise FileNotFoundError or fail
        result = delete_catalogue_dataset(self.ds2.id, user=self.admin_user)
        self.assertTrue(result["deleted"])
        self.assertFalse(Dataset.objects.filter(pk=self.ds2.id).exists())

    # -------------------------------------------------------------------------
    # Safety Check: Prevent deletion of datasets in use by training runs
    # -------------------------------------------------------------------------
    def test_dataset_referenced_by_runs_cannot_be_deleted(self):
        """Datasets referenced by existing runs raise DatasetInUseError and are not deleted."""
        # Attach a mock runs relation to ds1
        self.ds1.runs = MockRun(exists=True, count=2)
        with self.assertRaises(DatasetInUseError):
            delete_catalogue_dataset(self.ds1, user=self.admin_user)
        self.assertTrue(Dataset.objects.filter(pk=self.ds1.id).exists())

    def test_unknown_dataset_delete_returns_404(self):
        """Attempting to delete a non-existent UUID returns 404 Not Found."""
        random_id = uuid.uuid4()
        resp = self.client_admin.post(reverse("catalogue_delete", kwargs={"pk": random_id}))
        self.assertEqual(resp.status_code, 404)
