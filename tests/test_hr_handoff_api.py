import json
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance.hrfinance_models import HRHandoffRecord, HRReadSnapshot
from apps.identity.models import Grant
from apps.policy.hrfinance_validators import SCOPE_ROUTE

from .helpers import rev
from .hrfinance_helpers import body, fixture


class HRHandoffAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = fixture()

    def setUp(self):
        self.case = self.f['case']
        self.url = f'/api/v1/projects/{self.case.pk}/hr-disclosures'
        self.contract = self.f['contract']

    def command(self, actor, action, expected=200, **fields):
        self.client.force_login(actor)
        response = self.client.post(self.url, {'action': action, 'revision': rev(self.case), **fields},
                                    content_type='application/json')
        self.assertEqual(response.status_code, expected, response.content)
        return response.json()

    def upload(self, actor, contract, key, data, expected=201):
        self.client.force_login(actor)
        response = self.client.post(f'{self.url}/{contract}/exports', {'revision': rev(self.case), 'operation_key': key,
            'file': SimpleUploadedFile('synthetic-hr-export.json', data.encode('utf-8'), 'application/json')})
        self.assertEqual(response.status_code, expected, response.content)
        return response.json()

    def test_source_owned_export_only_reaches_the_named_finance_recipient(self):
        finance, hr, proofs = (self.f[key] for key in ('finance', 'hr', 'e'))
        self.client.force_login(finance)
        options = self.client.get(self.url).json()
        self.assertIn('need', options['actions'])
        self.assertNotIn('capture', options['actions'])
        self.assertNotIn('private-staff-001', json.dumps(options))

        need = self.command(finance, 'need', reference='parallel-disclosure', need=self.f['config']['need'],
                            evidence_id=proofs['hr_finance_need'].pk)['record_id']
        contract = self.command(finance, 'contract', need_id=need, operation_key='contract-api',
                                evidence_id=proofs['hr_contract_source'].pk)['record_id']
        decision = {'contract_id': contract, 'evidence_id': proofs['hr_disclosure_decision'].pk}
        self.command(hr, 'authorize', verdict='return', operation_key='returned-api', **decision)
        self.upload(hr, contract, 'before-approval', body(self.f), expected=422)
        self.command(hr, 'authorize', verdict='approve', operation_key='approved-api', **decision)
        self.upload(finance, contract, 'outside-authority', body(self.f), expected=403)
        original = self.upload(hr, contract, 'original-api', body(self.f))
        snapshot = original['snapshot_id']
        self.assertEqual(original['status'], 'accepted')
        rows_url = f'{self.url}/snapshots/{snapshot}/rows'
        self.assertEqual(self.client.get(rows_url).status_code, 403)
        outsider = get_user_model().objects.create_user('synthetic-hr-read-only-api')
        Grant.objects.bulk_create(Grant(case=self.case, user=outsider, action=action)
                                  for action in ('case.read', 'hrfinance.read', 'hrfinance.snapshot.read'))
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(rows_url).status_code, 403)

        self.client.force_login(finance)
        rows = self.client.get(rows_url)
        self.assertEqual(rows.status_code, 200, rows.content)
        self.assertEqual(rows.json()['rows'][0]['employee_id'], 'private-staff-001')
        self.assertContains(self.client.get(reverse('hrfinance_snapshot', args=[self.case.pk, snapshot])), 'private-staff-001')
        proof = proofs['hr_disclosure_decision'].pk
        receipt = self.command(finance, 'receive', snapshot_id=snapshot, operation_key='read-receipt', evidence_id=proof)
        correction = self.command(finance, 'correction', snapshot_id=snapshot, operation_key='request-correction',
                                  evidence_id=proofs['hr_correction_request'].pk)
        fixed_rows = deepcopy(self.f['config']['export']['rows'])
        fixed_rows[0]['bu'] = 'beta'
        fixed = self.upload(hr, contract, 'corrected-api', body(self.f, rows=fixed_rows, source_version='api-v2'))['snapshot_id']
        response = self.command(hr, 'decide_correction', request_id=correction['record_id'], verdict='approve',
                                successor_id=fixed, operation_key='hreplied', evidence_id=proofs['hr_correction_response'].pk)
        self.assertEqual(HRHandoffRecord.objects.get(pk=response['record_id']).snapshot_id, fixed)
        self.command(finance, 'receive', snapshot_id=fixed, operation_key='successor-receipt', evidence_id=proof)
        self.assertEqual(self.client.get(rows_url).status_code, 409)
        review = self.client.get(f'{self.url}/{contract}')
        self.assertEqual(review.status_code, 200, review.content)
        self.assertNotContains(review, 'private-staff-001')
        self.assertEqual([row['verdict'] for row in review.json()['decisions']], ['approve', 'return'])
        by_snapshot = {row['id']: row for row in review.json()['snapshots']}
        self.assertEqual(by_snapshot[snapshot]['receipt_id'], receipt['record_id'])
        self.assertEqual(review.json()['corrections'][0]['successor_id'], fixed)

    def test_rejected_export_only_creates_a_typed_scope_question(self):
        hr, finance, proofs = (self.f[key] for key in ('hr', 'finance', 'e'))
        version = self.command(hr, 'draft_policy', policy={'component': SCOPE_ROUTE, 'content': {
            'owner_id': hr.pk, 'action': 'confirm_minimum_scope', 'question_version': 1,
            'disclosure': 'codes_and_source_identity_only'}}, evidence_id=proofs['owner'].pk,
            effective_from=(timezone.now() - timedelta(seconds=1)).isoformat())['record_id']
        from apps.policy.services import transition
        transition(hr, version, 'validated')
        transition(hr, version, 'active')
        invalid = json.loads(body(self.f))
        invalid['rows'][0]['medical'] = 'SYNTHETIC-EXCLUDED-FIELD'
        rejected = self.upload(hr, self.contract.pk, 'reject-outside-scope', json.dumps(invalid))
        self.assertEqual(rejected['findings'], ['out_of_contract_fields'])
        self.assertEqual(HRReadSnapshot.objects.get(pk=rejected['snapshot_id']).payload, {})
        task = self.command(hr, 'scope_request', snapshot_id=rejected['snapshot_id'])['record_id']
        url = f'{self.url}/clarifications/{task}'
        self.client.force_login(finance)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(hr)
        question = self.client.get(url)
        self.assertEqual(question.status_code, 200, question.content)
        self.assertTrue(question.json()['can_reply'])
        self.assertNotContains(question, 'SYNTHETIC-EXCLUDED-FIELD')
        self.command(hr, 'scope_reply', task_id=task, task_revision=question.json()['revision'], reply='minimum_scope_confirmed')
        self.assertEqual(self.client.get(url).json()['status'], 'await_proper_minimal_resubmission')
        self.assertFalse(HRHandoffRecord.objects.filter(snapshot_id=rejected['snapshot_id'], kind='receipt').exists())
