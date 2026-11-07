"""Literal PMO catalogue examples, synthetic owners and native PostgreSQL services.

These are bounded regressions, not process acceptance or live source authenticity.
P22's independent UI target/version correlation is deliberately NOT claimed here.
"""
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Evidence
from apps.core.services import add_evidence
from apps.documents.controlled import baseline_manifest, register_template, reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt, Version
from apps.identity.models import Grant
from apps.pmo import delivery
from apps.pmo.delivery_closure import archive_artifacts, finance_inputs, confirm_finance
from apps.pmo.gates import register_candidate
from apps.pmo.meetings import record_meeting
from apps.pmo.models import DeliveryRecord, DeliverySourceVerification, MeetingVersion, Milestone
from apps.pmo.reporting import draft_minutes
from apps.pmo.services import complete_milestone
from apps.workflows.services import run_once
from tests.document_helpers import artifact
from tests.helpers import rev
from tests.meeting_helpers import MINUTES_DEFINITION
from tests.test_delivery import DeliveryFixture


def rows(*models):
    return {model._meta.db_table: list(model.objects.order_by('pk').values()) for model in models}


class PMOExactCatalogueTests(TestCase):
    def delivery_fixture(self):
        self.assertEqual(connection.vendor, 'postgresql')
        f = DeliveryFixture()
        f.setup_delivery()  # Native P20 two-document packet/use, never raw signed-pointer edits.
        return f

    def planning_sources(self, f, missing=None):
        sources = {}
        for kind in delivery.PLANNING:
            if kind != missing:
                evidence = f.evidence(kind, 'Synthetic distinct owner artifact: ' + kind)
                payload = {'requires_ui': False, 'client_signoff_required': False} if kind == 'ui_applicability' else {}
                sources[kind] = f.source(kind, payload, evidence)
        return sources

    def test_p11_m01_minutes_and_final_results_owned_versioned_repository_and_reader_denial(self):
        f = self.delivery_fixture()
        f.accepted()
        definition = deepcopy(MINUTES_DEFINITION)
        definition['internal_review_required'] = False
        template = register_template(f.actor, f.case.pk, 'P11 formal minutes', definition,
                                     f.e['policy_decision'].pk, rev(f.case))
        storage = artifact(f.actor, f.case, 'D11.template_storage_retention_rules',
            'schema:psl/document-storage/v2', {'template_ids': [f.t.pk, template.pk],
                'repository': 'internal-versioned', 'retention_days': 30,
                'closure_inventory': {'required_kinds': ['technical_document', 'test_results', 'project_artifact'],
                                      'archive_mode': 'immutable_local_manifest'}}, f.e['policy_decision'])
        notes = f.evidence('meeting_notes', 'P11 MINUTES PRIVATE: actual final review')
        meeting = record_meeting(f.actor, f.case.pk, 'P11-FINAL-REVIEW', 'status', timezone.now(),
            'Final test results review', 'P11 MINUTES PRIVATE: retain actual findings', [f.actor.pk], [], notes.pk, rev(f.case))
        minutes = draft_minutes(f.actor, f.case.pk, meeting.meeting_id, template.pk, 'internal', rev(f.case))
        publication = reserve_publication(f.actor, f.case.pk, minutes.version_id, rev(f.case))
        self.assertTrue(run_publication_once(case_id=f.case.pk, job_id=publication.job.pk))
        receipt = PublicationReceipt.objects.get(publication=publication, recipient=f.actor)
        inventory = {kind: f.evidence(kind, 'P11 FINAL RESULTS PRIVATE' if kind == 'test_results' else 'P11 ' + kind).pk
                     for kind in ['technical_document', 'test_results', 'project_artifact']}
        f.source('technical_finalization', evidence=Evidence.objects.get(pk=inventory['technical_document']))
        archive = archive_artifacts(f.actor, f.case.pk, f.d.pk, inventory, f.e['requirements'].pk,
                                   'P11 exact immutable repository inventory', rev(f.case))
        version = Version.objects.select_related('document').get(pk=minutes.version_id)
        final = Evidence.objects.get(pk=inventory['test_results'])
        self.assertEqual(version.document.case_id, f.case.pk)
        self.assertEqual(version.document.owner_id, f.actor.pk)
        self.assertEqual(version.number, 1)
        self.assertEqual(version.document.current_id, version.pk)
        self.assertEqual(minutes.manifest['meeting_version'], meeting.pk)
        self.assertEqual(final.case_id, f.case.pk)
        self.assertEqual(final.created_by_id, f.actor.pk)
        self.assertEqual(final.version, 1)
        self.assertEqual(archive.snapshot['inventory']['test_results'],
                         {'id': final.pk, 'version': final.version, 'sha256': final.sha256})
        self.assertEqual(archive.snapshot['repository'], 'internal-versioned')
        self.assertEqual(archive.snapshot['policy_id'], storage.pk)
        self.assertEqual(publication.policies['D11.template_storage_retention_rules'], storage.pk)
        self.assertEqual(receipt.payload_sha256, version.payload_sha256)
        self.assertEqual(receipt.publication.version_id, version.pk)
        self.assertTrue(version.source_manifest)
        self.assertTrue(all(Evidence.objects.filter(case=f.case, pk=p['id'], version=p['version'], sha256=p['sha256']).exists()
                            for p in version.source_manifest))
        # Stable database IDs are the internal-versioned repository locators, not a claimed remote SharePoint deployment.
        before = rows(Evidence, MeetingVersion, Version, PublicationReceipt, DeliveryRecord)
        self.client.force_login(f.actor)
        self.assertContains(self.client.get(reverse('documents', args=[f.case.pk])), 'P11-FINAL-REVIEW')
        self.assertContains(self.client.get(reverse('delivery', args=[f.case.pk])), 'internal-versioned')
        finance_reader = get_user_model().objects.create_user('p11-finance-only')
        Grant.objects.bulk_create([Grant(case=f.case, user=finance_reader, action=a) for a in ['case.read', 'finance.read']])
        self.client.force_login(finance_reader)
        for endpoint in ['documents', 'delivery']:
            response = self.client.get(reverse(endpoint, args=[f.case.pk]))
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, 'P11 MINUTES PRIVATE', status_code=403)
            self.assertNotContains(response, 'P11 FINAL RESULTS PRIVATE', status_code=403)
        self.assertNotContains(self.client.get(reverse('document_inbox')), 'P11 MINUTES PRIVATE')
        self.assertEqual(before, rows(Evidence, MeetingVersion, Version, PublicationReceipt, DeliveryRecord))
        for model, pk, field, value in [(Version, version.pk, 'number', 99),
                                       (Evidence, final.pk, 'version', 99),
                                       (DeliveryRecord, archive.pk, 'snapshot', {})]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=pk).update(**{field: value})
        self.assertEqual(before, rows(Evidence, MeetingVersion, Version, PublicationReceipt, DeliveryRecord))

    def test_p12_m01_one_signed_baseline_two_distinct_completion_handoffs_no_invoice(self):
        from apps.finance.models import Handoff, SignedBaselineIntake, Invoice, InvoicePreparation
        from apps.pmo.commercial import capture_response, adopt_signed
        from apps.pmo.models import BaselineAdoption, CommercialSignatureUse
        from apps.workflows.models import Outbox
        from adapters.signed_baselines import InternalSignedBaselineAdapter
        from tests.signature_helpers import packet_for
        from tests.test_commercial_changes import fixture, proposal, approvals, delivered

        actor, case, evidence, template = fixture(username='p12-owner')
        revision = proposal(actor, case, evidence)
        approvals(actor, case, revision)
        client_receipt = delivered(actor, case, revision, template)
        response = capture_response(actor, case.pk, revision.pk, client_receipt.pk, 'signed',
                                    evidence['signature'].pk, 'Exact source SOW signature received', rev(case))
        packet = packet_for(actor, case, evidence, revision)
        adoption = adopt_signed(actor, case.pk, revision.pk, response.pk, rev(case))
        intake = SignedBaselineIntake.objects.get(adoption=adoption)
        baseline = baseline_manifest(case)
        self.assertEqual(adoption.after, baseline)
        self.assertEqual(intake.payload['signature_packet']['id'], packet.pk)
        self.assertEqual(intake.payload['sources']['signed']['id'], baseline['signed_id'])
        self.assertEqual(intake.payload['signature_packet']['sources'], packet.sources)
        self.assertEqual(CommercialSignatureUse.objects.get(adoption=adoption).packet_id, packet.pk)
        candidate = register_candidate(actor, case.pk, 'P12-signed-candidate', evidence['requirements'].pk, rev(case))
        dossier = delivery.open_dossier(actor, case.pk, candidate.pk, evidence['plan'].pk,
                                       'P12 fixed signed baseline for two reached milestones', rev(case))
        milestones = []
        for name in ['M1', 'M2']:
            completion = add_evidence(actor, case.pk, 'completion', 'Actual synthetic completed milestone ' + name, 'synthetic:p12:' + name)
            milestone = complete_milestone(actor, case.pk, name, completion.pk, rev(case))
            milestones.append(milestone)
            self.assertTrue(run_once())
            handoff = Handoff.objects.get(milestone=milestone)
            self.assertEqual(handoff.case_id, case.pk)
            self.assertEqual(handoff.payload, {'milestone_id': milestone.pk, 'name': name,
                'evidence_id': completion.pk, 'evidence_sha256': completion.sha256})
            self.assertEqual(baseline_manifest(case), baseline)
        handoffs = list(Handoff.objects.filter(case=case).order_by('milestone_id'))
        self.assertEqual(len(handoffs), 2)
        self.assertEqual(len({h.operation_key for h in handoffs}), 2)
        self.assertEqual(Outbox.objects.filter(case=case, status='confirmed').count(), 2)
        expected = [[m.pk, h.pk, h.operation_key] for m, h in zip(milestones, handoffs)]
        self.assertEqual(finance_inputs(dossier), {'milestones': expected})
        confirmation = confirm_finance(actor, case.pk, dossier.pk, [m.pk for m in milestones], True,
            evidence['completion'].pk, 'Finance confirms both exact completion receipts', rev(case))
        self.assertEqual(confirmation.snapshot, {'milestones': expected})
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(InvoicePreparation.objects.count(), 0)
        before = rows(Milestone, Handoff, Outbox, SignedBaselineIntake, BaselineAdoption, CommercialSignatureUse)
        self.assertFalse(run_once())
        self.assertEqual(InternalSignedBaselineAdapter().deliver(adoption).pk, intake.pk)
        for milestone in milestones:
            with self.assertRaisesMessage(ValidationError, 'unique'):
                complete_milestone(actor, case.pk, milestone.name, milestone.evidence_id, rev(case))
        self.assertEqual(before, rows(Milestone, Handoff, Outbox, SignedBaselineIntake, BaselineAdoption, CommercialSignatureUse))
        self.assertEqual(SignedBaselineIntake.objects.filter(case=case).count(), 1)
        self.client.force_login(actor)
        page = self.client.get(reverse('case', args=[case.pk]))
        self.assertContains(page, 'M1')
        self.assertContains(page, 'M2')
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(InvoicePreparation.objects.count(), 0)
        # Notification schema is deliberately narrow. This proves the unchanged-baseline chain,
        # not a per-notification baseline FK or changed-baseline reconciliation.

    def test_p24_m02_approved_test_strategy_cannot_substitute_for_missing_uat_approach(self):
        f = self.delivery_fixture()
        sources = self.planning_sources(f, missing='uat_approach')
        strategy, proof = delivery.verified_source(f.d, 'test_strategy')
        self.assertEqual(strategy.pk, sources['test_strategy'].pk)
        self.assertEqual(proof.result['owner'], 'QA Lead')
        self.assertFalse(f.d.sources.filter(kind='uat_approach').exists())
        before = rows(DeliveryRecord, DeliverySourceVerification)
        with self.assertRaisesMessage(ValidationError, 'uat_approach'):
            delivery.planning_inputs(f.d)
        with self.assertRaisesMessage(ValidationError, 'uat_approach'):
            delivery.decide_planning(f.actor, f.case.pk, f.d.pk, 'approve', f.e['plan'].pk,
                                    'QA strategy is not Product Owner UAT approval', rev(f.case))
        self.client.force_login(f.actor)
        page = self.client.get(reverse('delivery', args=[f.case.pk]))
        self.assertContains(page, 'Current source-verified evidence required: uat_approach')
        self.assertEqual(before, rows(DeliveryRecord, DeliverySourceVerification))
        uat = f.source('uat_approach', evidence=f.evidence('uat_approach', 'Separate Product Owner UAT approach'))
        uat_source, uat_proof = delivery.verified_source(f.d, 'uat_approach')
        self.assertEqual(uat_proof.result['owner'], 'Product Owner')
        self.assertNotEqual(uat.evidence_id, strategy.evidence_id)
        pins = delivery.planning_inputs(f.d)['sources']
        self.assertEqual(pins['test_strategy'], [strategy.pk, proof.pk])
        self.assertEqual(pins['uat_approach'], [uat_source.pk, uat_proof.pk])

    def test_p26_m02_old_approved_plan_does_not_hide_missing_current_technical_design_receipt(self):
        f = self.delivery_fixture()
        sources = self.planning_sources(f)
        old = delivery.decide_planning(f.actor, f.case.pk, f.d.pk, 'approve', f.e['plan'].pk,
                                      'Actual original complete plan approval', rev(f.case))
        self.assertEqual(delivery.approved_plan(f.d).pk, old.pk)
        current = f.source('technical_design', evidence=f.evidence('technical_design', 'Technical design v2 awaiting Engineering receipt'), verify=False)
        self.assertFalse(current.verifications.exists())
        self.assertTrue(sources['technical_design'].verifications.exists())
        before = rows(DeliveryRecord, DeliverySourceVerification)
        with self.assertRaisesMessage(ValidationError, 'technical_design'):
            delivery.approved_plan(f.d)
        with self.assertRaisesMessage(ValidationError, 'technical_design'):
            delivery.record_progress(f.actor, f.case.pk, f.d.pk, 'progress', f.e['plan'].pk,
                                     'Old PMO approval is not Engineering receipt', rev(f.case))
        self.client.force_login(f.actor)
        page = self.client.get(reverse('delivery', args=[f.case.pk]))
        self.assertContains(page, 'Current source-verified evidence required: technical_design')
        self.assertEqual(before, rows(DeliveryRecord, DeliverySourceVerification))
        delivery.verify_source(f.actor, f.case.pk, current.pk, rev(f.case))
        with self.assertRaisesMessage(ValidationError, 'Current exact Planning exit'):
            delivery.approved_plan(f.d)
        fresh = delivery.decide_planning(f.actor, f.case.pk, f.d.pk, 'approve', f.e['plan'].pk,
                                        'New Planning decision references new Engineering receipt', rev(f.case))
        self.assertNotEqual(fresh.pk, old.pk)
        self.assertEqual(delivery.approved_plan(f.d).pk, fresh.pk)
        self.assertEqual(DeliveryRecord.objects.get(pk=old.pk).snapshot, old.snapshot)

    def test_p27_m02_early_actual_kickoff_retained_without_compliant_execution_entry(self):
        f = self.delivery_fixture()
        occurred = timezone.now() - timedelta(hours=1)
        notes = f.evidence('meeting_notes', 'P27 actual early kickoff; plan not yet approved')
        meeting = record_meeting(f.actor, f.case.pk, 'P27-EARLY-KICKOFF', 'kickoff', occurred,
            'Scope timelines roles and expectations', 'Actual early meeting; Planning prerequisite unresolved',
            [f.actor.pk], [], notes.pk, rev(f.case))
        before = rows(MeetingVersion, DeliveryRecord)
        with self.assertRaisesMessage(ValidationError, 'planning_decision'):
            delivery.record_progress(f.actor, f.case.pk, f.d.pk, 'kickoff', notes.pk,
                                     'Retain actual meeting but do not claim compliant entry', rev(f.case), meeting.pk)
        self.assertEqual(before, rows(MeetingVersion, DeliveryRecord))
        self.planning_sources(f)
        plan = delivery.decide_planning(f.actor, f.case.pk, f.d.pk, 'approve', f.e['plan'].pk,
                                       'Later actual plan approval cannot move meeting time', rev(f.case))
        self.assertLess(meeting.occurred_at, plan.created_at)
        self.client.force_login(f.actor)
        before = rows(MeetingVersion, DeliveryRecord)
        page = self.client.post(reverse('delivery', args=[f.case.pk]), {'action': 'progress',
            'revision': rev(f.case), 'dossier': f.d.pk, 'kind': 'kickoff', 'evidence': notes.pk,
            'note': 'Old event is not a new compliant entry', 'meeting': meeting.pk})
        self.assertContains(page, 'Link the current actual kickoff meeting after Planning approval')
        self.assertEqual(before, rows(MeetingVersion, DeliveryRecord))
        stored = MeetingVersion.objects.get(pk=meeting.pk)
        self.assertEqual(stored.occurred_at, occurred)
        self.assertEqual(stored.evidence_id, notes.pk)
        self.assertEqual(stored.meeting.current_id, meeting.pk)
        self.assertFalse(f.d.records.filter(kind__in=['kickoff', 'release_ready', 'release_outcome']).exists())
        with self.assertRaises(DatabaseError), transaction.atomic():
            MeetingVersion.objects.filter(pk=meeting.pk).update(occurred_at=timezone.now())
        self.assertEqual(MeetingVersion.objects.get(pk=meeting.pk).occurred_at, occurred)
