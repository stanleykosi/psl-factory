"""Exact PMO catalogue examples; synthetic receipts, real internal services/SQL.

No new policy, signature authenticity, operational clock or whole-process claim.
"""
from decimal import Decimal
import json
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adapters.pmo_gates import SyntheticGateAdapter
from apps.identity.models import Grant
from apps.pmo import delivery, delivery_closure as closure
from apps.pmo.delivery_documents import draft_delivery_document
from apps.pmo.gates import gate_summary, record_gate, register_candidate, verify_gate
from apps.pmo.models import DeliveryRecord, GateRecord, GateVerification
from apps.documents.models import PublicationReceipt
from apps.workflows.models import HumanTask
from tests.helpers import rev
from tests.test_delivery import DeliveryFixture


class ReleaseHandoverExactTests(DeliveryFixture, TestCase):
    @classmethod
    def setUpTestData(cls):
        f = DeliveryFixture()
        f.setup_delivery()
        for key, value in vars(f).items():
            setattr(cls, key, value)

    def request_blocked(self, missing):
        before = list(self.d.records.values_list('pk', 'kind'))
        with self.assertRaisesMessage(ValidationError, missing):
            delivery.record_release_request(self.actor, self.case.pk, self.d.pk,
                'GLPI-754', self.e['plan'].pk, 'Actual request cannot bypass exact prerequisites', rev(self.case))
        self.client.force_login(self.actor)
        response = self.client.post(reverse('delivery', args=[self.case.pk]), {
            'action': 'request', 'revision': rev(self.case), 'dossier': self.d.pk,
            'external_ref': 'GLPI-754', 'evidence': self.e['plan'].pk,
            'note': 'Exact missing gate must remain visible'})
        self.assertContains(response, missing)
        self.assertEqual(before, list(self.d.records.values_list('pk', 'kind')))
        self.assertFalse(self.d.records.filter(kind__in=['glpi_request', 'release_ready', 'release_outcome']).exists())

    def test_p30_m02_product_approvals_without_client_uat_do_not_enable_request(self):
        self.plan()
        self.gates([k for k in delivery.UPSTREAM_GATES if k != 'uat_client'])
        self.assertTrue(all('accepted' in line for line in gate_summary(self.candidate)
                            if line.startswith(('uat_product_manager:', 'uat_product_owner:'))))
        self.request_blocked('uat_client')
        self.gates(['uat_client'])
        request = delivery.record_release_request(self.actor, self.case.pk, self.d.pk,
            'GLPI-754', self.e['plan'].pk, 'All three current UAT approvals now exist', rev(self.case))
        self.assertEqual(len(request.snapshot['gates']), 5)
        with self.assertRaisesMessage(ValidationError, 'glpi_security'):
            delivery.prepare_readiness(self.actor, self.case.pk, self.d.pk, rev(self.case))

    def test_p31_m02_missing_engineering_go_not_inferred_from_complete_uat(self):
        self.plan()
        self.gates([k for k in delivery.UPSTREAM_GATES if k != 'engineering_go'])
        self.request_blocked('engineering_go')

    def test_p31_m02_engineering_no_go_retained_and_cannot_be_rewritten(self):
        self.plan()
        self.gates([k for k in delivery.UPSTREAM_GATES if k != 'engineering_go'])
        evidence = self.evidence('engineering_release_decision', 'Engineering explicitly records No-Go for delivery-build')
        gate = record_gate(self.actor, self.case.pk, self.candidate.pk, 'engineering_go',
            'ENGINEERING-NO-GO-754', evidence.pk, rev(self.case))
        class NoGo(SyntheticGateAdapter):
            def read(self, record):
                return dict(super().read(record), decision='rejected', source_receipt='synthetic:engineering:no-go:754')
        verification = verify_gate(self.actor, self.case.pk, gate.pk, rev(self.case), NoGo())
        self.request_blocked('engineering_go')
        self.assertIn('engineering_go: rejected (Engineering)', gate_summary(self.candidate))
        with self.assertRaises(DatabaseError), transaction.atomic():
            GateVerification.objects.filter(pk=verification.pk).update(result=dict(verification.result, decision='accepted'))
        verification.refresh_from_db()
        self.assertEqual(verification.result['decision'], 'rejected')
        self.assertEqual(verification.result['source_receipt'], 'synthetic:engineering:no-go:754')

    def test_p31_m02_old_candidate_receipt_cannot_verify_current_engineering_gate(self):
        self.plan()
        self.gates([k for k in delivery.UPSTREAM_GATES if k != 'engineering_go'])
        old = register_candidate(self.actor, self.case.pk, 'older-build-754', self.e['requirements'].pk, rev(self.case))
        old_gate = record_gate(self.actor, self.case.pk, old.pk, 'engineering_go', 'OLD-GO-754', self.e['requirements'].pk, rev(self.case))
        old_proof = verify_gate(self.actor, self.case.pk, old_gate.pk, rev(self.case))
        current = record_gate(self.actor, self.case.pk, self.candidate.pk, 'engineering_go', 'CURRENT-GO-754', self.e['requirements'].pk, rev(self.case))
        class WrongCandidate(SyntheticGateAdapter):
            def read(self, record):
                return dict(super().read(record), candidate_ref=old.reference,
                            source_receipt=old_proof.result['source_receipt'])
        with self.assertRaisesMessage(ValidationError, 'does not match candidate'):
            verify_gate(self.actor, self.case.pk, current.pk, rev(self.case), WrongCandidate())
        self.assertFalse(current.verifications.exists())
        self.request_blocked('engineering_go')
        with self.assertRaises(DatabaseError), transaction.atomic():
            GateRecord.objects.filter(pk=old_gate.pk).update(candidate=self.candidate)
        old_gate.refresh_from_db()
        self.assertEqual(old_gate.candidate_id, old.pk)

    def test_p63_m02_global_approved_evidence_cannot_replace_missing_qa_or_glpi(self):
        approved = self.evidence('global_gate_approval', 'Synthetic PMO global Execution gate marked approved')
        planning = self.plan()
        self.assertEqual(planning.data['verdict'], 'approve')
        self.gates([k for k in delivery.UPSTREAM_GATES if k != 'qa_exit'])
        self.request_blocked('qa_exit')
        self.gates(['qa_exit'])
        request = delivery.record_release_request(self.actor, self.case.pk, self.d.pk,
            'GLPI-754', approved.pk, 'Global status attached but specific controls remain independent', rev(self.case))
        self.gates(['glpi_cto', 'glpi_ceo'], 'GLPI-754')
        with self.assertRaisesMessage(ValidationError, 'glpi_security'):
            delivery.prepare_readiness(self.actor, self.case.pk, self.d.pk, rev(self.case))
        response = self.client.post(reverse('delivery', args=[self.case.pk]), {
            'action': 'ready', 'revision': rev(self.case), 'dossier': self.d.pk})
        self.assertContains(response, 'glpi_security')
        self.assertFalse(self.d.records.filter(kind__in=['release_ready', 'release_outcome']).exists())
        self.assertEqual(request.evidence_id, approved.pk)
        self.gates(['glpi_security'], 'GLPI-754')
        ready = delivery.prepare_readiness(self.actor, self.case.pk, self.d.pk, rev(self.case))
        self.assertEqual(ready.snapshot['request_id'], request.pk)
        self.assertEqual(len(ready.snapshot['glpi']), 3)
        self.assertFalse(ready.snapshot['deployment_authorized'])

    def go_live_receipt(self):
        data = {key: self.evidence(kind).pk for key, kind in [
            ('checklist', 'deployment_checklist'), ('incident_reporting', 'incident_reporting'), ('rollback', 'rollback_plan')]}
        version = draft_delivery_document(self.actor, self.case.pk, self.d.pk, 'go_live', self.t.pk, data, rev(self.case))
        return self.publish(version)

    def released_with_uat(self, pm_uat, client_uat):
        self.plan()
        for kind in delivery.UPSTREAM_GATES:
            evidence = pm_uat if kind == 'uat_product_manager' else client_uat if kind == 'uat_client' else self.e['requirements']
            gate = record_gate(self.actor, self.case.pk, self.candidate.pk, kind, 'PRE-RELEASE-754:' + kind, evidence.pk, rev(self.case))
            verify_gate(self.actor, self.case.pk, gate.pk, rev(self.case))
        delivery.record_release_request(self.actor, self.case.pk, self.d.pk, 'GLPI-754', self.e['plan'].pk,
            'Exact pre-release UAT approvals and Engineering Go', rev(self.case))
        self.gates(delivery.GLPI_GATES, 'GLPI-754')
        ready = delivery.prepare_readiness(self.actor, self.case.pk, self.d.pk, rev(self.case))
        outcome = delivery.capture_release(self.actor, self.case.pk, self.d.pk, ready.pk, timezone.now(),
            'INFRA-754', self.e['completion'].pk, 'Actual later synthetic release', rev(self.case))
        return outcome

    def test_p33_m02_pre_release_uat_results_cannot_substitute_for_signatures(self):
        pm_uat = self.evidence('uat_results', 'Pre-release Product Manager UAT approval')
        client_uat = self.evidence('uat_results', 'Pre-release Client UAT approval')
        outcome = self.released_with_uat(pm_uat, client_uat)
        receipt = self.go_live_receipt()
        self.assertLess(pm_uat.created_at, outcome.created_at)
        self.assertEqual(delivery.valid_release(self.d).pk, outcome.pk)
        with self.assertRaisesMessage(ValidationError, 'required kind'):
            closure.accept_go_live(self.actor, self.case.pk, self.d.pk, receipt.pk,
                pm_uat.pk, client_uat.pk, 'Attempt to reuse only UAT results', rev(self.case))
        self.client.force_login(self.actor)
        response = self.client.post(reverse('delivery', args=[self.case.pk]), {
            'action': 'accept', 'revision': rev(self.case), 'dossier': self.d.pk,
            'receipt': receipt.pk, 'pm_signature': pm_uat.pk, 'client_signature': client_uat.pk,
            'attestation': json.dumps(self.attestation(receipt, pm_uat, client_uat)),
            'note': 'Only pre-release UAT evidence is supplied'})
        self.assertContains(response, 'required kind')
        self.assertFalse(self.d.records.filter(kind__in=['go_live', 'go_live_reaffirmation']).exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            pm_uat.__class__.objects.filter(pk=pm_uat.pk).update(kind='signature')

    def test_p33_m02_signature_typed_pre_release_uat_cannot_be_reused_as_go_live(self):
        pm_uat = self.evidence('signature', 'Pre-release UAT signature only, not go-live: PM')
        client_uat = self.evidence('signature', 'Pre-release UAT signature only, not go-live: Client')
        outcome = self.released_with_uat(pm_uat, client_uat)
        receipt = self.go_live_receipt()
        self.assertLess(client_uat.created_at, outcome.created_at)
        self.assertEqual(delivery.valid_release(self.d).pk, outcome.pk)
        with self.assertRaises(ValidationError):
            closure.accept_go_live(self.actor, self.case.pk, self.d.pk, receipt.pk, pm_uat.pk, client_uat.pk,
                'Attempt to reuse recorded pre-release UAT signatures only', rev(self.case))
        self.assertFalse(self.d.records.filter(kind__in=['go_live', 'go_live_reaffirmation']).exists())

    def test_p39_m01_m03_pmo_closure_retains_unpaid_issued_invoice_and_open_billing_review(self):
        from apps.finance import cash, invoices, invoice_delivery, receivables
        from apps.finance.models import Invoice, InvoiceIssue, InvoiceReview, CashReceipt, CashAllocation
        from apps.policy.services import register_reference
        from tests.helpers import activate
        from tests.billing_helpers import coverage, prices, usage, prepare, policy
        from tests.settlement_helpers import draft
        from tests.signature_helpers import reaffirm_for

        # Extend only this synthetic case's roster, before the delivery decisions.
        finance = register_reference(self.actor, self.case.pk, 'release754:finance',
            'schema:psl/role-assignment/v1', {'role': 'Finance', 'user_id': self.actor.pk}, self.e['policy_decision'].pk)
        activate(self.actor, self.case, 'D05.role_principal_assignments',
                 ['role:0', 'role:1', 'role:2', 'role:3', finance.ref], self.e['policy_decision'])
        f = json.loads(Path('fixtures/finance-settlement.json').read_text())
        f['adapter']['recipient_id'] = self.actor.pk
        for component, value in [('D05.decision_action_matrix', f['review']),
                ('D08.adapter_contract_ref', f['adapter']), ('D08.duplicate_correction_rules', f['identity'])]:
            policy(self.actor, self.case, component, value)
        reaffirm_for(self.actor, self.case)
        cov = coverage(self.actor, self.case)
        prices(self.actor, self.case, cov)
        first_usage = usage(self.actor, self.case, cov)
        prep = prepare(self.actor, self.case, cov, u=first_usage)
        invoice = draft(self.actor, self.case, prep, 'UNPAID-754')
        review_evidence = self.evidence('invoice_review', 'Synthetic Finance exact invoice review')
        invoices.review(self.actor, self.case.pk, invoice.pk, 'Finance', 'approve', review_evidence.pk,
                        'Approve exact synthetic invoice only', rev(self.case))
        invoices.reserve(self.actor, self.case.pk, invoice.pk, 'issue', 'Finance', rev(self.case))
        self.assertTrue(invoice_delivery.run_once())
        issue = InvoiceIssue.objects.get(invoice=invoice)
        self.assertGreater(invoice.amount, Decimal('0'))
        self.assertEqual(cash.open_amount(issue), invoice.amount)
        self.assertFalse(CashReceipt.objects.filter(case=self.case).exists())
        self.assertFalse(CashAllocation.objects.filter(issue=issue).exists())

        # A different ordinary billing obligation is actually returned by Finance.
        csv = json.loads(Path('fixtures/finance-billing.json').read_text())['csv']
        for row in first_usage.rows:
            csv = csv.replace(row['transaction_id'], row['transaction_id'] + '-754-review')
        pending_usage = usage(self.actor, self.case, cov, csv)
        pending = draft(self.actor, self.case, prepare(self.actor, self.case, cov, u=pending_usage), 'OPEN-REVIEW-754')
        returned = invoices.review(self.actor, self.case.pk, pending.pk, 'Finance', 'return', review_evidence.pk,
            'Billing review remains open: reconcile source evidence before approval', rev(self.case))
        with self.assertRaisesMessage(ValidationError, 'human Finance approval'):
            invoices.reviewed(pending)
        data = self.closing()
        before_finance = {table: list(model.objects.order_by('pk').values()) for table, model in [
            ('invoices', Invoice), ('issues', InvoiceIssue), ('reviews', InvoiceReview),
            ('cash', CashReceipt), ('allocations', CashAllocation)]}
        before_receivables = receivables.calculate(self.case, timezone.localdate())
        version = draft_delivery_document(self.actor, self.case.pk, self.d.pk, 'closure', self.t.pk, data, rev(self.case))
        closure.decide_closure(self.actor, self.case.pk, version.pk, 'approve', self.e['requirements'].pk,
            'Head of PMO approves only prescribed closure evidence', rev(self.case))
        closed = closure.finalize_closure(self.actor, self.case.pk, self.d.pk, rev(self.case))
        self.assertFalse(closed.snapshot['debt_waived'])
        self.assertFalse(closed.snapshot['deployment_authorized'])
        self.assertEqual(closed.data['archive_state'], 'immutable_index_recorded')
        self.assertEqual(before_finance, {table: list(model.objects.order_by('pk').values()) for table, model in [
            ('invoices', Invoice), ('issues', InvoiceIssue), ('reviews', InvoiceReview),
            ('cash', CashReceipt), ('allocations', CashAllocation)]})
        self.assertEqual(before_receivables, receivables.calculate(self.case, timezone.localdate()))
        self.assertEqual(cash.open_amount(issue), invoice.amount)
        self.assertEqual(InvoiceReview.objects.filter(invoice=pending).latest('pk').pk, returned.pk)
        self.assertFalse(InvoiceIssue.objects.filter(invoice=pending).exists())
        self.client.force_login(self.actor)
        self.assertContains(self.client.get(reverse('delivery', args=[self.case.pk])), 'Closure recorded; immutable archive index preserved')
        page = self.client.get(reverse('finance_settlement', args=[self.case.pk]))
        self.assertContains(page, 'UNPAID-754')
        self.assertContains(page, 'OPEN-REVIEW-754')
        pending_projection = next(i for i in page.context['invoices'] if i.pk == pending.pk)
        self.assertEqual(pending_projection.display_status, 'Draft; not issued')
        self.assertIn('human Finance approval', ' '.join(pending_projection.current_findings))
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeliveryRecord.objects.filter(pk=closed.pk).update(snapshot=dict(closed.snapshot, debt_waived=True))


class FactoryReleaseHandoverExactTests(TestCase):
    def test_p35_m02_zero_incidents_but_missing_owner_confirmation_never_completes_monitoring(self):
        from tests.test_factory_hypercare import setup
        from apps.workflows import factory, factory_hypercare
        f = setup()
        f.accepted()
        f.criteria()  # Explicit synthetic 0-hour criterion, never an operational default.
        def observations(confirmed):
            f.source('hypercare_engineering', {'observed_at': timezone.now().isoformat(),
                'confirmed': confirmed, 'metrics': {'errors': {'value': 0, 'unit': 'count'},
                    'incidents': {'value': 0, 'unit': 'count'}}})
            f.source('hypercare_infrastructure', {'observed_at': timezone.now().isoformat(),
                'confirmed': confirmed, 'metrics': {'availability': {'value': 100, 'unit': 'percent'}}})
        observations(None)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        row = factory_hypercare.assessed(f.work)
        self.assertEqual(f.work.status, 'waiting', f.work.finding)
        self.assertIsNone(row.snapshot['qualified'])
        self.assertEqual(set(row.snapshot['findings']), {
            'Engineering stability confirmation is unknown', 'Infrastructure stability confirmation is unknown'})
        sources = list(f.d.sources.filter(kind__startswith='hypercare_').order_by('pk'))
        self.assertEqual(sources[0].payload['metrics']['errors']['value'], 0)
        self.assertEqual(sources[0].payload['metrics']['incidents'], {'value': 0, 'unit': 'count'})
        self.assertEqual(sources[1].payload['metrics']['availability']['value'], 100)
        with self.assertRaises(ValidationError):
            factory_hypercare.verify(f.work)
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertContains(page, 'confirmation is unknown')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d, kind='closure').exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeliveryRecord.objects.filter(pk=row.pk).update(snapshot=dict(row.snapshot, qualified=True))
        # Only actual owner confirmation successors can satisfy the same metrics.
        observations(True)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        row.refresh_from_db()
        self.assertIsNone(row.snapshot['qualified'])
        self.assertTrue(factory_hypercare.assessed(f.work).snapshot['qualified'])

    def test_p37_m02_inaccessible_handover_recorded_then_authorized_correction_redelivery_without_approval(self):
        from tests.test_factory_handover import setup, ready, receipt
        from apps.workflows import factory, factory_handover as handover
        f = setup()
        ready(f)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        original = receipt(f)
        old_source = f.work.source_head_id
        access_issue = f.evidence('handover_access_issue', 'Support cannot open the original support document; authorized correction and re-delivery required')
        handover.acknowledge(f.actor, f.work.pk, f.work.revision, rev(f.case), original.pk, 'gaps',
                            access_issue.pk, 'Actual recipient reports inaccessible support document')
        gap = DeliveryRecord.objects.get(dossier=f.d, kind='handover')
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'waiting')
        # Exercise a genuine current authorization denial, not only an error label.
        grant = Grant.objects.get(case=f.case, user=f.actor, action='document.receive:internal')
        Grant.objects.filter(pk=grant.pk).update(active=False)
        self.client.force_login(f.actor)
        inbox = self.client.get(reverse('document_inbox'))
        self.assertNotIn(original.pk, [r.pk for r in inbox.context['receipts']])
        with self.assertRaises(PermissionDenied):
            handover.acknowledge(f.actor, f.work.pk, f.work.revision, rev(f.case), original.pk,
                                'received', access_issue.pk, 'Cannot fabricate receipt while access is withdrawn')
        self.assertFalse(HumanTask.objects.filter(version__deliverydocumentbinding__dossier=f.d,
            version__deliverydocumentbinding__purpose='handover').exists())
        self.assertFalse(HumanTask.objects.filter(case=f.case, kind='factory_review').exists())
        # Explicit synthetic owner authorization restores only the prior grant.
        Grant.objects.filter(pk=grant.pk).update(active=True)
        replacement = f.evidence('support_document', 'Corrected accessible Support operations instructions, version 2')
        inputs = dict(f.inputs, support_document=replacement.pk)
        response = self.client.post(reverse('factory_detail', args=[f.work.pk]), {
            'action': 'correct', 'revision': f.work.revision, 'case_revision': rev(f.case),
            **inputs, 'reason': 'Authorized source correction and re-delivery for recorded access issue'})
        self.assertEqual(response.status_code, 302)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        current = receipt(f)
        self.assertNotEqual(current.pk, original.pk)
        self.assertNotEqual(f.work.source_head_id, old_source)
        self.assertEqual(current.recipient_id, original.recipient_id)
        self.assertEqual(current.publication.version.fields['scope']['text'], 'Corrected accessible Support operations instructions, version 2')
        self.assertEqual(current.payload, current.publication.version.payload)
        self.assertEqual(current.payload_sha256, current.publication.version.payload_sha256)
        self.assertIn('Corrected accessible Support operations instructions, version 2', json.dumps(current.payload))
        accessible = self.client.get(reverse('document_inbox'))
        self.assertIn(current.pk, [r.pk for r in accessible.context['receipts']])
        self.assertContains(accessible, 'Corrected accessible Support operations instructions, version 2')
        with self.assertRaisesMessage(ValidationError, 'exact current handover receipt'):
            handover.acknowledge(f.actor, f.work.pk, f.work.revision, rev(f.case), original.pk,
                                'received', access_issue.pk, 'Old receipt cannot stand for corrected delivery')
        handover.acknowledge(f.actor, f.work.pk, f.work.revision, rev(f.case), current.pk,
                            'received', replacement.pk, 'Actual recipient can now access corrected support documents')
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        self.assertFalse(handover.verify(f.work)['separate_handover_approval'])
        self.assertFalse(HumanTask.objects.filter(version__deliverydocumentbinding__dossier=f.d,
            version__deliverydocumentbinding__purpose='handover').exists())
        self.assertFalse(HumanTask.objects.filter(case=f.case, kind='factory_review').exists())
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=f.work).count(), 2)
        gap.refresh_from_db()
        self.assertEqual(gap.data['status'], 'gaps')
        self.assertEqual(gap.evidence_id, access_issue.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeliveryRecord.objects.filter(pk=gap.pk).update(data=dict(gap.data, status='received'))
