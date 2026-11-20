import json
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from adapters import case_uploads, client_uat as contract
from apps.agents.models import AgentJob, CaseUpload
from apps.core.models import Audit, Case
from apps.identity import staff
from apps.identity.models import Grant
from apps.pmo import delivery, delivery_workarounds
from apps.pmo.models import DeliverySource, Issue
from apps.workflows import factory_delivery
from apps.workflows.models import FactoryProgress, FactoryWork
from tests import railway_admitted_schedule_seed as admission_seed, railway_planning_workaround_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


class SampleBucket:
    def __init__(self):
        self.files = {}

    def put_object(self, *, Key, Body, **kwargs):
        self.files[Key] = Body

    def get_object(self, *, Key, **kwargs):
        return {'Body': BytesIO(self.files[Key])}


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class PlanningWorkaroundWalkthroughTests(TestCase):
    def test_admitted_pm_links_existing_review_then_distinct_trial_approves_only_planning(self):
        self.assertEqual(connection.vendor, 'postgresql')
        staff_fixture = configured()
        origin = staff_fixture['scopes'][0]['case']
        invitation, token = staff.invite(staff_fixture['actor'], origin.pk, seed.ADMITTED_USERNAME, 'Sample project manager',
            'sample-project-manager@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader')
        pm = staff.accept(token, 'Synthetic!planning.sample.816')
        lead = get_user_model().objects.create_user('psl-agent-trial')
        original_revision = rev(origin)
        original_audits = list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True))
        bucket = SampleBucket()

        def launch():
            output = StringIO()
            with redirect_stdout(output):
                seed.run()
            prefix, payload = output.getvalue().strip().split('=', 1)
            self.assertEqual(prefix, seed.GUARD)
            return json.loads(payload)

        with (patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, pm.pk), ADMITTED_STAFF_CASE=origin.pk),
              patch.object(case_uploads, 'bucket', return_value=(bucket, 'fictional-sample-bucket'))):
            with patch.dict('os.environ', {seed.GUARD: ''}):
                with self.assertRaisesMessage(RuntimeError, 'Planning workaround fixture guard'):
                    seed.run()
            self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
            sample = launch()
            self.assertEqual(launch(), sample | {'preserved': True})
            self.assertEqual(len(bucket.files), 1)
            self.assertNotEqual(sample['case'], str(origin.pk))
            self.assertEqual(rev(origin), original_revision)
            self.assertEqual(list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True)), original_audits)

            work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
            dossier = delivery.dossier_for(work.case, sample['dossier'])
            returned = delivery.latest(dossier, 'planning_decision')
            self.assertEqual((returned.pk, returned.actor_id, returned.data['verdict']), (sample['returned'], lead.pk, 'return'))
            response = DeliverySource.objects.get(dossier=dossier, pk=sample['response'], kind=contract.RESPONSE)
            review = response.verifications.get(pk=sample['review'], adapter=contract.REVIEW)
            self.assertEqual(response.actor_id, pm.pk)
            self.assertEqual(review.actor_id, work.actor_id)
            self.assertEqual(len({response.actor_id, review.actor_id, lead.pk}), 3)
            self.assertFalse(AgentJob.objects.filter(upload_id=sample['upload']).exists())
            self.assertEqual(CaseUpload.objects.get(pk=sample['upload']).actor_id, pm.pk)
            self.assertFalse(dossier.candidate.gates.exists())
            self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
            path = sample['decision_path']

            self.client.force_login(lead)
            self.assertContains(self.client.get(path), sample['issue_ref'])
            self.assertNotContains(self.client.get(path), 'Approve exact Planning exit')
            self.assertNotContains(self.client.get(path), 'Link reviewed client workaround')
            self.client.force_login(pm)
            self.assertContains(self.client.get(path), 'Link reviewed client workaround')
            self.assertContains(self.client.get(sample['client_path']), response.payload['workaround'])
            command = {'action': 'delivery_workaround', 'revision': work.revision, 'case_revision': rev(work.case),
                       'return_id': returned.pk, 'issue_state_id': sample['issue_state'], 'response_id': response.pk,
                       'review_id': review.pk, 'note': 'The written acceptance covers this exact sample issue and build.'}
            self.assertContains(self.client.post(path, command | {'issue_state_id': sample['issue_state'] + 1}),
                                'The linked issue changed.')
            self.assertFalse(dossier.sources.filter(kind=delivery_workarounds.KIND).exists())
            self.assertRedirects(self.client.post(path, command), path, fetch_redirect_response=False)
            link = dossier.sources.get(kind=delivery_workarounds.KIND)
            self.assertEqual((link.actor_id, link.payload['return_id'], link.payload['review_id']),
                             (pm.pk, returned.pk, review.pk))
            self.assertNotContains(self.client.get(path), 'Approve exact Planning exit')

            self.client.force_login(lead)
            page = self.client.get(path)
            self.assertContains(page, 'Approve exact Planning exit')
            self.assertContains(page, response.payload['workaround'])
            work.refresh_from_db()
            decision = {'action': 'delivery_decision', 'revision': work.revision, 'case_revision': rev(work.case),
                        'packet': factory_delivery.projection(lead, work)['decision_packet'], 'verdict': 'approve',
                        'evidence': sample['planning_evidence'], 'note': 'Independently checked this exact Planning update.'}
            self.assertRedirects(self.client.post(path, decision), path, fetch_redirect_response=False)
            approved = delivery.approved_plan(dossier)
            self.assertEqual((approved.actor_id, approved.parent_id, approved.data['issue_remedy']['source_id']),
                             (lead.pk, returned.pk, link.pk))
            issue = Issue.objects.select_related('current').get(pk=sample['issue'])
            self.assertEqual((issue.current.status, issue.current_id), ('Open', sample['issue_state']))
            self.assertContains(self.client.get(path), 'Previous decision')
            self.assertFalse(dossier.records.exclude(kind='planning_decision').exists())
            self.assertFalse(dossier.candidate.gates.exists())
            self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
            self.assertEqual(launch(), sample | {'preserved': True})
            self.assertEqual(len(bucket.files), 1)
            self.assertEqual(delivery.approved_plan(dossier).pk, approved.pk)
