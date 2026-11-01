from types import SimpleNamespace

from django.test import SimpleTestCase

from .charts import comparison_chart


class ChartTests(SimpleTestCase):
    def comparison(self, task, key, values):
        return {"task": task,
                "columns": [{"algorithm": SimpleNamespace(label=f"Model {i}"),
                             "run": SimpleNamespace(job_key=f"r-{i}")} for i in range(len(values))],
                "rows": [{"key": key, "label": key.upper(), "values": [str(v) for v in values],
                          "display_values": [str(v) for v in values]}]}

    def test_classification_uses_fixed_percentage_scale_and_highest_score(self):
        chart = comparison_chart(self.comparison("classification", "accuracy", [.725, .8]))
        self.assertEqual([bar["width"] for bar in chart["bars"]], ["72.50", "80.00"])
        self.assertTrue(chart["higher"])
        self.assertEqual(chart["leaders"], "Model 1")
        self.assertEqual(chart["zero"], "0.00")

    def test_regression_errors_favor_lower_values(self):
        chart = comparison_chart(self.comparison("regression", "rmse", [4, 2]))
        self.assertFalse(chart["higher"])
        self.assertEqual(chart["leaders"], "Model 1")
        self.assertEqual(chart["bars"][1]["width"], "50.00")

    def test_negative_r2_bars_have_correct_zero_and_direction(self):
        chart = comparison_chart(self.comparison("regression", "r2", [-.5, .25]), "r2")
        self.assertTrue(chart["higher"])
        self.assertEqual(chart["zero"], "66.67")
        self.assertEqual(chart["bars"][0]["left"], "0.00")
        self.assertEqual(chart["bars"][1]["left"], "66.67")
        self.assertEqual(chart["bars"][0]["width"], "66.67")

    def test_zero_scores_ties_and_invalid_metric_are_safe(self):
        chart = comparison_chart(self.comparison("classification", "accuracy", [0, 0]), "unsafe")
        self.assertEqual(chart["metric"], "accuracy")
        self.assertTrue(chart["tied"])
        self.assertEqual(chart["leaders"], "Model 0, Model 1")
        self.assertEqual(chart["bars"][0]["width"], "0.00")
        self.assertIsNone(comparison_chart(None))
