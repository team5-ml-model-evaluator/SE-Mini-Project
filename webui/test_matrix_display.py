"""Regression tests: large confusion matrices must not exhaust the results page."""
from copy import deepcopy

from django.urls import reverse
from django.db import connection
from django.test.utils import CaptureQueriesContext

from .models import Run
from .test_comparison import CLASSIFICATION
from .tests import WebUITestCase


class MatrixDisplayTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()
        self.result = {**deepcopy(CLASSIFICATION),
                       "labels": [f"class-{i}" for i in range(45)],
                       "confusion_matrix": [[r * 45 + c for c in range(45)] for r in range(45)]}
        self.run = Run.objects.create(
            job_key="r-many-classes", owner=self.user, dataset=self.dataset,
            state=Run.COMPLETED, run_config={"algorithm": "random_forest", "target_column": "bought"},
            result=self.result,
        )
        self.url = reverse("run_detail", args=[self.run.job_key])

    def test_large_matrix_page_is_bounded_and_explains_pagination(self):
        response = self.client.get(self.url)
        self.assertContains(response, "45 classes")
        self.assertContains(response, "Rows 1–20")
        self.assertEqual(len(response.context["matrix"]), 20)
        self.assertEqual(len(response.context["labels"]), 20)
        self.assertEqual(sum(len(row["cells"]) for row in response.context["matrix"]), 400)
        self.assertContains(response, "Next actual classes")
        self.assertContains(response, "Next predicted classes")
        self.assertLess(len(response.content), 100_000)

    def test_independent_row_and_column_pages_preserve_stored_values(self):
        response = self.client.get(self.url, {"matrix_row": "2", "matrix_col": "3"})
        self.assertEqual(response.context["matrix"][0]["label"], "class-20")
        self.assertEqual(response.context["labels"], self.result["labels"][40:45])
        self.assertEqual(response.context["matrix"][0]["cells"][0],
                         {"value": self.result["confusion_matrix"][20][40], "correct": False})
        self.assertContains(response, "Previous actual classes")
        self.assertContains(response, "Previous predicted classes")
        self.assertNotContains(response, "Next predicted classes")
        diagonal = self.client.get(self.url, {"matrix_row": "3", "matrix_col": "3"})
        self.assertTrue(diagonal.context["matrix"][0]["cells"][0]["correct"])
        self.run.refresh_from_db()
        self.assertEqual(self.run.result, self.result)

    def test_invalid_page_parameters_are_safe_and_clamped(self):
        for page in ["bad", "-1", "0", "9" * 5000]:
            with self.subTest(page=page[:20]):
                response = self.client.get(self.url, {"matrix_row": page, "matrix_col": page})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["matrix"][0]["label"], "class-0")
        response = self.client.get(self.url, {"matrix_row": "999", "matrix_col": "999"})
        self.assertEqual(response.context["matrix"][0]["label"], "class-40")

    def test_comparison_uses_bounded_preview_and_links_to_full_matrix(self):
        other = Run.objects.create(job_key="r-many-classes-2", owner=self.user, dataset=self.dataset,
                                   state=Run.COMPLETED, run_config=self.run.run_config, result=self.result)
        response = self.client.get(reverse("run_comparison", args=[self.dataset.id]),
                                   {"runs": [self.run.job_key, other.job_key]})
        self.assertContains(response, "Showing the first 20 of 45 classes")
        self.assertContains(response, "Browse full matrix")
        for column in response.context["comparison"]["columns"]:
            self.assertEqual(len(column["matrix_rows"]), 20)
            self.assertEqual(len(column["labels"]), 20)
            self.assertEqual(column["matrix_rows"][0]["values"], self.result["confusion_matrix"][0][:20])
        self.assertLess(len(response.content), 100_000)

    def test_run_choices_and_status_do_not_load_large_results(self):
        response = self.client.get(reverse("run_comparison", args=[self.dataset.id]))
        choice = response.context["form"].fields["runs"].queryset.first()
        self.assertIn("result", choice.get_deferred_fields())
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("run_status", args=[self.run.job_key]))
        self.assertEqual(response.json()["state"], Run.COMPLETED)
        run_reads = [query["sql"] for query in queries if 'FROM "webui_run"' in query["sql"]]
        self.assertTrue(run_reads)
        for sql in run_reads:
            self.assertNotIn('"webui_run"."result"', sql)
