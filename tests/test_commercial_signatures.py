from copy import deepcopy
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction
from django.test import TestCase
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition, PolicyHold
from apps.pmo.commercial import capture_response, adopt_signed
from apps.pmo.models import Baseline, BaselineAdoption, CommercialSignaturePacket, CommercialSignatureUse
from apps.pmo.signatures import capture_packet, latest
from .helpers import rev, prepared, setup_case
from .test_commercial_changes import fixture, proposal, approvals, delivered
from .signature_helpers import packet_for, contract


class CommercialSignatureTests(TestCase):
    def setUp(self):
        self.actor, self.case, self.e, self.template = fixture()
        self.proposal = proposal(self.actor, self.case, self.e)
        approvals(self.actor, self.case, self.proposal)
        receipt = delivered(self.actor, self.case, self.proposal, self.template)
        self.response = capture_response(self.actor, self.case.pk, self.proposal.pk, receipt.pk, 'signed',
            self.e['signature'].pk, 'Human received SOW signature', rev(self.case))
        self.client.force_login(self.actor)
        self.url = f'/cases/{self.case.pk}/commercial/'

    def packet(self, **kwargs):
        return packet_for(self.actor, self.case, self.e, self.proposal, **kwargs)

    def adopt(self):
        return adopt_signed(self.actor, self.case.pk, self.proposal.pk, self.response.pk, rev(self.case))

    def test_generic_one_signature_and_each_partial_document_hold_only_adoption(self):
        with self.assertRaises(ValidationError): self.adopt()
        complete = self.packet()
        for kind in ['sow', 'prd']:
            self.packet(signatures={kind: complete.signatures[kind]})
            with self.assertRaises(ValidationError): self.adopt()
            self.assertFalse(BaselineAdoption.objects.exists())
        self.assertEqual(CommercialSignaturePacket.objects.count(), 3)

    def test_received_file_can_be_captured_with_explicit_unknown_signature_details(self):
        partial = {'sow': {'evidence_id': self.e['signature'].pk, 'party_ref': None,
                           'method': None, 'locator': None, 'human_verified': False}}
        packet = self.packet(signatures=partial, configure=False)
        self.assertIsNone(packet.signatures['sow']['party_ref'])
        with self.assertRaises(ValidationError): self.adopt()
        partial['sow']['human_verified'] = True
        with self.assertRaises(ValidationError): self.packet(signatures=partial, configure=False)

    def test_complete_current_packet_adopts_exact_sources_and_receipt_once(self):
        packet = self.packet()
        adoption = self.adopt()
        self.assertEqual(adoption.signature_use.packet_id, packet.pk)
        receipt = adoption.signedbaselineintake
        self.assertEqual(receipt.payload['signature_packet']['sources']['prd'], packet.sources['prd'])
        self.assertFalse(receipt.payload['invoice_created'])
        with self.assertRaises(ValidationError): self.adopt()
        self.assertEqual(CommercialSignatureUse.objects.count(), 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            CommercialSignaturePacket.objects.filter(pk=packet.pk).update(note='rewrite')
        with self.assertRaises(DatabaseError), transaction.atomic():
            CommercialSignatureUse.objects.all().delete()

    def test_unchanged_prd_reference_reuse_requires_explicit_owner_rule(self):
        original = self.packet(); first_adoption = self.adopt()
        from tests.test_commercial_changes import change_roles, impact_fixture
        from apps.pmo.changes import log_change, assess_change, decide_change, authorize_change, CONTRIBUTORS
        change_roles(self.actor, self.case, self.e['policy_decision'])
        change_source = add_evidence(self.actor, self.case.pk, 'change_request', 'Actual synthetic controlled SOW change', 'synthetic:change')
        change = log_change(self.actor, self.case.pk, 'CR-001', 'Normal', 'Delivery', 'New SOW work', 'Client evidence', change_source.pk, rev(self.case))
        for team in CONTRIBUTORS:
            assess_change(self.actor, self.case.pk, change.pk, team, True, True, True, change_source.pk,
                'Owner impact assessment', rev(self.case), **impact_fixture(team, True))
        for role in ['Product', 'Engineering', 'Client', 'Engineering Lead', 'Security Manager']:
            decide_change(self.actor, self.case.pk, change.pk, role, 'approve', change_source.pk, 'Owner decision', rev(self.case))
        evidence = dict(self.e)
        evidence['sow'] = add_evidence(self.actor, self.case.pk, 'sow', 'New controlled SOW document', 'synthetic:new-sow')
        evidence['signature'] = add_evidence(self.actor, self.case.pk, 'signature', 'New SOW signature', 'synthetic:new-sow-signature')
        successor = proposal(self.actor, self.case, evidence, change_source)
        approvals(self.actor, self.case, successor)
        receipt = delivered(self.actor, self.case, successor, self.template)
        response = capture_response(self.actor, self.case.pk, successor.pk, receipt.pk, 'signed', evidence['signature'].pk,
            'New exact SOW signed response', rev(self.case))
        signatures = deepcopy(original.signatures)
        signatures['sow']['evidence_id'] = evidence['signature'].pk
        packet_for(self.actor, self.case, evidence, successor, signatures=signatures)
        with self.assertRaisesMessage(ValidationError, 'Owner re-sign rule'):
            adopt_signed(self.actor, self.case.pk, successor.pk, response.pk, rev(self.case))
        contract(self.actor, self.case, self.e['policy_decision'], reuse='same_document_reference_allowed')
        current = packet_for(self.actor, self.case, evidence, successor, signatures=signatures)
        authorize_change(self.actor, self.case.pk, change.pk, successor.pk, rev(self.case))
        adoption = adopt_signed(self.actor, self.case.pk, successor.pk, response.pk, rev(self.case))
        self.assertEqual(adoption.signature_use.packet_id, current.pk)
        self.assertEqual(current.sources['prd'], original.sources['prd'])
        self.assertEqual(CommercialSignatureUse.objects.count(), 2)
        # A current claim cannot resurrect old dual-proof history after a later adoption.
        with self.assertRaisesMessage(DatabaseError, 'Separate current SOW and PRD'), transaction.atomic():
            Baseline.objects.filter(case=self.case).delete()
            Baseline.objects.create(case=self.case, **first_adoption.after)
        self.assertEqual(Baseline.objects.get(case=self.case).signed_id, evidence['signature'].pk)

    def test_unknown_contract_allows_capture_but_holds_adoption(self):
        packet = self.packet(configure=False)
        self.assertIsNone(packet.policy_id)
        with self.assertRaises(PolicyHold): self.adopt()
        contract(self.actor, self.case, self.e['policy_decision'])
        with self.assertRaises(ValidationError): self.adopt()
        self.packet()
        self.adopt()

    def test_revoked_policy_recorder_authority_and_unsupported_client_method_hold(self):
        packet = self.packet()
        transition(self.actor, packet.policy_id, 'revoked')
        with self.assertRaises(PolicyHold): self.adopt()
        packet = self.packet()
        altered = deepcopy(packet.signatures)
        altered['prd']['method'] = 'unapproved method'
        self.packet(signatures=altered)
        with self.assertRaises(ValidationError): self.adopt()
        self.packet()
        Grant.objects.filter(case=self.case, user=self.actor, action='commercial.response').update(active=False)
        with self.assertRaises(PermissionDenied): self.adopt()
        self.assertFalse(BaselineAdoption.objects.exists())

    def test_new_prd_version_requires_new_document_specific_evidence(self):
        packet = self.packet()
        add_evidence(self.actor, self.case.pk, 'prd', 'Changed PRD', 'synthetic:revision')
        with self.assertRaises(ValidationError): self.adopt()
        with self.assertRaises(ValidationError):
            capture_packet(self.actor, self.case.pk, packet.sources['prd']['id'], packet.signatures, 'Old PRD', 'old-prd', rev(self.case), self.proposal.pk, packet.pk)
        self.assertEqual(CommercialSignaturePacket.objects.count(), 1)
        # A later packet cannot simply relabel the old signature as the new PRD.
        with self.assertRaises(ValidationError): self.packet(signatures=packet.signatures)

    def test_one_bundle_requires_distinct_document_signature_locations(self):
        packet = self.packet()
        signatures = deepcopy(packet.signatures)
        signatures['prd'] = dict(signatures['sow'])
        with self.assertRaises(ValidationError): self.packet(signatures=signatures)
        signatures['prd']['locator'] = 'PRD page 4 client signature'
        self.packet(signatures=signatures)
        self.adopt()

    def test_http_typed_capture_stale_retry_and_history(self):
        packet = self.packet()
        data = {'action': 'signature_packet', 'revision': rev(self.case), 'proposal': self.proposal.pk,
                'prd': packet.sources['prd']['id'], 'predecessor': packet.pk, 'operation_key': 'operator-packet', 'note': 'Actual human checks'}
        for kind, signature in packet.signatures.items():
            data.update({kind + '_signature': signature['evidence_id'], kind + '_party': signature['party_ref'],
                         kind + '_method': signature['method'], kind + '_locator': signature['locator'], kind + '_verified': 'on'})
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(CommercialSignaturePacket.objects.count(), 2)
        self.assertContains(self.client.post(self.url, data), 'Stale revision')
        data['revision'] = rev(self.case)
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(CommercialSignaturePacket.objects.count(), 2)
        self.assertContains(self.client.get(self.url), 'Separate SOW and PRD signatures')
        self.assertContains(self.client.get(self.url), 'Not verified by a signature provider')


    def test_foreign_prd_and_signature_are_rejected_without_capture(self):
        other_actor, other = setup_case(username='foreign-signature')
        foreign_prd = add_evidence(other_actor, other.pk, 'prd', 'Other PRD', 'synthetic:foreign')
        packet = self.packet()
        before = CommercialSignaturePacket.objects.count()
        with self.assertRaises(ValidationError):
            capture_packet(self.actor, self.case.pk, foreign_prd.pk, packet.signatures, 'Wrong project',
                           'foreign-prd', rev(self.case), self.proposal.pk, packet.pk)
        foreign_sig = add_evidence(other_actor, other.pk, 'signature', 'Other signature', 'synthetic:foreign')
        signatures = deepcopy(packet.signatures)
        signatures['prd']['evidence_id'] = foreign_sig.pk
        with self.assertRaises(ValidationError): self.packet(signatures=signatures)
        self.assertEqual(CommercialSignaturePacket.objects.count(), before)

    def test_owner_contract_http_creates_draft_without_activating_or_signing(self):
        from apps.policy.models import Configuration
        from apps.policy.services import resolve
        from apps.policy.signature_validators import COMPONENT
        identity = add_evidence(self.actor, self.case.pk, 'client_identity', 'Synthetic known client', 'synthetic:identity')
        data = {'action': 'signature_contract', 'revision': rev(self.case), 'party_ref': 'known-party',
                'display_name': 'Synthetic known client', 'identity_evidence': identity.pk,
                'documents': ['sow', 'prd'], 'methods': 'owner-reviewed-file', 'applicability': 'client_project', 'signature_requirement': 'required',
                'evidence': self.e['policy_decision'].pk, 'effective_from': '2026-11-01T00:00:00Z'}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(Configuration.objects.filter(component=COMPONENT).count(), 1)
        self.assertContains(self.client.post(self.url, data), 'Stale revision')
        self.assertEqual(Configuration.objects.filter(component=COMPONENT).count(), 1)
        self.assertNotEqual(resolve(COMPONENT, self.case).status, 'ACTIVE')
        self.assertFalse(CommercialSignatureUse.objects.exists())



class LegacySignatureTests(TestCase):
    def test_planning_preparation_stays_available_but_legacy_single_signature_cannot_bypass(self):
        from apps.pmo.services import decide, sign_baseline
        actor, case = setup_case()
        evidence = prepared(actor, case)
        self.assertIsNone(Baseline.objects.get(case=case).signed_id)
        for role in ['PM', 'Head of PMO', 'CEO', 'PMO Lead']:
            decide(actor, case.pk, role, rev(case))
        with self.assertRaises(ValidationError): sign_baseline(actor, case.pk, evidence['signature'].pk, rev(case))
        packet_for(actor, case, evidence)
        sign_baseline(actor, case.pk, evidence['signature'].pk, rev(case))
        self.assertEqual(CommercialSignatureUse.objects.count(), 1)

class CurrentSignatureClaimTests(CommercialSignatureTests):
    def test_revoked_contract_holds_current_claim_not_historical_receipt_and_human_reaffirms(self):
        from django.db import connection
        from apps.pmo.signatures import assert_current_signed_baseline
        from adapters.signed_baselines import InternalSignedBaselineAdapter
        packet = self.packet()
        adoption = self.adopt()
        receipt = adoption.signedbaselineintake
        original = deepcopy(receipt.payload)
        self.assertEqual(assert_current_signed_baseline(self.case).pk, packet.pk)
        transition(self.actor, packet.policy_id, 'revoked')
        with self.assertRaises(PolicyHold): assert_current_signed_baseline(self.case)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_pmo_signed_baseline_current(%s)', [self.case.pk])
            self.assertFalse(cursor.fetchone()[0])
        self.assertEqual(InternalSignedBaselineAdapter().deliver(adoption).pk, receipt.pk)
        contract(self.actor, self.case, self.e['policy_decision'])
        successor = self.packet(signatures=deepcopy(packet.signatures))
        # Preparation alone does not recertify an old adoption.
        with self.assertRaises(ValidationError): assert_current_signed_baseline(self.case)
        response = self.client.post(self.url, {'action': 'signature_reaffirm', 'revision': rev(self.case), 'packet': successor.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(assert_current_signed_baseline(self.case).pk, successor.pk)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_pmo_signed_baseline_current(%s)', [self.case.pk])
            self.assertTrue(cursor.fetchone()[0])
        receipt.refresh_from_db()
        self.assertEqual(receipt.payload, original)
        self.assertEqual(CommercialSignatureUse.objects.count(), 1)
        self.assertEqual(BaselineAdoption.objects.count(), 1)

    def test_reaffirmation_cannot_change_original_party_identity(self):
        from apps.pmo.signatures import reaffirm_baseline
        from apps.policy.services import reference_values
        from tests.document_helpers import artifact
        from apps.policy.signature_validators import COMPONENT, SCHEMA
        packet = self.packet(); self.adopt()
        value = deepcopy(reference_values(packet.policy)[0])
        replacement = add_evidence(self.actor, self.case.pk, 'client_identity', 'Different actual party', 'synthetic:different-identity')
        value['parties'][0]['identity_evidence_id'] = replacement.pk
        artifact(self.actor, self.case, COMPONENT, SCHEMA, value, self.e['policy_decision'])
        successor = self.packet(signatures=deepcopy(packet.signatures))
        with self.assertRaisesMessage(ValidationError, 'original client identity'):
            reaffirm_baseline(self.actor, self.case.pk, successor.pk, rev(self.case))
        from apps.pmo.models import CommercialSignatureReaffirmation
        with self.assertRaisesMessage(DatabaseError, 'original client identity'), transaction.atomic():
            CommercialSignatureReaffirmation.objects.create(use=CommercialSignatureUse.objects.get(), packet=successor, actor=self.actor)

    def test_new_draft_prd_and_proposal_do_not_replace_current_adopted_proof(self):
        from django.db import connection
        from apps.pmo.signatures import assert_current_signed_baseline, reaffirm_baseline
        packet = self.packet(); adoption = self.adopt()
        add_evidence(self.actor, self.case.pk, 'prd', 'Proposed PRD draft', 'synthetic:draft')
        proposed = dict(self.e)
        proposed['sow'] = add_evidence(self.actor, self.case.pk, 'sow', 'Proposed SOW draft', 'synthetic:draft-sow')
        proposal(self.actor, self.case, proposed)
        self.assertEqual(assert_current_signed_baseline(self.case).pk, packet.pk)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_pmo_signed_baseline_current(%s)', [self.case.pk])
            self.assertTrue(cursor.fetchone()[0])
        # The prior adopted version remains eligible for human reaffirmation.
        data = {'action': 'signature_packet', 'revision': rev(self.case), 'commercial_revision': self.proposal.pk,
                'prd': packet.sources['prd']['id'], 'predecessor': packet.pk, 'operation_key': 'adopted-not-draft',
                'note': 'Reaffirm adopted facts while a successor is only proposed'}
        for kind, signature in packet.signatures.items():
            data.update({kind + '_signature': signature['evidence_id'], kind + '_party': signature['party_ref'],
                         kind + '_method': signature['method'], kind + '_locator': signature['locator'], kind + '_verified': 'on'})
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        successor = latest(self.case)
        self.assertNotEqual(successor.pk, packet.pk)
        self.assertEqual(self.client.post(self.url, {'action': 'signature_reaffirm', 'revision': rev(self.case), 'packet': successor.pk}).status_code, 302)
        self.assertEqual(assert_current_signed_baseline(self.case).pk, successor.pk)
        self.assertEqual(BaselineAdoption.objects.count(), 1)
        self.assertEqual(Baseline.objects.get(case=self.case).sow_id, adoption.after['sow_id'])


class CurrentFactorySignatureTests(TestCase):
    def test_native_release_and_direct_sql_recertification_hold_revoked_signature_contract(self):
        from tests.test_factory_delivery import setup, release_sources
        from apps.workflows import factory, factory_delivery
        from apps.workflows.models import FactoryWork
        from apps.pmo import delivery
        f = setup(); release_sources(f)
        factory.run_until_wait(f.work.pk); f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        packet = CommercialSignatureUse.objects.get(packet__case=f.case).packet
        transition(f.actor, packet.policy_id, 'revoked')
        with self.assertRaises(PolicyHold): delivery.readiness_inputs(f.d)
        with self.assertRaises((ValidationError, PolicyHold)): factory_delivery.verify(f.work)
        with self.assertRaisesMessage(DatabaseError, 'Current PMO claim requires exact current two-document'), transaction.atomic():
            FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        # No historical readiness record is removed by revocation.
        self.assertTrue(f.d.records.filter(kind='release_ready').exists())

    def test_native_milestone_and_direct_sql_require_current_signature_proof(self):
        from tests.helpers import signed
        from apps.pmo.services import complete_milestone
        from apps.pmo.models import Milestone
        actor, case = setup_case()
        signed(actor, case)
        proof = add_evidence(actor, case.pk, 'completion', 'Actual synthetic completion', 'synthetic:completion')
        first = complete_milestone(actor, case.pk, 'Before revocation', proof.pk, rev(case))
        packet = CommercialSignatureUse.objects.get(packet__case=case).packet
        transition(actor, packet.policy_id, 'revoked')
        with self.assertRaises(PolicyHold): complete_milestone(actor, case.pk, 'After revocation', proof.pk, rev(case))
        with self.assertRaisesMessage(DatabaseError, 'Current PMO claim requires exact current two-document'), transaction.atomic():
            Milestone.objects.create(case=case, name='Forged current completion', evidence=proof, completed_by=actor)
        self.assertTrue(Milestone.objects.filter(pk=first.pk).exists())
