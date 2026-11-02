from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from jobs.models import TrainingJob
from .models import AuditLog, Dataset, Run, RunBatch


User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AdministratorManagementTests(TestCase):
    def setUp(self):
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin = User.objects.create_user(
            username="site_admin", password="Admin-test-password-93"
        )
        self.admin.groups.add(admin_group)
        self.account = User.objects.create_user(
            username="customer", email="customer@example.test",
            password="Customer-test-password-93",
        )
        self.client.force_login(self.admin)

    def test_admin_can_view_account_list_and_dashboard_totals(self):
        response = self.client.get(reverse("admin_users"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin.username)
        self.assertContains(response, self.account.email)
        self.assertContains(response, "Active")

        dashboard = self.client.get(reverse("admin_dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Registered users")
        self.assertContains(dashboard, "Audit events")

    def test_admin_can_search_accounts_by_username_or_email(self):
        by_username = self.client.get(
            reverse("admin_users"), {"q": self.account.username}
        )
        self.assertContains(by_username, self.account.username)
        self.assertEqual(list(by_username.context["accounts"]), [self.account])

        by_email = self.client.get(
            reverse("admin_users"), {"q": self.account.email}
        )
        self.assertContains(by_email, self.account.username)
        self.assertEqual(list(by_email.context["accounts"]), [self.account])

    def test_admin_can_deactivate_account_and_audit_success(self):
        response = self.client.post(
            reverse(
                "admin_user_status",
                args=[self.account.pk, "deactivate"],
            )
        )
        self.assertRedirects(response, reverse("admin_users"))
        self.account.refresh_from_db()
        self.assertFalse(self.account.is_active)

        event = AuditLog.objects.get(action="account_deactivated")
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.resource, f"user:{self.account.pk}")
        self.assertEqual(event.outcome, "success")
        self.assertEqual(event.details, {"username": self.account.username})

    def test_admin_can_reactivate_account_and_audit_success(self):
        self.account.is_active = False
        self.account.save(update_fields=["is_active"])

        response = self.client.post(
            reverse(
                "admin_user_status",
                args=[self.account.pk, "reactivate"],
            )
        )
        self.assertRedirects(response, reverse("admin_users"))
        self.account.refresh_from_db()
        self.assertTrue(self.account.is_active)

        event = AuditLog.objects.get(action="account_reactivated")
        self.assertEqual(event.actor, self.admin)
        self.assertEqual(event.resource, f"user:{self.account.pk}")
        self.assertEqual(event.outcome, "success")

    def test_deactivated_user_cannot_log_in(self):
        self.account.is_active = False
        self.account.save(update_fields=["is_active"])

        client = Client()
        self.assertFalse(
            client.login(
                username=self.account.username,
                password="Customer-test-password-93",
            )
        )

    def test_deactivating_user_invalidates_an_existing_session(self):
        client = Client()
        self.assertTrue(
            client.login(
                username=self.account.username,
                password="Customer-test-password-93",
            )
        )
        self.account.is_active = False
        self.account.save(update_fields=["is_active"])

        response = client.get(reverse("dataset_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_normal_users_are_forbidden_from_administrator_pages(self):
        self.client.force_login(self.account)
        for name in ("admin_dashboard", "admin_users", "admin_datasets"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403)

    def test_normal_users_cannot_deactivate_or_reactivate_accounts(self):
        self.client.force_login(self.account)
        for action in ("deactivate", "reactivate"):
            with self.subTest(action=action):
                response = self.client.post(
                    reverse(
                        "admin_user_status",
                        args=[self.admin.pk, action],
                    )
                )
                self.assertEqual(response.status_code, 403)

        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_cannot_deactivate_own_account(self):
        response = self.client.post(
            reverse(
                "admin_user_status",
                args=[self.admin.pk, "deactivate"],
            )
        )
        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertFalse(
            AuditLog.objects.filter(action="account_deactivated").exists()
        )

    def test_superuser_account_status_is_protected(self):
        superuser = User.objects.create_superuser(
            username="root_admin", password="Root-test-password-93"
        )
        response = self.client.post(
            reverse(
                "admin_user_status",
                args=[superuser.pk, "deactivate"],
            )
        )
        self.assertEqual(response.status_code, 403)
        superuser.refresh_from_db()
        self.assertTrue(superuser.is_active)

    def test_status_changes_require_post_and_csrf(self):
        url = reverse(
            "admin_user_status",
            args=[self.account.pk, "deactivate"],
        )
        self.assertEqual(self.client.get(url).status_code, 405)

        strict_client = Client(enforce_csrf_checks=True)
        strict_client.force_login(self.admin)
        self.assertEqual(strict_client.post(url).status_code, 403)

    def test_admin_dataset_catalogue_shows_metadata_and_ownership_only(self):
        dataset = Dataset.objects.create(
            owner=self.account,
            original_name="private-records.csv",
            file="private-records.csv",
            rows=25,
            column_count=3,
            profile={"columns": [{"name": "secret_column"}]},
        )
        response = self.client.get(reverse("admin_datasets"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, dataset.original_name)
        self.assertContains(response, self.account.username)
        self.assertContains(response, "25")
        self.assertNotContains(response, "secret_column")
        self.assertNotContains(response, "private-records.csv</a>")

    def test_normal_user_cannot_access_dataset_catalogue(self):
        self.client.force_login(self.account)
        self.assertEqual(
            self.client.get(reverse("admin_datasets")).status_code, 403
        )

    def test_dataset_and_training_records_are_protected_from_deletion(self):
        dataset = Dataset.objects.create(
            owner=self.account,
            original_name="retained.csv",
            file="retained.csv",
            rows=25,
            column_count=3,
            profile={"columns": []},
        )
        batch = RunBatch.objects.create(
            owner=self.account,
            dataset=dataset,
            task="classification",
            run_config={},
        )
        run = Run.objects.create(
            owner=self.account,
            dataset=dataset,
            batch=batch,
            job_key="retention-test",
            run_config={},
            state=Run.COMPLETED,
        )
        training_job = TrainingJob.objects.create(
            user=self.account,
            dataset_name="retained.csv",
            model_name="random_forest",
            configuration={},
            status=TrainingJob.Status.COMPLETED,
        )

        with self.assertRaises(ProtectedError):
            dataset.delete()
        with self.assertRaises(ProtectedError):
            self.account.delete()

        self.assertTrue(Dataset.objects.filter(pk=dataset.pk).exists())
        self.assertTrue(RunBatch.objects.filter(pk=batch.pk).exists())
        self.assertTrue(Run.objects.filter(pk=run.pk).exists())
        self.assertTrue(TrainingJob.objects.filter(pk=training_job.pk).exists())

    def test_audit_history_survives_actor_deletion(self):
        event = AuditLog.objects.create(
            actor=self.account,
            action="test_event",
            resource=f"user:{self.account.pk}",
            outcome="success",
        )
        self.account.delete()
        event.refresh_from_db()
        self.assertIsNone(event.actor)

    def test_status_endpoint_rejects_unknown_account_action(self):
        response = self.client.post(
            reverse(
                "admin_user_status",
                args=[self.account.pk, "delete"],
            )
        )
        self.assertEqual(response.status_code, 404)
