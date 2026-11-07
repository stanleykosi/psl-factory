from copy import deepcopy
from uuid import uuid4
from django.test import TestCase
from django.db import connection, DatabaseError, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import transition, PolicyHold
from apps.policy.signature_validators import COMPONENT, SCHEMA
from apps.pmo.models import Baseline, BaselineSignatureExemption, CommercialSignatureUse, BaselineAdoption, DeliveryRecord
from apps.pmo.services import prepare_baseline, decide, sign_baseline, complete_milestone
from apps.pmo.signature_exemptions import record_exemption, assert_current_baseline_assurance, latest
from apps.pmo.signatures import capture_packet
from tests.helpers import rev, roles, setup_case
from tests.document_helpers import artifact
from tests.test_commercial_changes import fixture, proposal, approvals, delivered


class InternalApplicabilityTests(TestCase):
    def setUp(self):
        self.actor, self.case, self.e, self.template = fixture()
        prepare_baseline(self.actor, self.case.pk, self.e['plan'].pk, self.e['costing'].pk, self.e['sow'].pk, rev(self.case))
        for role in ['PM', 'Head of PMO', 'CEO', 'PMO Lead']:
            decide(self.actor, self.case.pk, role, rev(self.case))
        self.prd = add_evidence(self.actor, self.case.pk, 'prd', 'Synthetic actual internal PRD', 'synthetic:internal-prd')
        self.scope = add_evidence(self.actor, self.case.pk, 'internal_project_scope', 'Owner evidence: this synthetic project serves an internal unit only', 'synthetic:internal-scope')
        self.client.force_login(self.actor)
        self.url = f'/cases/{self.case.pk}/commercial/'

    def policy(self, requirement='not_applicable', applicability='internal_project', scope=None, parties=None, methods=None):
        value = {'parties': parties or [], 'methods': methods or [], 'assurance': 'human_verified_reference_only',
                 'unchanged_prd_signature_reuse': 'unconfigured', 'applicability': applicability,
                 'signature_requirement': requirement, 'scope_evidence_id': (scope or self.scope).pk if applicability == 'internal_project' else None,
                 'allow_synthetic': self.case.synthetic}
        return artifact(self.actor, self.case, COMPONENT, SCHEMA, value, self.e['policy_decision'])

    def capture(self):
        return record_exemption(self.actor, self.case.pk, self.prd.pk, 'Human records the actual owner internal applicability decision',
                                str(uuid4()), rev(self.case), getattr(latest(self.case), 'pk', None))

    def sql_current(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_pmo_baseline_assurance_current(%s), psl_pmo_signed_baseline_current(%s)', [self.case.pk, self.case.pk])
            return cursor.fetchone()

    def test_explicit_internal_exemption_http_is_unsigned_and_idempotent(self):
        from apps.finance.models import SignedBaselineIntake
        self.policy()
        data = {'action': 'signature_exemption', 'revision': rev(self.case), 'prd': self.prd.pk,
                'operation_key': 'owner-internal-proof', 'note': 'Actual internal scope and owner not-applicable decision'}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        row = BaselineSignatureExemption.objects.get(case=self.case)
        self.assertEqual(assert_current_baseline_assurance(self.case), {'kind': 'internal_signature_exemption', 'id': row.pk})
        self.assertEqual(self.sql_current(), (True, False))
        self.assertContains(self.client.post(self.url, data), 'Stale revision')
        data['revision'] = rev(self.case)
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(BaselineSignatureExemption.objects.count(), 1)
        self.assertIsNone(Baseline.objects.get(case=self.case).signed_id)
        self.assertFalse(CommercialSignatureUse.objects.exists())
        self.assertFalse(BaselineAdoption.objects.exists())
        self.assertFalse(SignedBaselineIntake.objects.exists())
        completion = add_evidence(self.actor, self.case.pk, 'completion', 'Actual synthetic internal milestone evidence', 'synthetic:completion')
        complete_milestone(self.actor, self.case.pk, 'Internal milestone', completion.pk, rev(self.case))
        self.assertIsNone(Baseline.objects.get(case=self.case).signed_id)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Baseline.objects.filter(case=self.case).update(signed=self.e['signature'])
        with self.assertRaises(DatabaseError), transaction.atomic():
            BaselineSignatureExemption.objects.filter(pk=row.pk).update(note='Rewrite exemption')

    def test_absent_and_unresolved_owner_choice_hold_only_dependent_claims(self):
        for configured in [False, True]:
            if configured: self.policy(requirement='unresolved', applicability='unresolved')
            prepare_baseline(self.actor, self.case.pk, self.e['plan'].pk, self.e['costing'].pk, self.e['sow'].pk, rev(self.case))
            with self.assertRaises(PolicyHold): self.capture()
            with self.assertRaises(PolicyHold): assert_current_baseline_assurance(self.case)
            self.assertEqual(self.sql_current(), (False, False))
            self.assertFalse(BaselineSignatureExemption.objects.exists())
        data = {'action': 'signature_contract', 'revision': rev(self.case), 'applicability': 'unresolved',
                'signature_requirement': 'unresolved', 'evidence': self.e['policy_decision'].pk,
                'effective_from': '2026-11-01T00:00:00Z'}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertFalse(self.case.evidence.filter(kind__in=['client_identity', 'internal_signer_identity']).exists())

    def test_internal_required_uses_real_owner_eligible_internal_signers(self):
        identity = add_evidence(self.actor, self.case.pk, 'internal_signer_identity', 'Synthetic owner-confirmed internal unit representative', 'synthetic:internal-signer')
        parties = [{'party_ref': 'internal-unit', 'display_name': 'Synthetic internal unit representative', 'identity_evidence_id': identity.pk, 'documents': ['sow', 'prd']}]
        self.policy(requirement='required', parties=parties, methods=['owner-reviewed-internal-file'])
        with self.assertRaises(ValidationError): self.capture()
        with self.assertRaises(ValidationError): assert_current_baseline_assurance(self.case)
        prd_signature = add_evidence(self.actor, self.case.pk, 'signature', 'Actual synthetic internal PRD signature reference', 'synthetic:prd-signature')
        signatures = {kind: {'evidence_id': source.pk, 'party_ref': 'internal-unit', 'method': 'owner-reviewed-internal-file',
                            'locator': kind + ':signature', 'human_verified': True}
                      for kind, source in [('sow', self.e['signature']), ('prd', prd_signature)]}
        capture_packet(self.actor, self.case.pk, self.prd.pk, signatures, 'Human checked actual eligible internal signatures', 'internal-required', rev(self.case))
        sign_baseline(self.actor, self.case.pk, self.e['signature'].pk, rev(self.case))
        self.assertEqual(assert_current_baseline_assurance(self.case)['kind'], 'dual_document_signatures')
        self.assertEqual(self.sql_current(), (True, True))
        self.assertFalse(BaselineSignatureExemption.objects.exists())
        self.assertFalse(self.case.evidence.filter(kind='client_identity').exists())

    def test_client_scope_cannot_claim_exemption_and_contrary_delivery_revokes_currentness(self):
        with self.assertRaises(ValidationError): self.policy(applicability='client_project')
        self.policy(); row = self.capture()
        revision = proposal(self.actor, self.case, self.e)
        approvals(self.actor, self.case, revision)
        receipt = delivered(self.actor, self.case, revision, self.template)
        with self.assertRaisesMessage(ValidationError, 'contradict'): assert_current_baseline_assurance(self.case)
        with self.assertRaisesMessage(ValidationError, 'contradict'): self.capture()
        self.assertEqual(self.sql_current(), (False, False))
        self.assertTrue(BaselineSignatureExemption.objects.filter(pk=row.pk).exists())
        self.assertIsNotNone(receipt.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            BaselineSignatureExemption.objects.create(case=self.case, sources=row.sources, approval_refs=row.approval_refs,
                scope_evidence=self.scope, policy=row.policy, authority=row.authority, actor=self.actor, predecessor=row,
                note='Forged contradictory exemption', operation_key='forged-contradiction')

    def test_role_policy_and_source_changes_hold_current_proof_but_keep_history(self):
        policy = self.policy(); first = self.capture()
        Grant.objects.filter(case=self.case, user=self.actor, action='baseline.sign').update(active=False)
        with self.assertRaises(PermissionDenied): assert_current_baseline_assurance(self.case)
        self.assertEqual(self.sql_current(), (False, False))
        Grant.objects.filter(case=self.case, user=self.actor, action='baseline.sign').update(active=True)
        from apps.policy.services import active_component
        from tests.helpers import activate
        prior_roles = active_component('D05.role_principal_assignments', self.case)
        activate(self.actor, self.case, prior_roles.component, prior_roles.envelope['value'], self.e['policy_decision'])
        with self.assertRaises(ValidationError): assert_current_baseline_assurance(self.case)
        second = self.capture()
        self.assertEqual(second.approval_refs, first.approval_refs)
        self.assertEqual(self.sql_current(), (True, False))
        transition(self.actor, policy.pk, 'revoked')
        with self.assertRaises(PolicyHold): assert_current_baseline_assurance(self.case)
        self.policy()
        with self.assertRaises(ValidationError): assert_current_baseline_assurance(self.case)
        self.capture()
        successor = add_evidence(self.actor, self.case.pk, 'sow', 'New actual prepared internal scope document', 'synthetic:new-internal-sow')
        prepare_baseline(self.actor, self.case.pk, self.e['plan'].pk, self.e['costing'].pk, successor.pk, rev(self.case))
        with self.assertRaises(ValidationError): assert_current_baseline_assurance(self.case)
        self.assertEqual(self.sql_current(), (False, False))
        self.assertEqual(BaselineSignatureExemption.objects.count(), 3)
        self.assertIsNone(Baseline.objects.get(case=self.case).signed_id)

    def test_cross_case_scope_and_forged_unsigned_proof_are_rejected(self):
        other_actor, other = setup_case(username='other-internal-owner')
        foreign = add_evidence(other_actor, other.pk, 'internal_project_scope', 'Other project scope', 'synthetic:foreign-scope')
        with self.assertRaises(ValidationError): self.policy(scope=foreign)
        self.policy(); row = self.capture()
        foreign_prd = add_evidence(other_actor, other.pk, 'prd', 'Other PRD', 'synthetic:foreign-prd')
        with self.assertRaises(ValidationError):
            record_exemption(self.actor, self.case.pk, foreign_prd.pk, 'Wrong project', 'foreign', rev(self.case), row.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            BaselineSignatureExemption.objects.create(case=other, sources=row.sources, approval_refs=row.approval_refs,
                scope_evidence=self.scope, policy=row.policy, authority=row.authority, actor=self.actor,
                note='Forged other-case internal proof', operation_key='foreign-forgery')
        self.assertEqual(BaselineSignatureExemption.objects.count(), 1)

    def test_new_exemption_cannot_forge_obsolete_prd_but_adopted_proof_survives_drafts(self):
        from apps.pmo.signatures import pin
        from apps.pmo.services import baseline_approval_refs
        from apps.policy.services import role_policy
        policy = self.policy()
        baseline = Baseline.objects.get(case=self.case)
        sources = {key: pin(getattr(baseline, key)) for key in ['plan', 'costing', 'sow']}
        sources['prd'] = pin(self.prd)
        next_prd = add_evidence(self.actor, self.case.pk, 'prd', 'New proposed internal PRD', 'synthetic:new-prd')
        with self.assertRaises(ValidationError): self.capture()
        with self.assertRaises(DatabaseError), transaction.atomic():
            BaselineSignatureExemption.objects.create(case=self.case, sources=sources,
                approval_refs=baseline_approval_refs(self.case, baseline), scope_evidence=self.scope, policy=policy,
                authority=role_policy(self.actor, self.case, 'PM'), actor=self.actor,
                note='Forged first proof with obsolete PRD', operation_key='obsolete-prd')
        self.prd = next_prd
        proof = self.capture()
        add_evidence(self.actor, self.case.pk, 'prd', 'Another unadopted proposal', 'synthetic:unadopted-prd')
        self.assertEqual(assert_current_baseline_assurance(self.case)['id'], proof.pk)
        self.assertEqual(self.sql_current(), (True, False))

    def test_internal_release_factory_uses_explicit_exemption_and_rechecks_sql_currentness(self):
        import json
        from pathlib import Path
        from django.utils import timezone
        from tests.test_delivery import DeliveryFixture
        from tests.test_factory_delivery import release_sources
        from apps.pmo.gates import register_candidate
        from apps.pmo.delivery import open_dossier, readiness_inputs
        from apps.workflows import factory, factory_delivery
        from apps.workflows.models import FactoryWork
        from apps.policy.operator_drafts import draft_operator_policy
        policy = self.policy(); exemption = self.capture()
        f = DeliveryFixture(); f.actor, f.case, f.e = self.actor, self.case, self.e
        f.candidate = register_candidate(self.actor, self.case.pk, 'internal-build', self.e['requirements'].pk, rev(self.case))
        f.d = open_dossier(self.actor, self.case.pk, f.candidate.pk, self.e['plan'].pk, 'Owner internal project plan scope', rev(self.case))
        value = json.loads(Path('fixtures/factory-delivery.json').read_text()); value.pop('classification')
        execution = draft_operator_policy(self.actor, self.case.pk, 'OPS.factory_delivery_execution', value, self.e['policy_decision'].pk, timezone.now())
        transition(self.actor, execution.pk, 'validated'); transition(self.actor, execution.pk, 'active')
        f.work = factory_delivery.start(self.actor, self.case.pk, 'INTERNAL-DELIVERY', f.d.pk, 'Internal release readiness', rev(self.case))
        release_sources(f); factory.run_until_wait(f.work.pk); f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        ready = DeliveryRecord.objects.get(dossier=f.d, kind='release_ready')
        self.assertIsNone(ready.snapshot['signed_id'])
        self.assertEqual(ready.snapshot['signature_requirement'], 'not_applicable')
        self.assertEqual(ready.snapshot['signature_exemption_id'], exemption.pk)
        forged = deepcopy(ready.snapshot); forged['signature_exemption_id'] += 999
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeliveryRecord.objects.create(dossier=f.d, kind='release_ready', parent=ready.parent, data=ready.data,
                snapshot=forged, evidence=ready.evidence, actor=self.actor)
        transition(self.actor, policy.pk, 'revoked')
        with self.assertRaises(PolicyHold): readiness_inputs(f.d)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactoryWork.objects.filter(pk=f.work.pk).update(status='verified')
        self.assertTrue(DeliveryRecord.objects.filter(pk=ready.pk).exists())
        self.assertIsNone(Baseline.objects.get(case=self.case).signed_id)
