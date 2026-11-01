"""Task-aware, owned batch training and comparison dashboard."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Run
from .test_comparison import CLASSIFICATION, REGRESSION
from .tests import WebUITestCase


class BatchTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()
        self.summary_url = reverse("settings_summary", args=[self.dataset.id])
        self.start_url = reverse("start_batch", args=[self.dataset.id])
        self.set_draft()

    def set_draft(self, algorithm="random_forest", target="bought"):
        session = self.client.session
        session[f"draft-{self.dataset.id}"] = {
            "algorithm": algorithm, "target_column": target,
            "feature_columns": [name for name in self.dataset.column_names if name != target],
            "excluded_columns": [],
        }
        session.save()

    def token(self):
        response = self.client.get(self.summary_url)
        return response.context["batch_token"]

    def start(self, token=None):
        return self.client.post(self.start_url, {"batch_token": token or self.token()})

    def batch(self):
        from .models import RunBatch
        return RunBatch.objects.latest("created_at")

    def finish(self, batch, result=CLASSIFICATION):
        batch.runs.update(state=Run.COMPLETED, result=result)
        type(batch).objects.filter(pk=batch.pk).update(active=False)
        batch.refresh_from_db()

    def test_classification_batch_creates_five_runs_with_identical_data_settings(self):
        from .models import RunBatch
        response = self.start()
        batch = self.batch()
        self.assertRedirects(response, reverse("batch_detail", args=[batch.id]))
        self.assertEqual(RunBatch.objects.count(), 1)
        runs = list(batch.runs.all())
        self.assertEqual(len(runs), 5)
        self.assertEqual({r.run_config["algorithm"] for r in runs},
                         {"logistic_regression", "decision_tree", "random_forest", "knn", "svm"})
        for run in runs:
            self.assertEqual(run.owner_id, self.user.id)
            self.assertEqual(run.dataset_id, self.dataset.id)
            self.assertEqual(run.run_config["target_column"], "bought")
            self.assertEqual(run.run_config["feature_columns"], ["age", "city"])
            self.assertEqual(run.run_config["random_seed"], 42)
            self.assertEqual(run.run_config["split_ratio"], 0.8)

    def test_regression_batch_creates_only_three_regression_models(self):
        self.set_draft("linear_regression", "age")
        self.start()
        self.assertEqual({r.run_config["algorithm"] for r in self.batch().runs.all()},
                         {"linear_regression", "decision_tree_regressor", "random_forest_regressor"})

    def test_repeat_submission_reuses_batch_and_fresh_requests_do_not_duplicate_active_work(self):
        from .models import RunBatch
        token = self.token()
        first = self.start(token)
        second = self.start(token)
        third = self.start(self.token())
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(first["Location"], third["Location"])
        self.assertEqual(RunBatch.objects.count(), 1)
        self.assertEqual(Run.objects.count(), 5)

    def test_invalid_stale_or_foreign_tokens_never_queue_jobs(self):
        token = self.token()
        self.assertEqual(self.start("tampered").status_code, 400)
        self.set_draft("linear_regression", "age")
        self.assertEqual(self.start(token).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.start_url, {"batch_token": token}).status_code, 403)
        self.assertEqual(Run.objects.count(), 0)

    def test_wrong_target_task_is_rejected_before_any_run_is_created(self):
        self.set_draft("random_forest", "age")  # 25 distinct numeric amounts
        response = self.start()
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "looks like a numeric amount", status_code=400)
        self.set_draft("linear_regression", "city")
        response = self.start()
        self.assertContains(response, "numeric target", status_code=400)
        self.assertEqual(Run.objects.count(), 0)

    def test_authentication_get_only_and_csrf(self):
        self.assertEqual(self.client.get(self.start_url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(self.start_url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.start_url).status_code, 302)

    def test_worker_uses_one_model_at_a_time_and_continues_after_model_failure(self):
        from .batches import execute_batch
        self.start()
        batch = self.batch()
        keys = list(batch.runs.order_by("pk").values_list("job_key", flat=True))
        calls = []

        def execute(key, queue_s, run_s):
            calls.append(key)
            if len(calls) == 1:
                raise RuntimeError("private internal worker failure")
            Run.objects.filter(job_key=key).update(state=Run.COMPLETED, result=CLASSIFICATION)

        with patch("webui.batches.runs._execute", side_effect=execute):
            execute_batch(batch.id)
        self.assertEqual(calls, keys)
        batch.refresh_from_db()
        self.assertFalse(batch.active)
        failed = batch.runs.get(job_key=keys[0])
        self.assertEqual(failed.state, Run.FAILED)
        self.assertNotIn("private", failed.error)
        self.assertEqual(batch.runs.filter(state=Run.COMPLETED).count(), 4)

    @override_settings(STANDIN_RUN_SYNC=True)
    def test_real_batch_trains_and_records_results(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.start()
        batch = self.batch()
        self.assertEqual(batch.runs.filter(state=Run.COMPLETED).count(), 5)
        self.assertFalse(type(batch).objects.get(pk=batch.id).active)
        for run in batch.runs.all():
            self.assertEqual(run.result["task"], "classification")
            self.assertFalse(run.result["standin"])

    def test_dashboard_shows_partial_progress_then_charts_and_matching_table(self):
        self.start()
        batch = self.batch()
        url = reverse("batch_detail", args=[batch.id])
        response = self.client.get(url)
        self.assertContains(response, "0 of 5")
        self.assertContains(response, "Queued")
        self.assertContains(response, "Waiting for at least two")
        self.assertContains(response, "batch.js")
        completed = list(batch.runs.order_by("pk")[:2])
        for run in completed:
            Run.objects.filter(pk=run.pk).update(state=Run.COMPLETED, result=deepcopy(CLASSIFICATION))
        response = self.client.get(url)
        self.assertContains(response, "81.23%")
        self.assertContains(response, "Comparison chart")
        self.assertContains(response, "Numeric comparison")
        self.assertContains(response, "Download comparison CSV")
        self.finish(batch)
        response = self.client.get(url)
        self.assertNotContains(response, 'src="/static/webui/batch.js"')

    def test_dashboard_and_status_are_owned_and_status_never_loads_results(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.start()
        batch = self.batch()
        url = reverse("batch_status", args=[batch.id])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.json()["total"], 5)
        self.assertNotIn('"webui_run"."result"', " ".join(query["sql"] for query in queries))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse("batch_detail", args=[batch.id])).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 401)

    def test_failed_models_show_reasons_and_do_not_enter_comparison(self):
        self.start()
        batch = self.batch()
        first = batch.runs.first()
        Run.objects.filter(pk=first.pk).update(state=Run.FAILED, error="Choose a different target.")
        for run in batch.runs.exclude(pk=first.pk):
            Run.objects.filter(pk=run.pk).update(state=Run.COMPLETED, result=CLASSIFICATION)
        response = self.client.get(reverse("batch_detail", args=[batch.id]))
        self.assertContains(response, "Choose a different target.")
        self.assertEqual(len(response.context["comparison"]["columns"]), 4)

    def test_manual_comparison_also_has_metric_visualizations(self):
        self.start()
        batch = self.batch()
        self.finish(batch)
        response = self.client.get(reverse("run_comparison", args=[self.dataset.id]),
                                   {"runs": list(batch.runs.values_list("job_key", flat=True))})
        self.assertContains(response, "Comparison chart")
        self.assertContains(response, 'name="metric"')

    def test_old_queued_models_stay_queued_while_batch_worker_is_alive(self):
        self.start()
        batch = self.batch()
        batch.runs.update(created_at=timezone.now() - timedelta(minutes=30))
        response = self.client.get(reverse("batch_status", args=[batch.id]))
        self.assertTrue(response.json()["active"])
        self.assertTrue(all(job["state"] == Run.QUEUED for job in response.json()["jobs"]))
        run = batch.runs.first()
        response = self.client.get(reverse("run_status", args=[run.job_key]))
        self.assertEqual(response.json()["state"], Run.QUEUED)

    def test_lost_worker_marks_remaining_models_failed_and_releases_active_batch(self):
        self.start()
        batch = self.batch()
        type(batch).objects.filter(pk=batch.id).update(heartbeat_at=timezone.now() - timedelta(minutes=3))
        response = self.client.get(reverse("batch_status", args=[batch.id]))
        self.assertFalse(response.json()["active"])
        self.assertEqual(response.json()["failed"], 5)
        batch.refresh_from_db()
        self.assertFalse(batch.active)
        self.assertTrue(all("interrupted" in job["error"] for job in response.json()["jobs"]))

    def test_full_local_queue_returns_clear_retry_guidance_without_submitting_work(self):
        from .batches import schedule_batch
        self.start()
        batch = self.batch()
        with patch("webui.batches._queue_slots") as slots, patch("webui.batches._executor.submit") as submit:
            slots.acquire.return_value = False
            schedule_batch(batch.id)
        submit.assert_not_called()
        batch.refresh_from_db()
        self.assertFalse(batch.active)
        self.assertEqual(batch.runs.filter(state=Run.FAILED).count(), 5)
        self.assertIn("queue is busy", batch.runs.first().error)

    def test_expired_run_cannot_be_overwritten_by_late_model_results(self):
        from .standins import runs
        self.start()
        run = self.batch().runs.order_by("pk").first()

        def expire_while_fitting(current):
            Run.objects.filter(pk=current.pk).update(state=Run.FAILED, error="The evaluation was interrupted.")
            return CLASSIFICATION

        with patch("webui.standins.runs._train_and_score", side_effect=expire_while_fitting):
            runs._execute(run.job_key, 0, 0)
        run.refresh_from_db()
        self.assertEqual(run.state, Run.FAILED)
        self.assertIn("interrupted", run.error)
        self.assertIsNone(run.result)
