"""UI tests for issue #19: job state, polling, failure reason and results (MLE-F-040, F-041, F-050, F-051)."""
import re
from datetime import timedelta
from pathlib import Path

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Dataset, Run
from .tests import WebUITestCase, upload

CLASSIFIER, REGRESSOR = "random_forest", "linear_regression"


def csv_with_constant_target(rows=25):
    lines = ["age,city,bought"] + [f"{20 + i},City{i % 3},1" for i in range(rows)]
    return ("\n".join(lines) + "\n").encode()


@override_settings(STANDIN_RUN_SYNC=True)
class RunTestCase(WebUITestCase):
    def start(self, algorithm=CLASSIFIER, target="bought", content=None):
        if content is not None:
            upload(self.client, content)
            dataset = Dataset.objects.latest("created_at")
        else:
            dataset = self.make_dataset()
        features = [c for c in dataset.column_names if c != target]
        session = self.client.session
        session[f"draft-{dataset.id}"] = {
            "target_column": target, "feature_columns": features, "excluded_columns": [], "algorithm": algorithm,
        }
        session.save()
        response = self.client.post(reverse("start_run", args=[dataset.id]))
        run = Run.objects.latest("created_at")
        return dataset, run, response

    def page(self, run):
        return self.client.get(reverse("run_detail", args=[run.job_key])).content.decode()

    def set_state(self, run, state, **fields):
        Run.objects.filter(pk=run.pk).update(state=state, **fields)
        run.refresh_from_db()


class StartRunTests(RunTestCase):
    def test_start_redirects_to_the_run_page_without_waiting(self):
        _, run, response = self.start()
        self.assertRedirects(response, reverse("run_detail", args=[run.job_key]))
        self.assertTrue(run.job_key.startswith("r-"))

    def test_run_config_has_the_keys_of_the_sad_interface(self):
        _, run, _ = self.start()
        self.assertEqual(
            set(run.run_config),
            {"dataset_id", "target_column", "feature_columns", "imputation", "encoding", "scaling",
             "split_ratio", "random_seed", "algorithm", "hyperparameters"},
        )

    def test_start_needs_post_login_and_saved_settings(self):
        dataset = self.make_dataset()
        self.assertEqual(self.client.get(reverse("start_run", args=[dataset.id])).status_code, 405)
        response = self.client.post(reverse("start_run", args=[dataset.id]))  # no algorithm chosen yet
        self.assertRedirects(response, reverse("model_step", args=[dataset.id]), fetch_redirect_response=False)
        self.assertEqual(Run.objects.count(), 0)
        self.client.logout()
        self.assertEqual(self.client.post(reverse("start_run", args=[dataset.id])).status_code, 302)

    def test_start_needs_a_csrf_token(self):
        from django.test import Client
        dataset = self.make_dataset()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(reverse("start_run", args=[dataset.id])).status_code, 403)

    def test_summary_offers_a_start_button(self):
        dataset = self.make_dataset()
        session = self.client.session
        session[f"draft-{dataset.id}"] = {"target_column": "bought", "feature_columns": ["age"], "excluded_columns": ["city"], "algorithm": CLASSIFIER}
        session.save()
        html = self.client.get(reverse("settings_summary", args=[dataset.id])).content.decode()
        self.assertIn(reverse("start_run", args=[dataset.id]), html)
        self.assertIn("Start run", html)


