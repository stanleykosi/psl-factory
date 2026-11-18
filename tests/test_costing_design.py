from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.identity.models import Grant
from tests.costing_helpers import fixture, run


class CostingDesignTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = fixture()
        cls.costing_run = run(cls.data)

    def test_rule_and_examples_render_saved_facts_with_structured_reads_retained(self):
        data = self.data
        self.client.force_login(data['actor'])
        for kind, record in [('rule', data['rule']), ('oracle', data['oracle'])]:
            url = reverse('costing_source', args=[data['case'].pk, kind, record.pk])
            self.assertEqual(self.client.get(url).json()['payload'], record.payload)
            page = self.client.get(url + '?view=page')
            self.assertEqual(page.status_code, 200)
            self.assertEqual(page['Cache-Control'], 'no-store')
            self.assertContains(page, 'Source owners')
            if kind == 'rule':
                self.assertContains(page, 'Prices and parameters')
                self.assertContains(page, 'How the total is calculated')
            else:
                self.assertContains(page, 'Expected result')
                self.assertContains(page, 'Rule result')
                self.assertContains(page, 'Matches')
        Grant.objects.filter(case=data['case'], user=data['actor'], action='costing.source.read').update(active=False)
        for kind, record in [('rule', data['rule']), ('oracle', data['oracle'])]:
            url = reverse('costing_source', args=[data['case'].pk, kind, record.pk]) + '?view=page'
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_calculation_and_workbench_hide_amounts_without_source_access(self):
        data = self.data
        self.client.force_login(data['actor'])
        url = reverse('costing_report', args=[data['case'].pk, self.costing_run.pk])
        self.assertEqual(self.client.get(url).json()['result'], self.costing_run.result)
        self.assertContains(self.client.get(url + '?view=page'), '20.00')
        home = reverse('costing', args=[data['case'].pk])
        self.assertContains(self.client.get(home), '?view=page')
        Grant.objects.filter(case=data['case'], user=data['actor'], action='costing.source.read').update(active=False)
        self.assertNotContains(self.client.get(url + '?view=page'), '20.00')
        self.assertNotContains(self.client.get(home), '20.00')


class CostingDesignTemplateTests(SimpleTestCase):
    def test_readable_costing_templates_compile(self):
        from django.template.loader import get_template

        for template in ['pmo/costing.html', 'pmo/costing_source.html', 'pmo/costing_report.html']:
            self.assertIsNotNone(get_template(template))
