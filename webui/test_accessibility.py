"""Issue #22: rendered workflow semantics; real keyboard trials are recorded separately."""
from html.parser import HTMLParser

from django.urls import reverse

from .models import Run
from .test_comparison import CLASSIFICATION
from .tests import WebUITestCase


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def by_id(self, value):
        return next(attrs for _, attrs in self.elements if attrs.get('id') == value)


class AccessibilityTests(WebUITestCase):
    def setUp(self):
        super().setUp()
        self.dataset = self.make_dataset()

    def elements(self, response):
        return Elements(response.content.decode())

    def assert_descriptions_exist(self, response):
        elements = self.elements(response)
        ids = {attrs.get('id') for _, attrs in elements.elements}
        for _, attrs in elements.elements:
            for reference in attrs.get('aria-describedby', '').split():
                self.assertIn(reference, ids, f'Description {reference} is missing')

    def test_skip_link_has_a_focusable_main_destination(self):
        page = self.client.get(reverse('dataset_list'))
        self.assertEqual(self.elements(page).by_id('main').get('tabindex'), '-1')

    def test_upload_error_is_programmatically_associated_with_file_control(self):
        page = self.client.post(reverse('dataset_new'), {})
        control = self.elements(page).by_id('id_file')
        self.assertEqual(control.get('aria-invalid'), 'true')
        self.assertIn('id_file_error', control.get('aria-describedby', '').split())
        self.assert_descriptions_exist(page)

    def test_pipeline_and_model_errors_have_existing_descriptions(self):
        page = self.client.post(reverse('pipeline_step', args=[self.dataset.pk]), {})
        self.assert_descriptions_exist(page)
        session = self.client.session
        session[f'draft-{self.dataset.pk}'] = {'target_column': 'bought', 'feature_columns': ['age']}
        session.save()
        page = self.client.post(reverse('model_step', args=[self.dataset.pk]), {'algorithm': 'invalid'})
        self.assert_descriptions_exist(page)
        algorithm = self.elements(page).by_id('id_algorithm')
        self.assertIn('id_algorithm_error', algorithm.get('aria-describedby', '').split())
        self.assertIn('algorithm-help', algorithm.get('aria-describedby', '').split())

    def test_comparison_error_focus_summary_links_to_selection_group(self):
        Run.objects.create(owner=self.user, dataset=self.dataset, job_key='r-a11y', state=Run.COMPLETED,
                           run_config={'algorithm': 'random_forest', 'target_column': 'bought'}, result=CLASSIFICATION)
        page = self.client.get(reverse('run_comparison', args=[self.dataset.pk]), {'compare': '1'})
        elements = self.elements(page)
        self.assertEqual(elements.by_id('error-summary').get('tabindex'), '-1')
        self.assertEqual(elements.by_id('run-selection').get('tabindex'), '-1')
        self.assertContains(page, 'href="#run-selection"')
        self.assert_descriptions_exist(page)

    def test_workflow_pages_keep_one_current_stage_in_the_correct_order(self):
        session = self.client.session
        session[f'draft-{self.dataset.pk}'] = {'target_column': 'bought', 'feature_columns': ['age'],
                                             'algorithm': 'random_forest'}
        session.save()
        run = Run.objects.create(owner=self.user, dataset=self.dataset, job_key='r-stage', state=Run.COMPLETED,
                                 run_config={'algorithm': 'random_forest', 'target_column': 'bought'}, result=CLASSIFICATION)
        pages = [(reverse('dataset_new'), 'Dataset'),
                 (reverse('pipeline_step', args=[self.dataset.pk]), 'Pipeline'),
                 (reverse('model_step', args=[self.dataset.pk]), 'Model'),
                 (reverse('settings_summary', args=[self.dataset.pk]), 'Model'),
                 (reverse('run_detail', args=[run.job_key]), 'Results')]
        for url, stage in pages:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                current = [attrs for _, attrs in Elements(html).elements if attrs.get('aria-current') == 'step']
                self.assertEqual(len(current), 1)
                labels = [html.index(f'{i}. {label}') for i, label in enumerate(
                    ['Dataset', 'Pipeline', 'Model', 'Run', 'Results'], 1)]
                self.assertEqual(labels, sorted(labels))
                self.assertRegex(html, rf'aria-current="step"[^>]*>\s+\d\. {stage}')

    def test_classification_results_explain_accuracy_in_plain_words(self):
        run = Run.objects.create(owner=self.user, dataset=self.dataset, job_key='r-explain', state=Run.COMPLETED,
                                 run_config={'algorithm': 'random_forest', 'target_column': 'bought'}, result=CLASSIFICATION)
        page = self.client.get(reverse('run_detail', args=[run.job_key]))
        self.assertContains(page, 'Accuracy is the share of held-out predictions that were correct.')

    def test_chart_describes_a_real_numeric_equivalent(self):
        for key in ['r-chart-a', 'r-chart-b']:
            Run.objects.create(owner=self.user, dataset=self.dataset, job_key=key, state=Run.COMPLETED,
                               run_config={'algorithm': 'random_forest', 'target_column': 'bought'}, result=CLASSIFICATION)
        page = self.client.get(reverse('run_comparison', args=[self.dataset.pk]),
                               {'runs': ['r-chart-a', 'r-chart-b']})
        elements = self.elements(page)
        chart = next(attrs for _, attrs in elements.elements if attrs.get('role') == 'img')
        self.assertEqual(chart.get('aria-describedby'), 'comparison-values')
        table = next(tag for tag, attrs in elements.elements if attrs.get('id') == 'comparison-values')
        self.assertEqual(table, 'table')
        self.assertContains(page, '<td class="num">81.23%</td>')

    def test_sign_in_errors_are_associated_with_both_controls(self):
        self.client.logout()
        page = self.client.post(reverse('login'), {'username': 'unknown', 'password': 'wrong'})
        elements = self.elements(page)
        for field in ['id_username', 'id_password']:
            self.assertEqual(elements.by_id(field).get('aria-invalid'), 'true')
            self.assertIn('error-summary', elements.by_id(field).get('aria-describedby', '').split())
        self.assert_descriptions_exist(page)

    def test_registration_errors_and_help_are_associated_with_controls(self):
        self.client.logout()
        page = self.client.post(reverse('register'), {})
        self.assertEqual(self.elements(page).by_id('error-summary').get('tabindex'), '-1')
        self.assert_descriptions_exist(page)
        for tag, attrs in self.elements(page).elements:
            if tag == 'input' and 'required' in attrs:
                self.assertEqual(attrs.get('aria-invalid'), 'true')