class JobStateTests(RunTestCase):
    def setUp(self):
        super().setUp()
        _, self.run, _ = self.start()

    def test_each_state_shows_its_word_and_a_glyph(self):
        for state, word in [("Queued", "Queued"), ("Running", "Running"), ("Completed", "Completed"), ("Failed", "Failed")]:
            self.set_state(self.run, state, error="x" if state == "Failed" else "")
            html = self.page(self.run)
            self.assertRegex(html, rf'run-state__glyph"[^>]*aria-hidden="true">[^<]+</span>\s*<span id="state-text">{word}</span>')

    def test_page_is_a_live_region_so_state_changes_are_announced(self):
        self.assertRegex(self.page(self.run), r'class="run-state[^"]*" role="status" aria-live="polite"')

    def test_active_run_polls_and_has_a_no_script_refresh_of_5_seconds_or_less(self):
        self.set_state(self.run, "Running", started_at=timezone.now())
        html = self.page(self.run)
        self.assertIn("webui/run.js", html)
        self.assertIn(reverse("run_status", args=[self.run.job_key]), html)
        self.assertRegex(html, r'<noscript><meta http-equiv="refresh" content="[1-5]">')

    def test_finished_run_does_not_poll(self):
        html = self.page(self.run)  # the stand-in worker already finished it
        self.assertNotIn("run.js", html)
        self.assertNotIn("http-equiv", html)

    def test_polling_interval_in_the_script_is_at_most_five_seconds(self):
        script = (Path(__file__).parent / "static" / "webui" / "run.js").read_text()
        interval = int(re.search(r"setInterval\(poll,\s*(\d+)\)", script).group(1))
        self.assertLessEqual(interval, 5000)

    def test_running_run_shows_elapsed_time_not_just_a_spinner(self):
        self.set_state(self.run, "Running", started_at=timezone.now() - timedelta(seconds=12), finished_at=None, result=None)
        html = self.page(self.run)
        self.assertRegex(html, r"Running for 00:1[23]\.")
        self.assertNotIn("spinner", html)

    def test_queued_run_says_it_is_waiting(self):
        self.set_state(self.run, "Queued", started_at=None, finished_at=None, result=None)
        self.assertIn("Waiting for a free worker", self.page(self.run))

    def test_stage_indicator_moves_to_results_only_when_completed(self):
        self.set_state(self.run, "Running", started_at=timezone.now(), finished_at=None, result=None)
        self.assertRegex(self.page(self.run), r'aria-current="step">\s*4\. Run')
        self.set_state(self.run, "Completed", finished_at=timezone.now())
        Run.objects.filter(pk=self.run.pk).update(result={"task": "regression", "mae": 1, "mse": 1, "rmse": 1, "r2": 0})
        self.assertRegex(self.page(self.run), r'aria-current="step">\s*5\. Results')


