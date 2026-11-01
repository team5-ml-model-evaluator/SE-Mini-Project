"""Issue #21: report completeness, CSV fidelity, and download authorization."""
import csv
import io
from copy import deepcopy

from django.urls import reverse
from django.test import override_settings
from pypdf import PdfReader

from .models import Run
from .test_comparison import CLASSIFICATION, REGRESSION
from .tests import WebUITestCase


class ReportTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()
        self.config = {"algorithm": "random_forest", "target_column": "bought", "feature_columns": ["age"],
                       "imputation": None, "encoding": None, "scaling": None,
                       "split_ratio": 0.8, "random_seed": 42, "hyperparameters": {}}
        self.result = {**deepcopy(CLASSIFICATION), "execution": {
            "preprocessing": {"imputation": "training median", "encoding": "one-hot", "scaling": "none"},
            "hyperparameters": {"n_estimators": 100, "random_state": 42},
        }}
        self.run = self.make_run("r-report")
        self.second = self.make_run("r-report2")

    def make_run(self, key, *, owner=None, state=Run.COMPLETED, result=None):
        return Run.objects.create(job_key=key, owner=owner or self.user, dataset=self.dataset,
                                  state=state, run_config=deepcopy(self.config),
                                  result=deepcopy(self.result if result is None else result))

    def report_url(self, format="html", run=None, detailed=True):
        url = reverse("run_report", kwargs={"job_key": (run or self.run).job_key, "format": format})
        return url + "?details=1" if detailed else url

    def csv_url(self):
        return reverse("run_comparison_csv", args=[self.dataset.id])

    def csv_rows(self, response):
        return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_html_download_contains_dataset_config_effective_settings_and_all_metrics(self):
        response = self.client.get(self.report_url())
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertIn('attachment;', response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        for text in ["Evaluation report", "data.csv", "25", "bought", "age", "city", "Random Forest",
                     "0.8", "42", "training median", "one-hot", "n_estimators", "100",
                     "Accuracy", "Precision", "Recall", "F1-score", "0.8123456789",
                     "Confusion matrix", "no", "yes"]:
            self.assertContains(response, text)

    def test_pdf_is_valid_readable_and_contains_report_data(self):
        response = self.client.get(self.report_url("pdf"))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(".pdf", response["Content-Disposition"])
        document = PdfReader(io.BytesIO(response.content))
        text = "\n".join(page.extract_text() for page in document.pages)
        for value in ["Evaluation report", "data.csv", "bought", "Random Forest", "n_estimators",
                      "training median", "0.8123456789", "Confusion matrix"]:
            self.assertIn(value, text)

    def test_reports_for_old_runs_explicitly_identify_missing_metadata(self):
        Run.objects.filter(pk=self.run.pk).update(result=CLASSIFICATION)
        self.assertContains(self.client.get(self.report_url()), "Not recorded for this run")

    def test_regression_report_has_all_metrics_and_no_classification_matrix(self):
        config = {**self.config, "algorithm": "linear_regression"}
        Run.objects.filter(pk=self.run.pk).update(run_config=config, result=REGRESSION)
        response = self.client.get(self.report_url())
        for text in ["MAE", "MSE", "RMSE", "R²", "-0.25"]:
            self.assertContains(response, text)
        self.assertNotContains(response, "Confusion matrix")
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf")).content))
        self.assertIn("-0.25", "\n".join(page.extract_text() for page in document.pages))

    def test_large_matrix_reports_use_complete_sparse_counts_not_millions_of_cells(self):
        labels = [f"class-{i}" for i in range(45)]
        matrix = [[0] * 45 for _ in labels]
        matrix[44][43] = 7
        Run.objects.filter(pk=self.run.pk).update(result={**self.result, "labels": labels, "confusion_matrix": matrix})
        response = self.client.get(self.report_url())
        self.assertContains(response, "Unlisted class pairs have count 0")
        self.assertContains(response, "class-44")
        self.assertContains(response, "class-43")
        self.assertContains(response, ">7<")
        self.assertLess(len(response.content), 25_000)
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf")).content))
        self.assertIn("class-44", "\n".join(page.extract_text() for page in document.pages))

    def test_downloads_require_login_ownership_and_get(self):
        for format in ["html", "pdf"]:
            url = self.report_url(format)
            self.assertEqual(self.client.post(url).status_code, 405)
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.user)
        foreign = self.make_run("r-foreign", owner=self.other)
        self.assertEqual(self.client.get(self.report_url(run=foreign)).status_code, 403)
        self.assertEqual(self.client.get(self.report_url("exe")).status_code, 404)
        url = reverse("run_report", kwargs={"job_key": "unknown", "format": "html"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_unfinished_and_invalid_results_cannot_be_downloaded(self):
        for state in [Run.QUEUED, Run.RUNNING, Run.FAILED]:
            Run.objects.filter(pk=self.run.pk).update(state=state)
            for format in ["html", "pdf"]:
                self.assertEqual(self.client.get(self.report_url(format)).status_code, 409)
        Run.objects.filter(pk=self.run.pk).update(state=Run.COMPLETED, result={})
        self.assertEqual(self.client.get(self.report_url()).status_code, 409)

    def test_untrusted_names_and_parameters_are_escaped_in_html_and_pdf(self):
        self.dataset.original_name = '<script>alert("x")</script>.csv'
        self.dataset.save(update_fields=["original_name"])
        result = {**self.result, "execution": {**self.result["execution"],
                  "hyperparameters": {"note": "<b>untrusted</b> & data"}}}
        Run.objects.filter(pk=self.run.pk).update(result=result)
        response = self.client.get(self.report_url())
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")
        self.assertEqual(self.client.get(self.report_url("pdf")).status_code, 200)

    def test_csv_matches_table_values_order_and_opens_with_csv_reader(self):
        result = {**self.result, "accuracy": 0.74333333333333}
        Run.objects.filter(pk=self.second.pk).update(result=result)
        selection = {"runs": [self.second.job_key, self.run.job_key]}
        response = self.client.get(self.csv_url(), selection)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        rows = self.csv_rows(response)
        self.assertEqual(rows[0], ["Metric", f"Random Forest ({self.second.job_key})",
                                   f"Random Forest ({self.run.job_key})"])
        page = self.client.get(reverse("run_comparison", args=[self.dataset.id]), selection)
        for row in page.context["comparison"]["rows"]:
            self.assertIn([row["label"], *row["display_values"]], rows)
        self.assertIn(["Accuracy", "74.33%", "81.23%"], rows)
        self.assertIn(["no", "yes", "2", "2"], rows)

    def test_csv_regression_has_numeric_values_without_percent_signs(self):
        for run in [self.run, self.second]:
            Run.objects.filter(pk=run.pk).update(run_config={**self.config, "algorithm": "linear_regression"},
                                                result=REGRESSION)
        rows = self.csv_rows(self.client.get(self.csv_url(), {"runs": [self.run.job_key, self.second.job_key]}))
        self.assertIn(["MAE", "0.00", "0.00"], rows)
        self.assertIn(["R²", "-0.25", "-0.25"], rows)

    def test_csv_rejects_invalid_selections_and_other_users(self):
        self.assertEqual(self.client.post(self.csv_url()).status_code, 405)
        for keys in [[], [self.run.job_key], [self.run.job_key, "unknown"]]:
            response = self.client.get(self.csv_url(), {"compare": "1", "runs": keys})
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("Content-Disposition", response)
        foreign = self.make_run("r-private-export", owner=self.other)
        self.assertEqual(self.client.get(self.csv_url(), {"runs": [self.run.job_key, foreign.job_key]}).status_code, 400)
        Run.objects.filter(pk=self.second.pk).update(state=Run.RUNNING)
        self.assertEqual(self.client.get(self.csv_url(), {"runs": [self.run.job_key, self.second.job_key]}).status_code, 400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.csv_url()).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.csv_url()).status_code, 302)

    def test_csv_protects_spreadsheet_formula_labels(self):
        for run in [self.run, self.second]:
            result = {**self.result, "labels": ["=1+1", "@SUM(A1)"]}
            Run.objects.filter(pk=run.pk).update(result=result)
        rows = self.csv_rows(self.client.get(self.csv_url(), {"runs": [self.run.job_key, self.second.job_key]}))
        self.assertIn(["'=1+1", "'@SUM(A1)", "2", "2"], rows)

    def test_results_and_comparison_pages_offer_download_links(self):
        response = self.client.get(reverse("run_detail", args=[self.run.job_key]))
        for format in ["html", "pdf"]:
            self.assertContains(response, self.report_url(format))
        response = self.client.get(reverse("run_comparison", args=[self.dataset.id]),
                                   {"runs": [self.run.job_key, self.second.job_key]})
        self.assertContains(response, self.csv_url())

    def test_absent_config_is_not_reported_as_known_defaults_or_empty_features(self):
        config = {"algorithm": "random_forest", "target_column": "bought"}
        Run.objects.filter(pk=self.run.pk).update(run_config=config, result=CLASSIFICATION)
        response = self.client.get(self.report_url())
        self.assertNotContains(response, "Algorithm defaults requested")
        self.assertContains(response, "Not recorded for this run")
        self.assertNotContains(response, "[]")

    def test_csv_includes_zero_only_class_inventory(self):
        result = {**self.result, "labels": ["no", "yes", "never-seen"],
                  "confusion_matrix": [[8, 2, 0], [3, 7, 0], [0, 0, 0]]}
        for run in [self.run, self.second]:
            Run.objects.filter(pk=run.pk).update(result=result)
        rows = self.csv_rows(self.client.get(self.csv_url(), {"runs": [self.run.job_key, self.second.job_key]}))
        self.assertIn([self.run.job_key, "2", "never-seen"], rows)
        self.assertIn([self.second.job_key, "2", "never-seen"], rows)

    def test_pdf_preserves_unsupported_unicode_as_explicit_lossless_escapes(self):
        self.dataset.original_name = "₹_中文_हिन्दी_😀.csv"
        self.dataset.save(update_fields=["original_name"])
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf")).content))
        text = "\n".join(page.extract_text() for page in document.pages)
        self.assertIn("\\u20b9", text)
        self.assertIn("\\u4e2d", text)
        self.assertIn("\\U0001f600", text)
        self.assertIn("Unicode escapes", text)

    def test_invalid_recorded_report_metadata_is_rejected(self):
        cases = [("bad", self.config),
                 ({"preprocessing": "bad"}, self.config),
                 ({"hyperparameters": "bad"}, self.config),
                 ({}, {**self.config, "hyperparameters": "bad"})]
        for execution, config in cases:
            with self.subTest(execution=execution, config=config):
                Run.objects.filter(pk=self.run.pk).update(run_config=config,
                    result={**self.result, "execution": execution})
                for format in ["html", "pdf"]:
                    response = self.client.get(self.report_url(format))
                    self.assertEqual(response.status_code, 409)

    def test_placeholder_reports_include_clear_disclaimer(self):
        Run.objects.filter(pk=self.run.pk).update(result={**self.result, "standin": True})
        self.assertContains(self.client.get(self.report_url()), "Placeholder baseline")
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf")).content))
        self.assertIn("Placeholder baseline", "\n".join(page.extract_text() for page in document.pages))

    @override_settings(STANDIN_RUN_SYNC=True)
    def test_real_training_snapshots_effective_configuration_for_reports(self):
        from .standins import runs
        key = runs.start(self.user, self.dataset, self.config)
        run = Run.objects.get(job_key=key)
        self.assertEqual(run.state, Run.COMPLETED)
        self.assertEqual(run.result["execution"]["hyperparameters"]["n_estimators"], 100)
        self.assertIn("training-set median", run.result["execution"]["preprocessing"]["imputation"])
        self.assertContains(self.client.get(self.report_url(run=run)), "One-hot encoding")

    def test_default_client_report_has_business_metrics_without_internal_details(self):
        response = self.client.get(self.report_url(detailed=False))
        for value in ["Evaluation report", "Random Forest", "bought", "data.csv", "81.23%", "age",
                      "Fields used", "Prediction breakdown"]:
            self.assertContains(response, value)
        for value in ["Dataset ID", "Random seed", "hyperparameters", "Requested imputation",
                      "Not recorded for this run", "Stored value", "0.8123456789", str(self.dataset.id)]:
            self.assertNotContains(response, value)

    def test_default_client_pdf_is_one_page_and_contains_only_summary_details(self):
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf", detailed=False)).content))
        self.assertEqual(len(document.pages), 1)
        text = document.pages[0].extract_text()
        for value in ["Evaluation report", "Random Forest", "81.23%", "Fields used", "bought"]:
            self.assertIn(value, text)
        for value in ["hyperparameters", "Dataset ID", "Random seed", "0.8123456789"]:
            self.assertNotIn(value, text)

    def test_client_report_keeps_large_classification_results_concise(self):
        labels = [f"class-{i}" for i in range(45)]
        matrix = [[0] * 45 for _ in labels]
        matrix[44][43] = 7
        Run.objects.filter(pk=self.run.pk).update(result={**self.result, "labels": labels, "confusion_matrix": matrix})
        response = self.client.get(self.report_url(detailed=False))
        self.assertNotContains(response, "class-44")
        self.assertContains(response, "technical report")
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf", detailed=False)).content))
        self.assertEqual(len(document.pages), 1)

    def test_client_regression_report_uses_error_units_not_percentages(self):
        Run.objects.filter(pk=self.run.pk).update(run_config={**self.config, "algorithm": "linear_regression"},
                                                result=REGRESSION)
        document = PdfReader(io.BytesIO(self.client.get(self.report_url("pdf", detailed=False)).content))
        text = "\n".join(page.extract_text() for page in document.pages)
        self.assertIn("Average absolute error", text)
        self.assertIn("-0.25", text)
        self.assertNotIn("%", text)
        self.assertNotIn("Prediction breakdown", text)

    def test_csv_headers_identify_models_in_selected_order_for_both_tasks(self):
        cases = [
            ('classification', CLASSIFICATION, 'random_forest', 'decision_tree', 'Random Forest', 'Decision Tree'),
            ('regression', REGRESSION, 'linear_regression', 'random_forest_regressor', 'Linear Regression', 'Random Forest Regressor'),
        ]
        for task, result, first, second, first_label, second_label in cases:
            with self.subTest(task=task):
                for run, algorithm in [(self.run, first), (self.second, second)]:
                    Run.objects.filter(pk=run.pk).update(run_config={**self.config, 'algorithm': algorithm}, result=result)
                response = self.client.get(self.csv_url(), {'runs': [self.second.job_key, self.run.job_key]})
                rows = self.csv_rows(response)
                expected = [f'{second_label} ({self.second.job_key})', f'{first_label} ({self.run.job_key})']
                self.assertEqual(rows[0], ['Metric', *expected])
                if task == 'classification':
                    self.assertIn(['Actual class', 'Predicted class', *expected], rows)
                else:
                    self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
                    self.assertIn(['R²', '-0.25', '-0.25'], rows)

    def test_technical_field_lists_are_readable_in_html_and_pdf(self):
        from .reporting import build_report
        cases = [(['age', 'city'], [], 'age, city', 'None'),
                 (['age'], ['city'], 'age', 'city')]
        for features, excluded, expected_features, expected_excluded in cases:
            with self.subTest(features=features):
                self.run.run_config = {**self.config, 'feature_columns': features, 'excluded_columns': excluded}
                self.run.save(update_fields=['run_config'])
                config_rows = dict(next(s for s in build_report(self.run, detailed=True)['sections']
                                        if s['title'] == 'Run configuration')['rows'])
                self.assertEqual(config_rows['Features'], expected_features)
                self.assertEqual(config_rows['Excluded columns'], expected_excluded)
                html = self.client.get(self.report_url())
                self.assertContains(html, f'<th scope="row">Features</th><td>{expected_features}</td>', html=True)
                self.assertContains(html, f'<th scope="row">Excluded columns</th><td>{expected_excluded}</td>', html=True)
                pdf = PdfReader(io.BytesIO(self.client.get(self.report_url('pdf')).content))
                text = '\n'.join(page.extract_text() for page in pdf.pages)
                self.assertIn(expected_features, text)
                self.assertIn(expected_excluded, text)
                self.assertNotIn('["age"', text)
                self.assertNotIn('[]', text)

    def test_run_page_metrics_match_report_formatting_for_both_tasks(self):
        cases = [('random_forest', CLASSIFICATION, ['81.23%', '80.00%', '75.00%', '77.00%']),
                 ('linear_regression', {**REGRESSION, 'mae': 5.7358}, ['5.74', '0.25', '0.50', '-0.25'])]
        for algorithm, result, expected in cases:
            with self.subTest(algorithm=algorithm):
                Run.objects.filter(pk=self.run.pk).update(run_config={**self.config, 'algorithm': algorithm}, result=result)
                response = self.client.get(reverse('run_detail', args=[self.run.job_key]))
                report = self.client.get(self.report_url(detailed=False))
                for value in expected:
                    self.assertContains(response, f'<td class="num">{value}</td>')
                    self.assertContains(report, value)
                self.assertNotContains(response, '0.8123</td>')
                self.assertNotContains(response, '5.7358</td>')

    def test_failed_run_has_no_report_links_and_rejects_all_report_variants(self):
        Run.objects.filter(pk=self.run.pk).update(state=Run.FAILED, error='Training could not finish.')
        run_page = self.client.get(reverse('run_detail', args=[self.run.job_key]))
        for format in ['html', 'pdf']:
            for detailed in [False, True]:
                url = self.report_url(format, detailed=detailed)
                self.assertEqual(self.client.get(url).status_code, 409)
                self.assertNotContains(run_page, url)

    def test_run_metric_formatting_does_not_turn_missing_scores_into_zero(self):
        from .templatetags.metric_format import metric_display
        for value in [None, "bad", True, float("nan"), float("inf"), 10 ** 400]:
            with self.subTest(value=str(value)[:20]):
                self.assertEqual(metric_display(value, "classification"), "—")
        self.assertEqual(metric_display(0, "classification"), "0.00%")
        self.assertEqual(metric_display(0, "regression"), "0.00")
