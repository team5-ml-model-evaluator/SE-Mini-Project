"""Issue #20: compare stored, compatible runs without executing training."""
from copy import deepcopy
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse

from .comparison import build_comparison
from .models import Run
from .tests import WebUITestCase


CLASSIFICATION = {
    "task": "classification", "accuracy": 0.8123456789, "precision": 0.8,
    "recall": 0.75, "f1_score": 0.77, "labels": ["no", "yes"],
    "confusion_matrix": [[8, 2], [3, 7]], "standin": False,
}
REGRESSION = {"task": "regression", "mae": 0.0, "mse": 0.25, "rmse": 0.5, "r2": -0.25}


class ComparisonTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()
        self.url = reverse("run_comparison", args=[self.dataset.id])
        self.first = self.make_run("r-first")
        self.second = self.make_run("r-second", algorithm="decision_tree")

    def make_run(self, key, *, dataset=None, owner=None, algorithm="random_forest",
                 target="bought", result=None, state=Run.COMPLETED):
        return Run.objects.create(
            job_key=key, dataset=dataset or self.dataset, owner=owner or self.user,
            state=state, run_config={"target_column": target, "algorithm": algorithm,
                                     "feature_columns": ["age"], "scaling": None},
            result=deepcopy(CLASSIFICATION if result is None else result),
        )

    def compare(self, *runs):
        return self.client.get(self.url, {"runs": [r.job_key for r in runs]})

    def test_initial_page_offers_labelled_completed_runs_and_no_error(self):
        self.make_run("r-running", state=Run.RUNNING)
        html = self.client.get(self.url).content.decode()
        self.assertIn("r-first", html)
        self.assertNotIn("r-running", html)
        self.assertNotIn('role="alert"', html)
        self.assert_labelled(html)

    def test_three_runs_are_columns_with_exact_stored_values_and_selected_order(self):
        result = deepcopy(CLASSIFICATION)
        result["accuracy"] = 0.9123456789
        third = self.make_run("r-third", algorithm="svm", result=result)
        response = self.compare(third, self.first, self.second)
        self.assertEqual(response.status_code, 200)
        comparison = response.context["comparison"]
        self.assertEqual([item["run"].job_key for item in comparison["columns"]],
                         ["r-third", "r-first", "r-second"])
        self.assertEqual(comparison["rows"][0]["values"],
                         ["0.9123456789", "0.8123456789", "0.8123456789"])
        self.assertContains(response, '<td class="num">91.23%</td>')
        self.assertContains(response, '<td class="num">81.23%</td>')
        self.assertNotContains(response, "0.9123456789")
        self.assertContains(response, "Confusion matrix")
        self.assertContains(response, '<th scope="row">no</th>')
        self.assertContains(response, 'tabindex="0" role="region"')
        self.assertContains(response, 'aria-current="step"')

    def test_regression_preserves_zero_and_negative_values(self):
        a = self.make_run("r-reg1", algorithm="linear_regression", result=REGRESSION)
        b = self.make_run("r-reg2", algorithm="decision_tree_regressor", result=REGRESSION)
        response = self.compare(a, b)
        self.assertContains(response, '<td class="num">0.00</td>')
        self.assertContains(response, "-0.25")
        self.assertNotContains(response, "%</td>")
        self.assertEqual([r["label"] for r in response.context["comparison"]["rows"]],
                         ["MAE", "MSE", "RMSE", "R²"])

    def test_empty_single_and_duplicate_selections_are_explained(self):
        for keys in [[], [self.first.job_key], [self.first.job_key] * 2]:
            with self.subTest(keys=keys):
                response = self.client.get(self.url, {"compare": "1", "runs": keys})
                self.assertContains(response, "Select at least two different completed runs")
                self.assertIsNone(response.context["comparison"])

    def test_different_targets_and_tasks_are_rejected(self):
        target = self.make_run("r-target", target="age")
        task = self.make_run("r-task", algorithm="linear_regression", result=REGRESSION)
        for run, message in [(target, "same target column"), (task, "same task type")]:
            with self.subTest(key=run.job_key):
                response = self.compare(self.first, run)
                self.assertContains(response, message)
                self.assertIsNone(response.context["comparison"])

    def test_cross_dataset_unknown_incomplete_and_foreign_runs_are_rejected(self):
        other_dataset = self.make_dataset()
        wrong_dataset = self.make_run("r-other-dataset", dataset=other_dataset)
        foreign = self.make_run("r-private", owner=self.other)
        for key in [wrong_dataset.job_key, foreign.job_key, "does-not-exist"]:
            response = self.client.get(self.url, {"runs": [self.first.job_key, key]})
            self.assertContains(response, "Choose only completed runs from this dataset that belong to you")
            self.assertIsNone(response.context["comparison"])
        for state in [Run.QUEUED, Run.RUNNING, Run.FAILED]:
            run = self.make_run("r-" + state, state=state)
            response = self.compare(self.first, run)
            self.assertContains(response, "Choose only completed runs")
            self.assertIsNone(response.context["comparison"])

    def test_missing_or_invalid_results_do_not_render_as_valid_comparisons(self):
        bad_results = [None, {}, {"task": "classification"},
                       {**CLASSIFICATION, "accuracy": "bad"},
                       {**CLASSIFICATION, "accuracy": True},
                       {**CLASSIFICATION, "accuracy": float("inf")},
                       {**CLASSIFICATION, "task": "regression"}]
        for result in bad_results:
            with self.subTest(result=result):
                # Store inf as a string: JSONField does not accept non-finite JSON numbers on SQLite.
                if result and result.get("accuracy") == float("inf"):
                    result = {**result, "accuracy": "Infinity"}
                Run.objects.filter(pk=self.second.pk).update(result=result)
                response = self.compare(self.first, self.second)
                self.assertContains(response, "incomplete or invalid evaluation results")
                self.assertIsNone(response.context["comparison"])

    def test_different_preprocessing_is_allowed_and_placeholder_results_are_identified(self):
        config = {**self.second.run_config, "scaling": "standard"}
        Run.objects.filter(pk=self.second.pk).update(run_config=config,
                                                    result={**CLASSIFICATION, "standin": True})
        response = self.compare(self.first, self.second)
        self.assertIsNotNone(response.context["comparison"])
        self.assertContains(response, "Placeholder baseline")

    def test_authentication_dataset_ownership_and_get_only(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_comparison_does_not_execute_training_or_change_results(self):
        with patch("webui.views.runs.start") as start, patch("webui.views.runs.get_status") as status:
            self.compare(self.first, self.second)
        start.assert_not_called()
        status.assert_not_called()
        self.first.refresh_from_db()
        self.assertEqual(self.first.result, CLASSIFICATION)

    def test_dataset_and_completed_run_pages_link_to_comparison(self):
        self.assertContains(self.client.get(reverse("dataset_detail", args=[self.dataset.id])), self.url)
        self.assertContains(self.client.get(reverse("run_detail", args=[self.first.job_key])), self.url)

    def test_no_completed_runs_has_clear_guidance(self):
        Run.objects.all().delete()
        self.assertContains(self.client.get(self.url), "Complete at least two runs")

    def test_shared_builder_guards_completion_dataset_and_selection(self):
        with self.assertRaisesMessage(ValidationError, "at least two different"):
            build_comparison([self.first])
        self.second.state = Run.RUNNING
        with self.assertRaisesMessage(ValidationError, "only completed"):
            build_comparison([self.first, self.second])
        self.second.state = Run.COMPLETED
        self.second.dataset = self.make_dataset()
        with self.assertRaisesMessage(ValidationError, "same dataset"):
            build_comparison([self.first, self.second])

    def test_invalid_configuration_and_confusion_matrices_are_explained(self):
        configs = [[], {}, {"algorithm": "missing", "target_column": "bought"},
                   {"algorithm": "random_forest", "target_column": ""}]
        for config in configs:
            with self.subTest(config=config):
                self.second.run_config = config
                with self.assertRaisesMessage(ValidationError, "incomplete or invalid"):
                    build_comparison([self.first, self.second])
        self.second.run_config = self.first.run_config
        for changes in [{"labels": []}, {"confusion_matrix": []},
                        {"confusion_matrix": [[1], [2]]},
                        {"confusion_matrix": [[True, 0], [0, 1]]},
                        {"confusion_matrix": [[-1, 0], [0, 1]]}]:
            with self.subTest(changes=changes):
                self.second.result = {**CLASSIFICATION, **changes}
                with self.assertRaisesMessage(ValidationError, "incomplete or invalid"):
                    build_comparison([self.first, self.second])

    def test_oversized_integer_metric_gets_validation_guidance(self):
        self.second.result = {**CLASSIFICATION, "accuracy": 10 ** 400}
        with self.assertRaisesMessage(ValidationError, "incomplete or invalid"):
            build_comparison([self.first, self.second])