class StatusEndpointTests(RunTestCase):
    def setUp(self):
        super().setUp()
        _, self.run, _ = self.start()
        self.url = reverse("run_status", args=[self.run.job_key])

    def test_url_is_the_one_in_the_sad(self):
        self.assertEqual(self.url, f"/api/runs/{self.run.job_key}/status")

    def test_json_has_exactly_the_documented_fields(self):
        data = self.client.get(self.url).json()
        self.assertEqual(set(data), {"job_key", "state", "started_at", "elapsed_s", "error"})
        self.assertEqual(data["job_key"], self.run.job_key)

    def test_state_change_is_visible_on_the_next_request(self):
        self.set_state(self.run, "Queued", started_at=None, finished_at=None)
        self.assertEqual(self.client.get(self.url).json()["state"], "Queued")
        self.assertIsNone(self.client.get(self.url).json()["elapsed_s"])
        self.set_state(self.run, "Running", started_at=timezone.now() - timedelta(seconds=5))
        data = self.client.get(self.url).json()
        self.assertEqual(data["state"], "Running")
        self.assertGreaterEqual(data["elapsed_s"], 5)
        self.set_state(self.run, "Failed", error="Column 'x' is not numeric.", finished_at=timezone.now())
        data = self.client.get(self.url).json()
        self.assertEqual((data["state"], data["error"]), ("Failed", "Column 'x' is not numeric."))

    def test_signed_out_gets_401_not_a_login_page(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_another_users_run_is_403_and_leaks_nothing(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(self.run.job_key, response.content.decode())
        self.assertEqual(self.client.get(reverse("run_detail", args=[self.run.job_key])).status_code, 403)

    def test_unknown_run_is_404(self):
        self.assertEqual(self.client.get(reverse("run_status", args=["r-nothere"])).status_code, 404)
        self.assertEqual(self.client.get(reverse("run_detail", args=["r-nothere"])).status_code, 404)

    def test_status_cannot_be_changed_with_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_response_is_not_cached(self):
        self.assertIn("no-store", self.client.get(self.url)["Cache-Control"])

    def test_run_left_running_for_too_long_is_failed_not_shown_running_forever(self):
        self.set_state(self.run, "Running", started_at=timezone.now(), finished_at=None)
        Run.objects.filter(pk=self.run.pk).update(created_at=timezone.now() - timedelta(hours=1))
        data = self.client.get(self.url).json()
        self.assertEqual(data["state"], "Failed")
        self.assertIn("interrupted", data["error"])


class FailureTests(RunTestCase):
    def test_single_valued_target_fails_with_a_reason_the_user_can_act_on(self):
        _, run, _ = self.start(content=csv_with_constant_target())
        self.assertEqual(run.state, "Failed")
        html = self.page(run)
        self.assertIn('role="alert"', html)
        self.assertIn("has only one value", html)
        self.assertIn("Choose a different target", html)
        self.assertIn(reverse("settings_summary", args=[run.dataset_id]), html)
        self.assertNotIn("Classification metrics", html)

    def test_text_target_for_a_regression_algorithm_fails_with_its_reason(self):
        _, run, _ = self.start(algorithm=REGRESSOR, target="city")
        self.assertEqual(run.state, "Failed")
        self.assertIn("is not numeric", self.page(run))

    def test_failed_run_status_carries_the_same_reason(self):
        _, run, _ = self.start(algorithm=REGRESSOR, target="city")
        data = self.client.get(reverse("run_status", args=[run.job_key])).json()
        self.assertEqual(data["state"], "Failed")
        self.assertIn("is not numeric", data["error"])

    def test_unexpected_worker_error_is_a_plain_message_not_a_traceback(self):
        from unittest import mock
        with mock.patch("webui.standins.runs._train_and_score", side_effect=RuntimeError("boom /secret/path")):
            _, run, _ = self.start()
        self.assertEqual(run.state, "Failed")
        html = self.page(run)
        self.assertIn("stopped unexpectedly", html)
        self.assertNotIn("boom", html)
        self.assertNotIn("/secret/path", html)


class ResultsTests(RunTestCase):
    def test_classification_shows_the_four_metrics_in_a_numeric_table(self):
        _, run, _ = self.start()
        self.assertEqual(run.state, "Completed")
        html = self.page(run)
        for name in ("Accuracy", "Precision", "Recall", "F1-score"):
            self.assertRegex(html, rf'<th scope="row">{name}</th><td class="num">\d\.\d{{4}}</td>')

    def test_confusion_matrix_is_a_table_with_labelled_axes_and_matching_totals(self):
        _, run, _ = self.start()
        html = self.page(run)
        self.assertIn("Confusion matrix", html)
        self.assertRegex(html, r'<th scope="colgroup" colspan="2"[^>]*>Predicted</th>')
        self.assertIn('<th scope="col">Actual</th>', html)
        total = sum(sum(row) for row in run.result["confusion_matrix"])
        self.assertEqual(total, run.result["test_rows"])
        self.assertEqual(len(run.result["labels"]), len(run.result["confusion_matrix"]))

    def test_correct_cells_are_marked_with_a_tick_and_text_not_colour_alone(self):
        _, run, _ = self.start()
        html = self.page(run)
        self.assertIn('class="visually-hidden">correct: </span>', html)
        self.assertIn("&#10003;", html)

    def test_regression_shows_mae_mse_rmse_and_r2(self):
        _, run, _ = self.start(algorithm=REGRESSOR, target="age")
        self.assertEqual(run.state, "Completed", run.error)
        html = self.page(run)
        for name in ("MAE", "MSE", "RMSE", "R&sup2;"):
            self.assertRegex(html, rf'<th scope="row">{name} [^<]*</th><td class="num">-?\d+\.\d{{4}}</td>')
        self.assertNotIn("Confusion matrix", html)
        self.assertAlmostEqual(run.result["rmse"] ** 2, run.result["mse"], places=6)

    def test_every_table_has_a_caption_and_header_cells(self):
        for algorithm, target in [(CLASSIFIER, "bought"), (REGRESSOR, "age")]:
            _, run, _ = self.start(algorithm, target)
            html = self.page(run)
            tables = re.findall(r"<table.*?</table>", html, flags=re.DOTALL)
            self.assertTrue(tables)
            for table in tables:
                self.assertIn("<caption>", table)
                self.assertIn('scope="col"', table)

    def test_results_say_they_are_placeholders_while_the_worker_is_a_stand_in(self):
        _, run, _ = self.start()
        html = self.page(run)
        self.assertIn("Placeholder results", html)
        self.assertIn("not from Random Forest", html)

    def test_no_chart_without_a_table(self):
        _, run, _ = self.start()
        html = self.page(run)
        self.assertNotRegex(html, r"<(canvas|svg)[^>]*(?<!aria-hidden=\"true\")>\s*<(?!path|circle)")
        self.assertNotIn("<canvas", html)

    def test_metrics_are_not_shown_for_a_run_that_has_not_finished(self):
        _, run, _ = self.start()
        self.set_state(run, "Running", started_at=timezone.now(), finished_at=None, result=None)
        html = self.page(run)
        self.assertNotIn("Accuracy", html)
        self.assertNotIn("Confusion matrix", html)

    def test_run_page_has_a_keyboard_reachable_scroll_region_for_each_table(self):
        _, run, _ = self.start()
        html = self.page(run)
        self.assertGreaterEqual(len(re.findall(r'class="table-wrap" tabindex="0" role="region" aria-label="[^"]+"', html)), 2)
