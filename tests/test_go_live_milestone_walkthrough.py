"""Replay-preserving specimen for two separately authorised browser stations."""
import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Audit, Case, Evidence
from apps.documents.models import Publication, PublicationJob, PublicationReceipt
from apps.finance.models import Handoff, InvoicePreparation
from apps.identity import staff
from apps.identity.models import Grant, StaffAdmission
from apps.pmo.models import Milestone
from apps.policy.models import Configuration
from apps.workflows import factory_go_live as go_live, factory_go_live_milestone as milestone
from apps.workflows.models import FactoryProgress, FactoryWork, Outbox
from apps.workflows.services import run_once
from tests import railway_admitted_schedule_seed as admission_seed
from tests import railway_go_live_milestone_walkthrough_seed as seed
from tests.helpers import rev
from tests.test_staff_profiles import configured


@patch.dict('os.environ', {'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance', 'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                           'PGDATABASE': 'synthetic-preview', seed.GUARD: '1'})
@patch.object(admission_seed, 'ADMISSION_TENANT', 'staff-accounts')
@patch.object(admission_seed, 'ADMISSION_PROFILE', 'sample-reader')
class GoLiveMilestoneWalkthroughSeedTests(TestCase):
    def test_exact_verified_sample_requires_settings_operator_then_admitted_pm_and_separate_proof(self):
        self.assertEqual(connection.vendor, 'postgresql')
        origin_fixture = configured()
        origin = origin_fixture['scopes'][0]['case']
        invitation, token = staff.invite(
            origin_fixture['actor'], origin.pk, seed.ADMITTED_USERNAME, 'Sample project manager',
            'sample-milestone-pm@example.invalid', ['case.read'], rev(origin), profile_key='sample-reader',
        )
        pm = staff.accept(token, 'Synthetic!milestone.sample.648')
        operator = get_user_model().objects.create_user('psl-agent-trial')
        origin_revision = rev(origin)
        origin_audits = list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True))
        admission = StaffAdmission.objects.get(invitation=invitation, user=pm)

        with patch.multiple(seed, ADMITTED_IDENTITY=(invitation.pk, pm.pk), ADMITTED_STAFF_CASE=origin.pk):
            with patch.dict('os.environ', {seed.GUARD: ''}):
                with self.assertRaisesMessage(RuntimeError, 'go-live milestone fixture guard'):
                    seed.run()
            self.assertFalse(Case.objects.filter(tenant=seed.TENANT).exists())
            stdout = StringIO()
            with redirect_stdout(stdout):
                seed.run()
        key, data = stdout.getvalue().strip().split('=', 1)
        self.assertEqual(key, seed.GUARD)
        sample = json.loads(data)
        self.assertFalse(sample['preserved'])
        self.assertEqual(seed.prepare(pm, operator, admission), sample | {'preserved': True})

        work = FactoryWork.objects.select_related('case').get(pk=sample['work'])
        case = work.case
        url, policy_url = sample['work_path'], sample['policy_path']
        evidence_url = reverse('case', args=[case.pk])
        self.assertNotEqual(case.pk, origin.pk)
        self.assertEqual(work.status, 'verified')
        self.assertEqual(go_live.verify(work)['acceptance'], sample['acceptance'])
        receipt = PublicationReceipt.objects.get(publication__factory_work=work)
        self.assertEqual(receipt.pk, sample['receipt'])
        self.assertEqual(receipt.publication.actor_id, sample['publisher'])
        self.assertEqual(receipt.recipient_id, sample['sponsor'])
        self.assertEqual(receipt.publication.version_id, sample['report'])
        self.assertEqual(receipt.publication.version.reviews.get().actor_id, operator.pk)
        self.assertEqual(PublicationJob.objects.get(publication=receipt.publication).status, 'confirmed')
        self.assertFalse(FactoryProgress.objects.filter(work=work).exists())
        self.assertFalse(Configuration.objects.filter(case=case, component=seed.COMPONENT).exists())
        self.assertFalse(Milestone.objects.filter(case=case).exists())
        self.assertFalse(Outbox.objects.filter(case=case).exists())
        self.assertFalse(Handoff.objects.filter(case=case).exists())

        def post(action, **fields):
            return self.client.post(url, {
                'action': action, 'revision': work.revision, 'case_revision': rev(case), **fields,
            })

        mapping_data = {'milestone_name': sample['milestone_name'], 'owner_decision': sample['owner_decision']}
        self.client.force_login(pm)
        page = self.client.get(url)
        self.assertContains(page, 'Actual PM and Client sign-off recorded')
        self.assertNotContains(page, 'Milestone handoff settings')
        self.assertNotContains(page, 'Confirm milestone completion')
        self.assertEqual(post('draft_milestone_mapping', **mapping_data).status_code, 403)

        self.client.force_login(operator)
        self.assertContains(self.client.get(url), 'Milestone handoff settings')
        self.assertRedirects(post('draft_milestone_mapping', **mapping_data), policy_url, fetch_redirect_response=False)
        configuration = Configuration.objects.get(case=case, component=seed.COMPONENT)
        self.assertEqual(configuration.states.latest('pk').state, 'draft')
        for action in ('validated', 'active'):
            self.assertRedirects(self.client.post(policy_url, {
                'action': action, 'configuration': configuration.pk,
            }), policy_url, fetch_redirect_response=False)
        self.assertEqual(configuration.states.latest('pk').state, 'active')
        self.assertNotContains(self.client.get(url), 'Confirm milestone completion')
        self.assertFalse(Milestone.objects.filter(case=case).exists())
        self.assertFalse(Grant.objects.filter(case=case, user=operator, action='milestone.complete', active=True).exists())

        self.client.force_login(pm)
        self.assertContains(self.client.get(url), 'Add separate completion evidence to the project')
        self.assertNotContains(self.client.get(url), 'Confirm milestone completion')
        self.assertRedirects(self.client.post(evidence_url, {
            'action': 'evidence', 'revision': rev(case), 'kind': 'completion', 'source': 'synthetic:milestone-walkthrough-proof',
            'body': 'Fictional PM confirms the approved rollout milestone was reached. This is a separate record of completion.',
        }), evidence_url, fetch_redirect_response=False)
        evidence = Evidence.objects.get(case=case, created_by=pm, kind='completion')
        page = self.client.get(url)
        self.assertContains(page, 'Confirm milestone completion')
        self.assertEqual([item['pk'] for item in page.context['milestone_panel']['completion']['sources']], [evidence.pk])
        self.assertRedirects(post('record_milestone', milestone_mapping=configuration.pk, acceptance=sample['acceptance'],
                                  completion_evidence=evidence.pk), url, fetch_redirect_response=False)
        self.assertContains(self.client.get(url), 'Milestone completed')
        recorded = Audit.objects.get(case=case, action=milestone.RECORDED)
        self.assertEqual(recorded.actor_id, pm.pk)
        self.assertEqual(recorded.data['receipt'], receipt.pk)
        self.assertEqual(recorded.data['evidence'], evidence.pk)
        self.assertEqual(Milestone.objects.get(case=case).completed_by_id, pm.pk)
        self.assertEqual(Outbox.objects.get(case=case).status, 'pending')
        self.assertFalse(Handoff.objects.filter(case=case).exists())
        self.assertTrue(run_once(case_id=case.pk))
        self.assertEqual(Handoff.objects.filter(case=case).count(), 1)
        self.assertFalse(InvoicePreparation.objects.filter(handoff__case=case).exists())
        self.assertEqual(Publication.objects.filter(factory_work=work).count(), 1)
        self.assertEqual(seed.prepare(pm, operator, admission), sample | {'preserved': True})
        self.assertEqual(rev(origin), origin_revision)
        self.assertEqual(list(Audit.objects.filter(case=origin).order_by('pk').values_list('pk', flat=True)), origin_audits)
