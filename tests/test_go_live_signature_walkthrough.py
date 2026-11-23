import json
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Audit, Case, Evidence
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.finance.models import Handoff
from apps.identity import staff
from apps.identity.models import Grant, StaffAdmission
from apps.pmo import delivery
from apps.pmo.models import Milestone
from apps.workflows import factory_go_live as go_live, factory_progress
from apps.workflows.models import FactoryProgress, FactoryWork, HumanTask, Outbox
from tests import railway_admitted_schedule_seed as admission_seed, railway_go_live_signature_walkthrough_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
@patch.object(factory_progress, 'WAIT_INTERVAL', timedelta(0))
class GoLiveSignatureWalkthroughTests(TestCase):
    def test_separate_reviewer_delivers_once_then_admitted_pm_attests_two_exact_signatures(self):
        self.assertEqual(connection.vendor, 'postgresql')
        existing = configured()
        origin = existing['scopes'][0]['case']
        invitation, token = staff.invite(existing['actor'], origin.pk, seed.ADMITTED_USERNAME,
            'Sample project manager', 'sample-signature-pm@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader')
        witness = staff.accept(token, 'Synthetic!go-live.sample.816')
        reviewer = get_user_model().objects.create_user('psl-agent-trial')
        origin_revision = rev(origin)
        original_audits = list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True))

        def launch():
            output = StringIO()
            with redirect_stdout(output):
                seed.run()
            prefix, payload = output.getvalue().strip().split('=', 1)
            self.assertEqual(prefix, seed.GUARD)
            return json.loads(payload)

        with patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, witness.pk), ADMITTED_STAFF_CASE=origin.pk):
            with patch.dict('os.environ', {seed.GUARD: ''}):
                with self.assertRaisesMessage(RuntimeError, 'go-live signature fixture guard'):
                    seed.run()
            self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
            sample = launch()
            self.assertEqual(launch(), sample | {'preserved': True})

        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        case = work.case
        dossier = delivery.dossier_for(case, sample['dossier'])
        version = go_live.document(work)
        self.assertEqual((version.pk, version.created_by_id), (sample['report'], sample['author']))
        self.assertEqual(len({version.created_by_id, sample['publisher'], reviewer.pk, witness.pk}), 4)
        self.assertTrue(HumanTask.objects.filter(version=version, status='open', required_role='PMO Lead').exists())
        self.assertEqual(dossier.records.get(kind='release_outcome').pk, sample['release'])
        self.assertFalse(dossier.records.filter(kind__in=('go_live', 'go_live_reaffirmation')).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(version.reviews.exists())
        progress = FactoryProgress.objects.get(work=work, pk=sample['background'], requested_by_id=sample['author'])
        self.assertEqual(factory_progress.run_once(), progress.pk)
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        decisions, response = sample['decision_path'], sample['response_path']

        def post(path, action, **fields):
            work.refresh_from_db()
            return self.client.post(path, {'action': action, 'revision': work.revision, 'case_revision': rev(case),
                                           'version': version.pk, **fields})

        def approve():
            return post(decisions, 'review', verdict='approve', note='Independent review of the exact fictional go-live report.')

        self.client.force_login(witness)
        self.assertNotContains(self.client.get(decisions), 'Approve exact client report')
        self.assertNotContains(self.client.get(response), 'Record actual sign-off for this report')
        self.assertEqual(approve().status_code, 403)
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(decisions), 'Approve exact client report')
        self.assertRedirects(approve(), decisions, fetch_redirect_response=False)
        self.assertEqual(version.reviews.get().actor_id, reviewer.pk)
        for _ in range(24):
            self.assertEqual(factory_progress.run_once(), progress.pk)
            receipt = PublicationReceipt.objects.filter(publication__factory_work=work).first()
            if receipt:
                break
        else:
            work.refresh_from_db()
            self.fail(f'The existing request did not deliver the reviewed sample: {work.finding}')
        self.assertEqual((receipt.publication.actor_id, receipt.recipient_id, receipt.publication.version_id),
                         (sample['publisher'], sample['author'], version.pk))
        job = PublicationJob.objects.get(publication=receipt.publication)
        self.assertEqual(job.status, 'confirmed')
        self.assertFalse(dossier.records.filter(kind='go_live').exists())
        self.assertNotContains(self.client.get(response), 'Record actual sign-off for this report')

        self.client.force_login(witness)
        ready = self.client.get(response)
        self.assertContains(ready, 'Record actual sign-off for this report')
        self.assertNotContains(ready, 'Approve exact client report')
        self.assertNotContains(ready, 'Continue eligible work')

        def source(role):
            url = reverse('case', args=[case.pk])
            name = f'synthetic:go-live-{role.lower()}-written-copy'
            record = self.client.post(url, {'action': 'evidence', 'revision': rev(case), 'kind': 'signature',
                'source': name, 'body': f'Fictional {role} written sign-off on exact delivered report {version.pk}, receipt {receipt.pk}.'})
            self.assertRedirects(record, url, fetch_redirect_response=False)
            return Evidence.objects.get(case=case, created_by=witness, source=name)

        pm, client = source('PM'), source('Client')
        signed_at = timezone.now().isoformat()
        fields = {'receipt': receipt.pk, 'pm_signature': pm.pk, 'client_signature': client.pk,
                  'note': 'Recorded two separate fictional signatures on this exact delivered report.'}
        for role, proof in (('pm', pm), ('client', client)):
            values = {'source_system': 'synthetic-local-test', 'source_reference': proof.source,
                      'decision_id': f'SAMPLE-{role}-signoff-{version.pk}', 'decision_version': '1',
                      'signer_reference': f'SAMPLE-{role}-witness', 'signed_at': signed_at}
            fields.update({f'{role}-fact-{key}': value for key, value in values.items()})

        duplicate = post(response, 'accept', **(fields | {'client_signature': pm.pk}))
        self.assertContains(duplicate, 'Choose a different source record for each signature.')
        future = post(response, 'accept', **(fields | {'client-fact-signed_at': (timezone.now() + timedelta(hours=1)).isoformat()}))
        self.assertContains(future, 'Actual signed-at must be after actual release and not in the future')
        self.assertFalse(dossier.records.filter(kind='go_live').exists())
        self.assertRedirects(post(response, 'accept', **fields), response, fetch_redirect_response=False)
        accepted = dossier.records.get(kind='go_live')
        self.assertEqual((accepted.actor_id, accepted.data['receipt_id'], accepted.data['pm_signature_id'],
                          accepted.data['client_signature_id']), (witness.pk, receipt.pk, pm.pk, client.pk))
        self.assertFalse(Grant.objects.filter(case=case, user=witness, action__in=(
            'document.review_controlled', 'document.publish', 'factory.execute', 'factory.manage',
        )).exists())
        for _ in range(20):
            self.assertEqual(factory_progress.run_once(), progress.pk)
            work.refresh_from_db()
            if work.status == 'verified':
                break
        else:
            self.fail(f'The original background request did not verify sign-off: {work.finding}')
        self.assertEqual(go_live.verify(work)['acceptance'], accepted.pk)
        self.client.force_login(reviewer)
        self.assertContains(self.client.get(sample['recovery_path']), 'Actual PM and Client sign-off recorded')
        self.assertNotContains(self.client.get(response), 'Record actual sign-off for this report')
        self.assertEqual(Publication.objects.filter(factory_work=work).count(), 1)
        self.assertEqual(PublicationReceipt.objects.filter(publication__factory_work=work).get().pk, receipt.pk)
        self.assertEqual(dossier.records.get(kind='release_outcome').pk, sample['release'])
        self.assertFalse(Milestone.objects.filter(case=case).exists())
        self.assertFalse(Outbox.objects.filter(case=case).exists())
        self.assertFalse(Handoff.objects.filter(case=case).exists())
        admission = StaffAdmission.objects.get(invitation=invitation, user=witness)
        self.assertEqual(seed.prepare(witness, reviewer, admission), sample | {'preserved': True})
        self.assertEqual(rev(origin), origin_revision)
        self.assertEqual(list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True)), original_audits)
