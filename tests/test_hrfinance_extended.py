import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.agents.hrfinance import investigate
from apps.core.services import add_evidence
from apps.finance import hrfinance as domain
from apps.policy.hrfinance_drafts import draft_disclosure_fields
from apps.policy.hrfinance_validators import DISCLOSURE, REQUIRED
from apps.policy.services import reference_values
from tests.helpers import rev
from tests.hrfinance_helpers import fixture, policy


EXAMPLE = json.loads((Path(__file__).resolve().parent.parent / 'fixtures/hr-finance-extended.json').read_text())


def extended(f, fields=None):
    fields = fields or EXAMPLE['source_fields']
    source = add_evidence(f['hr'], f['case'].pk, 'hr_contract_source_v2',
        'SAMPLE reviewed extended source contract. Fictional values stay in the private export.', 'synthetic:hr-v2')
    rules = dict(deepcopy(f['config']['disclosure']), format=EXAMPLE['format'],
                 source_fields=EXAMPLE['source_fields'], allowed_fields=fields, source_evidence_id=source.pk)
    payload = dict(deepcopy(f['config']['need']), format=EXAMPLE['need_format'], fields=fields,
                   purpose='payroll_support', justification={field: 'SAMPLE explicit purpose for '+field for field in fields})
    # A separate explicit purpose is part of the synthetic source decision.
    rules['purposes'] = ['payroll_support']
    configured = policy(f['hr'], f['case'], DISCLOSURE, rules, f['e']['owner'])
    need = domain.need(f['finance'], f['case'].pk, 'extended-payroll', payload, f['e']['hr_finance_need'].pk, rev(f['case']))
    contract = domain.contract(f['finance'], f['case'].pk, need.pk, 'extended-contract', source.pk, rev(f['case']))
    return configured, contract, source


def export(f, contract, **changes):
    payload = deepcopy(f['config']['export'])
    payload['extracted_at'] = (timezone.now()).isoformat()
    for row in payload['rows']:
        row.update({key: value for key, value in EXAMPLE['row_values'].items() if key in contract.payload['fields']})
        row.update(changes)
    return json.dumps(payload)


class ExtendedHRContractTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = fixture()

    def test_explicit_v2_contract_needs_hr_approval_and_keeps_unknown_and_zero(self):
        f = self.f
        _, contract, _ = extended(f)
        with self.assertRaises(ValidationError):
            domain.capture(f['hr'], f['case'].pk, contract.pk, 'premature', export(f, contract), rev(f['case']))
        domain.decide(f['hr'], f['case'].pk, contract.pk, 'approve', 'approve-v2',
                      f['e']['hr_disclosure_decision'].pk, rev(f['case']))
        snapshot = domain.capture(f['hr'], f['case'].pk, contract.pk, 'private-v2', export(f, contract), rev(f['case']))
        self.assertEqual(snapshot.status, 'accepted')
        data = domain.read_snapshot(f['finance'], snapshot)
        self.assertEqual(data['rows'][0]['gross_pay'], '0')
        self.assertIsNone(data['rows'][0]['deductions'])
        self.assertEqual(data['rows'][0]['bank_account'], '000123-SAMPLE')
        run = investigate(f['hr'], f['case'].pk, rev(f['case']))
        self.assertNotIn('000123-SAMPLE', json.dumps(run.result))
        self.client.force_login(f['hr'])
        self.assertNotContains(self.client.get(reverse('hrfinance', args=[f['case'].pk])), '000123-SAMPLE')
        with self.assertRaises(ValidationError):
            domain.draft_basis(f['finance'], f['case'].pk, snapshot.pk, f['e']['owner'].pk, rev(f['case']))

    def test_v1_and_undeclared_source_fields_remain_rejected(self):
        f = self.f
        need = deepcopy(f['config']['need'])
        need['fields'] += ['bank_account']
        need['justification']['bank_account'] = 'SAMPLE'
        with self.assertRaises(ValidationError):
            domain.need(f['finance'], f['case'].pk, 'legacy-extra', need, f['e']['hr_finance_need'].pk, rev(f['case']))
        configured, _, _ = extended(f, REQUIRED)
        data = reference_values(configured)[0]
        data['source_fields'] = REQUIRED
        policy(f['hr'], f['case'], DISCLOSURE, data, f['e']['owner'])
        current = domain.active_component(DISCLOSURE, f['case'])
        with self.assertRaises(ValidationError):
            draft_disclosure_fields(f['hr'], f['case'].pk, current.pk, current.revision,
                REQUIRED + ['bank_account'], f['e']['owner'].pk, timezone.now(), rev(f['case']), reason='SAMPLE undeclared field')

    def test_private_field_validation_discards_invalid_values_and_extra_medical_fields(self):
        f = self.f
        _, contract, _ = extended(f)
        domain.decide(f['hr'], f['case'].pk, contract.pk, 'approve', 'approve-v2', f['e']['hr_disclosure_decision'].pk, rev(f['case']))
        for number, changed in enumerate([{'bank_account': 123}, {'home_address': {'private': 'SENTINEL'}},
                {'gross_pay': 'invalid-SENTINEL'}, {'date_of_birth': '2099-01-01'}, {'medical': 'SENTINEL'}]):
            snapshot = domain.capture(f['hr'], f['case'].pk, contract.pk, f'bad-v2-{number}',
                                      export(f, contract, **changed), rev(f['case']))
            self.assertEqual(snapshot.payload, {})
            self.assertNotIn('SENTINEL', json.dumps(snapshot.manifest))

    def test_structured_editor_uses_only_declared_v2_fields_and_preserves_other_terms(self):
        f = self.f
        configured, _, _ = extended(f, REQUIRED)
        self.client.force_login(f['hr'])
        url = reverse('workspace_settings', args=[f['case'].pk]) + '?area=payroll'
        page = self.client.get(url)
        self.assertContains(page, 'Bank account')
        self.assertEqual({key for key, _ in page.context['visibility_form'].fields['fields'].choices},
                         set(EXAMPLE['source_fields']))
        values = {'fields': REQUIRED + ['bank_account'], 'base_id': configured.pk,
            'latest_revision': configured.revision, 'revision': rev(f['case']), 'evidence': f['e']['owner'].pk,
            'effective_from': timezone.now().isoformat(), 'reason': 'SAMPLE explicit bank-reference test'}
        self.assertContains(self.client.post(url, values, follow=True), 'Visibility draft')
        from apps.policy.models import Configuration
        draft = Configuration.objects.filter(case=f['case'], component=DISCLOSURE).latest('revision')
        self.assertEqual(reference_values(draft)[0]['format'], EXAMPLE['format'])
        self.assertEqual(reference_values(draft)[0]['source_fields'], EXAMPLE['source_fields'])

    def test_department_assistant_never_loads_extended_private_payload(self):
        from apps.agents import assistant
        from apps.agents.assistant_models import AssistantConversation
        from apps.finance.hrfinance_models import HRReadSnapshot
        from apps.identity.models import Grant

        f = self.f
        _, contract, _ = extended(f)
        domain.decide(f['hr'], f['case'].pk, contract.pk, 'approve', 'approve-v2',
                      f['e']['hr_disclosure_decision'].pk, rev(f['case']))
        domain.capture(f['hr'], f['case'].pk, contract.pk, 'assistant-metadata', export(f, contract), rev(f['case']))
        Grant.objects.create(case=f['case'], user=f['finance'], action='agent.extract')
        conversation = AssistantConversation.objects.create(actor=f['finance'], case=f['case'], persona='zainab')

        def forbidden(_):
            raise AssertionError('Department metadata must leave private HR payload deferred')

        with patch.object(HRReadSnapshot, 'payload', new=property(forbidden)):
            sources, _ = assistant.tool_context(conversation)
            handoff = next(item for item in sources if item['label'].startswith('HR handoff'))
            self.assertIn('Gross pay', handoff['fact'])
            self.assertIn('Date of birth', handoff['fact'])
            self.assertNotIn('employee_id', handoff['fact'])
            self.assertNotIn('000123-SAMPLE', json.dumps(sources))
            Grant.objects.filter(case=f['case'], user=f['finance'], action='hrfinance.snapshot.read').update(active=False)
            sources, _ = assistant.tool_context(conversation)
            self.assertFalse(any(item['label'].startswith('HR handoff') for item in sources))
