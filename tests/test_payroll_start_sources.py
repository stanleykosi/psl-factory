from copy import deepcopy
import json

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.finance import hrfinance, payroll
from apps.finance.models import PayrollRun
from apps.identity.models import Grant
from apps.workflows import factory_payroll
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.payroll_helpers import capture, fixture


class PayrollStartSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sample = fixture()

    def setup_paths(self):
        self.case = self.sample['case']
        self.path = reverse('factory_create')
        self.get_url = f'{self.path}?definition={factory_payroll.DEFINITION}&case={self.case.pk}'

    def options(self, response, field):
        return set(response.context['inputs_form'].fields[field].queryset.values_list('pk', flat=True))

    def submit(self, inputs, snapshot):
        return self.client.post(self.path, {
            'definition': factory_payroll.DEFINITION, 'case': self.case.pk,
            'key': 'sample-restricted-payroll-start', 'reference': 'Sample exact payroll start',
            'revision': rev(self.case), 'request_id': self.sample['request'].pk,
            'input_ids': [source.pk for source in inputs], 'hr_snapshot_id': snapshot.pk,
        })

    def test_case_grants_without_current_source_nomination_show_no_choices(self):
        self.setup_paths()
        account = get_user_model().objects.create_user(username='sample-non-nominated-payroll-start')
        Grant.objects.bulk_create([Grant(case=self.case, user=account, action=action) for action in
                                  ('case.read', 'factory.start', 'payroll.read', 'payroll.private.read', 'evidence.add',
                                   'hrfinance.read', 'hrfinance.snapshot.read')])
        self.client.force_login(account)
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(self.get_url)
        self.assertNotContains(page, 'staff-costs', status_code=403)
        self.assertTrue(all('finance_payrollinput' not in sql['sql'] and 'finance_hrreadsnapshot' not in sql['sql']
                            for sql in queries.captured_queries))
        self.assertEqual(self.submit(self.sample['inputs'], self.sample['hr']).status_code, 403)
        self.assertFalse(FactoryWork.objects.filter(case=self.case).exists())

    def test_only_current_exact_sources_and_nominated_hr_snapshot_reach_intake(self):
        self.setup_paths()
        sample, case = self.sample, self.case
        maker, owner, reviewer = sample['preparer'], sample['owner'], sample['reviewer']
        original = sample['inputs'][0]
        newest = capture(sample, 0, 'start-new-provider-version', source_version='A-v2')
        foreign_request = payroll.request(maker, case.pk, 'outside-approved-entity',
            {**sample['request'].metadata, 'entity': 'different-entity'}, sample['e']['payroll_need'].pk, rev(case))

        replacement_need = {**sample['hr_config']['need'], 'recipient_ids': [reviewer.pk]}
        other_need = hrfinance.need(maker, case.pk, 'separate-nominated-payroll-hr', replacement_need,
                                   sample['e']['hr_finance_need'].pk, rev(case))
        other_contract = hrfinance.contract(maker, case.pk, other_need.pk, 'separate-start-contract',
                                           sample['e']['hr_contract_source'].pk, rev(case))
        hrfinance.decide(owner, case.pk, other_contract.pk, 'approve', 'separate-start-approval',
                         sample['e']['hr_disclosure_decision'].pk, rev(case))
        other_snapshot = hrfinance.capture(owner, case.pk, other_contract.pk, 'separate-start-snapshot',
                                           json.dumps(deepcopy(sample['hr_config']['export'])), rev(case))

        self.client.force_login(maker)
        earlier_revision = rev(case)
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(self.get_url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(rev(case), earlier_revision)
        self.assertEqual(self.options(page, 'request_id'), {sample['request'].pk})
        self.assertEqual(self.options(page, 'input_ids'), {newest.pk, sample['inputs'][1].pk})
        self.assertEqual(self.options(page, 'hr_snapshot_id'), {sample['hr'].pk})
        self.assertNotContains(page, str(foreign_request))
        self.assertNotContains(page, str(original))
        self.assertNotContains(page, str(other_snapshot))
        self.assertNotContains(page, 'E001')
        for query in queries.captured_queries:
            select = query['sql'].split(' FROM ', 1)[0]
            self.assertNotRegex(select, r'"finance_(payrollinput|hrreadsnapshot)"\."payload"(?=\s*(?:,|$))')

        declined = self.submit([newest, sample['inputs'][1]], other_snapshot)
        self.assertContains(declined, 'Select a valid choice')
        declined = self.submit(sample['inputs'], sample['hr'])
        self.assertContains(declined, 'Select a valid choice')
        self.assertFalse(FactoryWork.objects.filter(case=case).exists())

        Grant.objects.filter(case=case, user=maker, action='hrfinance.snapshot.read').update(active=False)
        page = self.client.get(self.get_url)
        self.assertEqual(self.options(page, 'hr_snapshot_id'), set())
        self.assertContains(self.submit([newest, sample['inputs'][1]], sample['hr']), 'Select a valid choice')
        Grant.objects.filter(case=case, user=maker, action='hrfinance.snapshot.read').update(active=True)
        response = self.submit([newest, sample['inputs'][1]], sample['hr'])
        work = FactoryWork.objects.get(case=case, actor=maker, definition=factory_payroll.DEFINITION)
        self.assertRedirects(response, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        selected, source = factory_payroll.source(work, maker)
        self.assertEqual(selected.pk, sample['request'].pk)
        self.assertEqual(source['inputs'], {'input_ids': sorted((newest.pk, sample['inputs'][1].pk)),
                                             'hr_snapshot_id': sample['hr'].pk})
        self.assertFalse(PayrollRun.objects.filter(request__case=case).exists())
