"""P63 bounded native evidence projection; no live gate policy is invented."""
import json
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase
from apps.agents.delivery import investigate_phases
from apps.identity.models import Grant
from apps.pmo.phase_evidence import projection
from apps.pmo.models import DeliveryRecord
from apps.pmo.delivery_closure import decide_closure, finalize_closure
from apps.pmo.delivery_documents import draft_delivery_document
from tests.test_delivery import DeliveryFixture
from tests.helpers import rev


class PhaseEvidence773Tests(DeliveryFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        f = DeliveryFixture(); f.setup_delivery(); selected = f.closing()
        version = draft_delivery_document(f.actor, f.case.pk, f.d.pk, 'closure', f.t.pk, selected, rev(f.case))
        decide_closure(f.actor, f.case.pk, version.pk, 'approve', f.e['requirements'].pk,
                      'Exact synthetic closure report decision', rev(f.case))
        finalize_closure(f.actor, f.case.pk, f.d.pk, rev(f.case))
        for key, value in vars(f).items(): setattr(cls, key, value)

    def read(self): return projection(self.actor, self.case.pk, self.d.pk)

    def test_native_chain_four_phases_registry_and_unknown_policy(self):
        result = self.read()
        self.assertEqual([p['name'] for p in result['phases']], ['Initiation', 'Planning', 'Execution', 'Closure'])
        self.assertTrue(result['phases'][2]['child_evidence_current'])
        self.assertTrue(result['phases'][3]['child_evidence_current'])
        # Legacy fixture has no native initial engagement/Finance intake. Do not
        # reinterpret that as rejected engagement or payment failure.
        self.assertFalse(result['phases'][0]['child_evidence_current'])
        for phase in result['phases']:
            self.assertEqual(phase['entry'], 'unknown'); self.assertEqual(phase['exit'], 'unknown')
            self.assertIn('Q05', phase['source_questions'])
            self.assertEqual(len(phase['references']), len(set(phase['references'])))
            for ref in phase['references']: self.assertIn(ref, result['evidence_registry'])
        ids = [(r['type'], r['id']) for r in result['evidence_registry'].values()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(result['approval_tasks_created']); self.assertEqual(result['effect_tools'], [])

    def test_revoked_child_authority_rechecked_without_history_mutation(self):
        before = list(DeliveryRecord.objects.filter(dossier=self.d).values())
        self.assertTrue(self.read()['phases'][2]['child_evidence_current'])
        Grant.objects.filter(user=self.actor, case=self.case, action='pmo.gate_verify').update(active=False)
        result = self.read()
        self.assertFalse(result['phases'][2]['child_evidence_current'])
        self.assertEqual(list(DeliveryRecord.objects.filter(dossier=self.d).values()), before)

    def test_metadata_reader_cannot_learn_finance_payload_or_errors(self):
        Grant.objects.filter(user=self.actor, case=self.case, action='finance.read').update(active=False)
        result = self.read()
        for phase in [result['phases'][0], result['phases'][3]]:
            check = next(c for c in phase['checks'] if c['key'] == 'finance')
            self.assertEqual(check['status'], 'restricted_or_authority_changed')
            self.assertEqual(check['references'], [])
        self.assertFalse(any(v['type'].startswith('finance.') for v in result['evidence_registry'].values()))
        self.assertNotIn('payload', json.dumps(result)); self.assertNotIn('note', json.dumps(result))

    def test_read_only_tool_and_ui_leave_unpaid_finance_independent(self):
        statements = []
        def record(execute, sql, params, many, context):
            statements.append(sql.strip().split()[0].upper())
            return execute(sql, params, many, context)
        with connection.execute_wrapper(record):
            result = investigate_phases(self.actor, self.case.pk, self.d.pk)
            html = render_to_string('factory/phase_evidence.html', {'phases': result})
        self.assertTrue(set(statements) <= {'SELECT'})
        self.assertFalse(result['debt_waived']); self.assertEqual(result['financial_status'], 'not_assessed')
        self.assertFalse(result['deployment_authorized']); self.assertFalse(result['phase_change_authorized'])
        for name in ['Initiation', 'Planning', 'Execution', 'Closure']: self.assertIn(name, html)
        self.assertIn('Q05', html); self.assertNotIn('<form', html); self.assertIn('Finance retains debt', html)

    def test_reader_grant_is_required(self):
        Grant.objects.filter(user=self.actor, case=self.case, action='delivery.read').update(active=False)
        with self.assertRaises(PermissionDenied): self.read()


class MissingPhaseEvidence773Tests(DeliveryFixture, TestCase):
    def test_global_approval_does_not_replace_missing_qa_or_glpi(self):
        self.setup_delivery(); self.plan()
        before = list(DeliveryRecord.objects.filter(dossier=self.d).values())
        result = projection(self.actor, self.case.pk, self.d.pk)
        execution = result['phases'][2]
        self.assertFalse(execution['child_evidence_current'])
        for key in ['qa_exit', 'glpi']:
            check = next(c for c in execution['checks'] if c['key'] == key)
            self.assertNotEqual(check['status'], 'current')
            self.assertEqual(check['business_outcome'], 'not_inferred')
        self.assertEqual(list(DeliveryRecord.objects.filter(dossier=self.d).values()), before)
        self.assertFalse(result['approval_tasks_created'])

    def test_changed_source_version_cannot_inherit_planning_decision(self):
        self.setup_delivery(); self.plan()
        self.assertTrue(projection(self.actor, self.case.pk, self.d.pk)['phases'][1]['child_evidence_current'])
        self.source('technical_design')
        result = projection(self.actor, self.case.pk, self.d.pk)
        check = next(c for c in result['phases'][1]['checks'] if c['key'] == 'plan')
        self.assertEqual(check['status'], 'unknown_or_stale')
        self.assertFalse(result['phase_change_authorized'])


class FullNativePhaseEvidence773Tests(DeliveryFixture, TestCase):
    def test_native_initiation_to_closure_has_one_four_phase_checklist(self):
        from pathlib import Path
        from apps.core.services import add_evidence
        from apps.pmo import engagement
        from apps.pmo.commercial import capture_response, adopt_signed
        from apps.pmo.gates import register_candidate
        from apps.pmo.delivery import open_dossier
        from apps.documents.controlled import register_template
        from apps.policy.engagement_validators import ASSIGN
        from tests.test_engagement_intake import activate as activate_engagement
        from tests.test_commercial_changes import fixture, proposal, approvals, delivered
        from tests.signature_helpers import packet_for
        self.actor, self.case, self.e, commercial_template = fixture(username='phase773-native')
        a, c, e = self.actor, self.case, self.e
        source = add_evidence(a, c.pk, 'engagement_source', 'Synthetic direct client source', 'synthetic:p63')
        engagement.capture(a, c.pk, 'B', source.pk, 'phase773-client', 'phase773-capture')
        values = json.loads(Path('fixtures/engagement-intake.json').read_text())
        activate_engagement(a, c, ASSIGN, values['assignment'], e['policy_decision'])
        engagement.assign(a, c.pk, a.pk, 'PMO Lead', source.pk, 'phase773-assignment')
        v = proposal(a, c, e); approvals(a, c, v)
        receipt = delivered(a, c, v, commercial_template)
        response = capture_response(a, c.pk, v.pk, receipt.pk, 'signed', e['signature'].pk,
                                    'Synthetic exact client signature', rev(c))
        packet_for(a, c, e, v); adopt_signed(a, c.pk, v.pk, response.pk, rev(c))
        self.candidate = register_candidate(a, c.pk, 'phase773-build', e['requirements'].pk, rev(c))
        self.d = open_dossier(a, c.pk, self.candidate.pk, e['plan'].pk, 'Exact synthetic delivery scope', rev(c))
        self.t = register_template(a, c.pk, 'Phase773 delivery artifact',
            {'document_type': 'project_artifact', 'required_fields': ['executive_summary', 'status'],
             'internal_review_required': False,
             'audience_fields': {aud: ['executive_summary', 'scope', 'risks', 'status', 'next_steps', 'timeline', 'dependencies']
                                for aud in ['client', 'internal']}}, e['policy_decision'].pk, rev(c))
        from apps.policy.services import register_reference
        from tests.helpers import activate
        refs = [register_reference(a, c.pk, 'phase773-recipient:'+aud, 'schema:psl/document-recipient/v1',
                                   {'audience': aud, 'user_id': a.pk}, e['policy_decision'].pk).ref
                for aud in ['client', 'internal']]
        activate(a, c, 'D11.recipient_grant_refs', refs, e['policy_decision']); self.storage(False)
        selected = self.closing()
        version = draft_delivery_document(a, c.pk, self.d.pk, 'closure', self.t.pk, selected, rev(c))
        decide_closure(a, c.pk, version.pk, 'approve', e['requirements'].pk, 'Synthetic actual closure decision', rev(c))
        finalize_closure(a, c.pk, self.d.pk, rev(c))
        result = projection(a, c.pk, self.d.pk)
        self.assertEqual(len(result['phases']), 4)
        for phase in result['phases']:
            self.assertTrue(phase['child_evidence_current'], phase)
            self.assertEqual(phase['exit'], 'unknown')
            self.assertEqual(len(phase['references']), len(set(phase['references'])))
        self.assertTrue(any(r['type'] == 'finance.signedbaselineintake' for r in result['evidence_registry'].values()))
        self.assertFalse(result['debt_waived']); self.assertEqual(result['financial_status'], 'not_assessed')


class UnpaidPhaseEvidence773Tests(DeliveryFixture, TestCase):
    def test_actual_unpaid_invoice_and_open_finance_review_survive_closure_and_projection(self):
        from decimal import Decimal
        from django.utils import timezone
        from apps.finance import cash, invoices, receivables
        from apps.finance.models import Invoice, InvoiceIssue, InvoiceReview, CashReceipt, CashAllocation
        from tests.test_release_handover_exact import ReleaseHandoverExactTests
        self.setup_delivery()
        # Reuse the accepted exact P39 native scenario including all of its
        # pre/post-closure row and receivable assertions. It issues a real local
        # synthetic invoice, returns a second invoice review, then closes PMO.
        # No duplicated mock Finance fixture or policy interpretation is added.
        ReleaseHandoverExactTests.test_p39_m01_m03_pmo_closure_retains_unpaid_issued_invoice_and_open_billing_review(self)
        issue = InvoiceIssue.objects.get(invoice__case=self.case, invoice__reference='UNPAID-754')
        pending = Invoice.objects.get(case=self.case, reference='OPEN-REVIEW-754')
        before_open = cash.open_amount(issue)
        self.assertGreater(before_open, Decimal('0'))
        self.assertEqual(before_open, issue.invoice.amount)
        selected = [('invoices', Invoice), ('issues', InvoiceIssue), ('reviews', InvoiceReview),
                    ('cash', CashReceipt), ('allocations', CashAllocation)]
        before_rows = {name: list(model.objects.order_by('pk').values()) for name, model in selected}
        before_receivables = receivables.calculate(self.case, timezone.localdate())
        result = investigate_phases(self.actor, self.case.pk, self.d.pk)
        html = render_to_string('factory/phase_evidence.html', {'phases': result})
        self.assertEqual(before_rows, {name: list(model.objects.order_by('pk').values()) for name, model in selected})
        self.assertEqual(before_receivables, receivables.calculate(self.case, timezone.localdate()))
        self.assertEqual(cash.open_amount(issue), before_open)
        self.assertFalse(CashReceipt.objects.filter(case=self.case).exists())
        self.assertFalse(CashAllocation.objects.filter(issue=issue).exists())
        self.assertEqual(InvoiceReview.objects.filter(invoice=pending).latest('pk').verdict, 'return')
        self.assertFalse(InvoiceIssue.objects.filter(invoice=pending).exists())
        with self.assertRaisesMessage(ValidationError, 'human Finance approval'):
            invoices.reviewed(pending)
        self.assertTrue(self.d.records.filter(kind='closure').exists())
        self.assertTrue(result['phases'][3]['child_evidence_current'])
        self.assertFalse(result['debt_waived']); self.assertFalse(result['approval_tasks_created'])
        self.assertEqual(result['financial_status'], 'not_assessed')
        self.assertNotIn('UNPAID-754', json.dumps(result)); self.assertNotIn('OPEN-REVIEW-754', html)
