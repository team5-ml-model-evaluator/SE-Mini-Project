"""Prevent accidental classification of amounts before queuing training."""
from unittest.mock import patch

from django.urls import reverse

from .models import Dataset, Run
from .tests import WebUITestCase, upload


class TargetValidationTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        content = "amount,purchased,category\n" + "\n".join(
            f"{1000 + i * 1.25},{i % 2},category-{i}" for i in range(40)
        ) + "\n"
        upload(self.client, content.encode())
        self.dataset = Dataset.objects.latest("created_at")
        self.model_url = reverse("model_step", args=[self.dataset.id])
        self.start_url = reverse("start_run", args=[self.dataset.id])

    def draft(self, target="amount", algorithm=None):
        config = {"target_column": target,
                  "feature_columns": [name for name in self.dataset.column_names if name != target],
                  "excluded_columns": []}
        if algorithm:
            config["algorithm"] = algorithm
        session = self.client.session
        session[f"draft-{self.dataset.id}"] = config
        session.save()

    def test_continuous_numeric_target_rejected_for_every_classifier(self):
        self.draft()
        for algorithm in ["logistic_regression", "decision_tree", "random_forest", "knn", "svm"]:
            with self.subTest(algorithm=algorithm):
                response = self.client.post(self.model_url, {"algorithm": algorithm})
                self.assertContains(response, "looks like a numeric amount")
                self.assertContains(response, "40 distinct values in 40 rows")
                self.assertContains(response, "regression algorithm")
                self.assertIn("algorithm", response.context["form"].errors)
        self.assertEqual(Run.objects.count(), 0)

    def test_start_endpoint_rechecks_old_or_forged_saved_settings(self):
        self.draft(algorithm="logistic_regression")
        with patch("webui.views.runs.start") as start:
            response = self.client.post(self.start_url, follow=True)
        start.assert_not_called()
        self.assertContains(response, "looks like a numeric amount")
        self.assertEqual(Run.objects.count(), 0)

    def test_numeric_binary_classification_and_amount_regression_are_allowed(self):
        for target, algorithm in [("purchased", "logistic_regression"),
                                  ("amount", "linear_regression"),
                                  ("category", "decision_tree")]:
            with self.subTest(target=target):
                self.draft(target)
                response = self.client.post(self.model_url, {"algorithm": algorithm})
                self.assertRedirects(response, reverse("settings_summary", args=[self.dataset.id]))

    def test_valid_configuration_can_start(self):
        self.draft("purchased", "logistic_regression")
        with patch("webui.views.runs.start", return_value="r-valid") as start:
            response = self.client.post(self.start_url)
        self.assertRedirects(response, reverse("run_detail", args=["r-valid"]), fetch_redirect_response=False)
        start.assert_called_once()

    def test_small_numeric_categories_are_allowed_even_when_stored_as_decimals(self):
        upload(self.client, ("amount,feature\n" + "\n".join(f"{i % 4}.0,{i}" for i in range(40))).encode())
        self.dataset = Dataset.objects.latest("created_at")
        self.model_url = reverse("model_step", args=[self.dataset.id])
        self.draft("amount")
        self.assertRedirects(self.client.post(self.model_url, {"algorithm": "random_forest"}),
                             reverse("settings_summary", args=[self.dataset.id]))

    def test_unknown_algorithm_still_has_normal_form_error(self):
        self.draft()
        self.assertContains(self.client.post(self.model_url, {"algorithm": "unknown"}),
                            "Choose an algorithm from the list")

    def test_missing_dataset_file_is_explained_and_never_starts_training(self):
        self.draft(algorithm="logistic_regression")
        self.dataset.file.delete(save=False)
        with patch("webui.views.runs.start") as start:
            response = self.client.post(self.start_url, follow=True)
        start.assert_not_called()
        self.assertContains(response, "Could not check the target column")

    def test_half_distinct_numeric_categories_are_allowed(self):
        content = "amount,feature\n" + "\n".join(f"{i % 25},{i}" for i in range(50)) + "\n"
        upload(self.client, content.encode())
        self.dataset = Dataset.objects.latest("created_at")
        self.model_url = reverse("model_step", args=[self.dataset.id])
        self.draft("amount")
        self.assertRedirects(self.client.post(self.model_url, {"algorithm": "random_forest"}),
                             reverse("settings_summary", args=[self.dataset.id]))

    def test_empty_target_is_left_to_existing_worker_failure_handling(self):
        content = "amount,feature\n" + "\n".join(f",{i}" for i in range(40)) + "\n"
        upload(self.client, content.encode())
        self.dataset = Dataset.objects.latest("created_at")
        self.model_url = reverse("model_step", args=[self.dataset.id])
        self.draft("amount")
        self.assertRedirects(self.client.post(self.model_url, {"algorithm": "random_forest"}),
                             reverse("settings_summary", args=[self.dataset.id]))
