"""UI tests for issue #18: upload, target/feature and model forms (MLE-F-010, F-020, F-030)."""
import re
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Dataset
from .standins.catalogue import ALGORITHMS

User = get_user_model()
TMP_MEDIA = tempfile.mkdtemp(prefix="mle-test-")


def make_csv(rows=25, extra_header="", width=3):
    header = ["age", "city", "bought"][:width]
    lines = [",".join(header)]
    for i in range(rows):
        lines.append(",".join([str(20 + i), f"City{i % 3}", str(i % 2)][:width]))
    return ("\n".join(lines) + "\n" + extra_header).encode()


def upload(client, content, name="data.csv"):
    return client.post(reverse("dataset_new"), {"file": SimpleUploadedFile(name, content)})


@override_settings(MEDIA_ROOT=TMP_MEDIA, PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WebUITestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pw-for-tests")
        self.other = User.objects.create_user("bob", password="pw-for-tests")
        self.client.force_login(self.user)

    def make_dataset(self, owner=None):
        response = upload(self.client, make_csv())
        self.assertEqual(response.status_code, 302)
        return Dataset.objects.latest("created_at")

    def assert_labelled(self, html):
        """Every visible control has a text label that points at it (MLE-NF-004)."""
        controls = re.findall(r"<(?:input|select|textarea)\b[^>]*>", html)
        for tag in controls:
            if 'type="hidden"' in tag or 'type="submit"' in tag:
                continue
            control_id = re.search(r'\bid="([^"]+)"', tag)
            self.assertIsNotNone(control_id, f"control without id: {tag}")
            self.assertRegex(html, rf'<label[^>]*for="{re.escape(control_id.group(1))}"', tag)
            self.assertNotRegex(tag, r'tabindex="[1-9]')  # nothing jumps the natural tab order


class UploadFormTests(WebUITestCase):
    def test_login_is_required(self):
        self.client.logout()
        response = self.client.get(reverse("dataset_new"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_form_has_a_labelled_file_control_and_stage_indicator(self):
        html = self.client.get(reverse("dataset_new")).content.decode()
        self.assertIn('type="file"', html)
        self.assert_labelled(html)
        self.assertIn('aria-current="step"', html)

    def test_valid_csv_is_stored_profiled_and_shown(self):
        response = upload(self.client, make_csv(rows=25), name="customers.csv")
        dataset = Dataset.objects.get()
        self.assertRedirects(response, reverse("dataset_detail", args=[dataset.id]))
        self.assertEqual((dataset.owner, dataset.rows, dataset.column_count), (self.user, 25, 3))
        self.assertEqual([c["dtype"] for c in dataset.profile["columns"]], ["integer", "text", "integer"])
        page = self.client.get(reverse("dataset_detail", args=[dataset.id])).content.decode()
        for name in ("age", "city", "bought"):
            self.assertIn(f">{name}</th>", page)

    def test_missing_values_are_profiled(self):
        content = make_csv(rows=20).replace(b"City1", b"")
        dataset_id = upload(self.client, content)
        self.assertEqual(dataset_id.status_code, 302)
        city = Dataset.objects.get().profile["columns"][1]
        self.assertGreater(city["missing_count"], 0)

    def assert_rejected(self, response, message_part):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "There is a problem")
        self.assertContains(response, message_part)
        self.assertEqual(Dataset.objects.count(), 0)  # nothing stored

    def test_no_file_chosen(self):
        response = self.client.post(reverse("dataset_new"), {})
        self.assert_rejected(response, "Choose a CSV file to upload.")

    def test_wrong_extension_is_rejected_with_the_fix(self):
        self.assert_rejected(upload(self.client, make_csv(), name="data.txt"), "name ends in .csv")

    def test_executable_renamed_to_csv_is_rejected(self):
        self.assert_rejected(upload(self.client, b"MZ\x90\x00\x03\x00\x00\x00" * 50), "binary data")

    def test_nineteen_rows_is_rejected(self):
        self.assert_rejected(upload(self.client, make_csv(rows=19)), "19 data rows")

    def test_exactly_twenty_rows_is_accepted(self):
        self.assertEqual(upload(self.client, make_csv(rows=20)).status_code, 302)

    def test_single_column_is_rejected(self):
        self.assert_rejected(upload(self.client, make_csv(rows=25, width=1)), "1 column")

    def test_uneven_rows_name_the_row(self):
        self.assert_rejected(upload(self.client, make_csv(rows=25) + b"1,2\n"), "Row 27 has 2 values")

    def test_duplicate_and_blank_column_names(self):
        dup = b"a,a\n" + b"1,2\n" * 25
        blank = b"a,\n" + b"1,2\n" * 25
        self.assert_rejected(upload(self.client, dup), "same name")
        self.assert_rejected(upload(self.client, blank), "has no name")

    def test_non_utf8_is_rejected(self):
        self.assert_rejected(upload(self.client, b"a,b\n" + "é,1\n".encode("latin-1") * 25), "UTF-8")

    def test_size_limit_message_states_limit_and_size(self):
        content = make_csv(rows=25)
        with override_settings(MAX_UPLOAD_BYTES=len(content) - 1):
            self.assert_rejected(upload(self.client, content), "the limit is 0 MB")
        with override_settings(MAX_UPLOAD_BYTES=len(content)):
            self.assertEqual(upload(self.client, content).status_code, 302)  # exactly at the limit

    def test_error_summary_links_to_the_field(self):
        response = upload(self.client, make_csv(rows=3))
        self.assertContains(response, 'href="#id_file"')
        self.assertContains(response, 'id="error-summary"')


class PipelineFormTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()
        self.url = reverse("pipeline_step", args=[self.dataset.id])

    def post(self, target, roles=("feature", "feature", "feature")):
        data = {"target": target}
        data.update({f"role_{i}": role for i, role in enumerate(roles)})
        return self.client.post(self.url, data)

    def test_lists_every_column_with_labelled_controls(self):
        html = self.client.get(self.url).content.decode()
        for name in ("age", "city", "bought"):
            self.assertIn(f"Use {name} as", html)
        self.assertEqual(html.count('type="radio"'), 6)
        self.assert_labelled(html)
        self.assertIn("Pipeline", re.search(r'aria-current="step">\s*([^<]+)', html).group(1))

    def test_valid_choice_saves_target_features_and_excluded(self):
        response = self.post("bought", ("feature", "excluded", "feature"))
        self.assertRedirects(response, reverse("model_step", args=[self.dataset.id]))
        draft = self.client.session[f"draft-{self.dataset.id}"]
        self.assertEqual(draft["target_column"], "bought")
        self.assertEqual(draft["feature_columns"], ["age"])
        self.assertEqual(draft["excluded_columns"], ["city"])

    def test_target_is_never_a_feature(self):
        self.post("bought", ("feature", "feature", "feature"))
        draft = self.client.session[f"draft-{self.dataset.id}"]
        self.assertNotIn("bought", draft["feature_columns"])

    def test_missing_target_is_explained(self):
        response = self.post("")
        self.assertContains(response, "Choose the column to predict.")
        self.assertContains(response, 'href="#id_target"')
        self.assertNotIn(f"draft-{self.dataset.id}", self.client.session)

    def test_unknown_target_is_refused(self):
        self.assertContains(self.post("nope"), "Choose the column to predict from the list.")

    def test_no_features_left_is_explained(self):
        response = self.post("bought", ("excluded", "excluded", "feature"))
        self.assertContains(response, "Mark at least one column other than the target as a feature")

    def test_missing_role_is_named(self):
        response = self.client.post(self.url, {"target": "bought", "role_0": "feature"})
        self.assertContains(response, "Mark “city” as a feature or excluded.")

    def test_revisiting_shows_saved_choices(self):
        self.post("bought", ("feature", "excluded", "feature"))
        html = self.client.get(self.url).content.decode()
        self.assertRegex(html, r'<option value="bought" selected>')
        self.assertRegex(html, r'value="excluded"[^>]*id="id_role_1_1"[^>]*checked|id="id_role_1_1"[^>]*checked')


class ModelFormTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()
        self.url = reverse("model_step", args=[self.dataset.id])

    def choose_columns(self):
        self.client.post(
            reverse("pipeline_step", args=[self.dataset.id]),
            {"target": "bought", "role_0": "feature", "role_1": "feature", "role_2": "feature"},
        )

    def test_requires_pipeline_choices_first(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("pipeline_step", args=[self.dataset.id]))

    def test_lists_five_classification_and_three_regression_algorithms(self):
        self.choose_columns()
        html = self.client.get(self.url).content.decode()
        self.assertIn('<optgroup label="Classification">', html)
        self.assertIn('<optgroup label="Regression">', html)
        for algorithm in ALGORITHMS:
            self.assertIn(f'value="{algorithm.key}"', html)
        self.assertEqual(len([a for a in ALGORITHMS if a.task == "classification"]), 5)
        self.assertEqual(len([a for a in ALGORITHMS if a.task == "regression"]), 3)
        self.assert_labelled(html)

    def test_choosing_an_algorithm_saves_it_and_shows_the_summary(self):
        self.choose_columns()
        response = self.client.post(self.url, {"algorithm": "random_forest"})
        self.assertRedirects(response, reverse("settings_summary", args=[self.dataset.id]))
        page = self.client.get(response["Location"]).content.decode()
        for text in ("bought", '<span class="chip">age</span>', '<span class="chip">city</span>', "Random Forest", "classification"):
            self.assertIn(text, page)

    def test_no_choice_and_invalid_choice_are_explained(self):
        self.choose_columns()
        self.assertContains(self.client.post(self.url, {}), "Choose an algorithm.")
        self.assertContains(self.client.post(self.url, {"algorithm": "xgboost"}), "Choose an algorithm from the list.")

    def test_summary_without_an_algorithm_goes_back(self):
        self.choose_columns()
        response = self.client.get(reverse("settings_summary", args=[self.dataset.id]))
        self.assertRedirects(response, self.url)


class OwnershipAndStageTests(WebUITestCase):
    def test_another_user_gets_403_on_every_dataset_page(self):
        dataset = self.make_dataset()
        bob = Client()
        bob.force_login(self.other)
        for name in ("dataset_detail", "pipeline_step", "model_step", "settings_summary"):
            response = bob.get(reverse(name, args=[dataset.id]))
            self.assertEqual(response.status_code, 403, name)
            self.assertNotIn(b"data.csv", response.content)

    def test_unknown_dataset_is_404(self):
        response = self.client.get(reverse("dataset_detail", args=["00000000-0000-0000-0000-000000000000"]))
        self.assertEqual(response.status_code, 404)

    def test_list_shows_only_own_datasets(self):
        self.make_dataset()
        bob = Client()
        bob.force_login(self.other)
        self.assertNotContains(bob.get(reverse("dataset_list")), "data.csv")

    def test_stage_indicator_marks_exactly_one_current_stage_in_workflow_order(self):
        dataset = self.make_dataset()
        self.client.post(
            reverse("pipeline_step", args=[dataset.id]),
            {"target": "bought", "role_0": "feature", "role_1": "feature", "role_2": "feature"},
        )
        expected = {"dataset_detail": "Dataset", "pipeline_step": "Pipeline", "model_step": "Model"}
        for name, label in expected.items():
            html = self.client.get(reverse(name, args=[dataset.id])).content.decode()
            order = re.findall(r"\d\. (Dataset|Pipeline|Model|Run|Results)", html)
            self.assertEqual(order, ["Dataset", "Pipeline", "Model", "Run", "Results"])
            self.assertEqual(html.count('aria-current="step"'), 1)
            self.assertRegex(html, rf'aria-current="step">\s*\d\. {label}')
            self.assertIn("(current stage)", html)  # shown to screen readers as text, not colour

    def test_csrf_is_enforced_on_forms(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        response = strict.post(reverse("dataset_new"), {"file": SimpleUploadedFile("a.csv", make_csv())})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Dataset.objects.count(), 0)

    def test_stored_file_has_a_random_name_in_a_per_user_folder(self):
        dataset = self.make_dataset()
        self.assertEqual(dataset.file.name, f"user-{self.user.id}/{dataset.id}.csv")
        self.assertNotIn("data.csv", dataset.file.name)
