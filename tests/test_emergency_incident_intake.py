from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Case
from apps.core.services import add_evidence
from apps.documents.models import Publication
from apps.identity.models import Grant
from apps.pmo import emergencies as native
from apps.pmo.models import ChangeRequest, EmergencyAuthorization, EmergencyOutcome, EmergencyProfile
from apps.workflows import factory_emergency
from apps.workflows.factory_emergency_intake import PROFILE_INPUTS, REQUESTED
from apps.workflows.models import FactoryWork
from tests import railway_emergency_incident_seed as seed
from tests.helpers import rev, setup_case


class EmergencyIncidentIntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user('psl-agent-trial')
        cls.sample = seed.prepare(cls.viewer)
        cls.case = Case.objects.get(pk=seed.CASE_ID)

    def setUp(self):
        self.client.force_login(self.viewer)

    def request_fields(self):
        response = self.client.get(self.sample['start'])
        self.assertContains(response, 'Emergency change for an incident')
        self.assertContains(response, seed.INCIDENT)
        self.assertContains(response, 'Ask for preauthorisation')
        self.assertNotContains(response, 'Report audience')
        return {'definition': factory_emergency.DEFINITION, 'mode': 'incident', 'case': str(self.case.pk),
                'key': response.context['form']['key'].value(), 'incident': self.sample['incident'],
                'module': self.sample['module'], 'plan': self.sample['plan'], 'revision': rev(self.case)}

    def requested(self):
        response = self.client.post(self.sample['start'], self.request_fields())
        self.assertEqual(response.status_code, 302)
        version = ChangeRequest.objects.get(case=self.case).current
        return version, response.url

    def test_exact_incident_creates_one_request_then_unknown_classification_and_work(self):
        self.assertEqual(connection.vendor, 'postgresql')
        with patch.dict('os.environ', {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT,
                                       'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                                       'PGDATABASE': 'isolated-preview', seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'Emergency incident fixture guard'):
                seed.run()
        fields = self.request_fields()
        outsider, other = setup_case(username='sample-other-incident-owner')
        foreign = add_evidence(outsider, other.pk, 'incident', 'Confidential foreign incident detail', 'synthetic:other')
        invalid = self.client.post(self.sample['start'], {**fields, 'incident': foreign.pk})
        self.assertContains(invalid, 'Select a valid choice')
        self.assertNotContains(invalid, foreign.body)
        self.assertFalse(ChangeRequest.objects.filter(case=self.case).exists())
        response = self.client.post(self.sample['start'], fields)
        self.assertEqual(response.status_code, 302)
        following = response.url
        version = ChangeRequest.objects.get(case=self.case).current
        self.assertEqual((version.actor_id, version.category, version.incident_id),
                         (self.viewer.pk, 'Emergency', self.sample['incident']))
        self.assertEqual((version.description, version.evidence.body), (self.sample['plan'], self.sample['plan']))
        self.assertEqual(self.case.audit.filter(action=REQUESTED).count(), 1)
        self.assertFalse(FactoryWork.objects.filter(case=self.case).exists())
        self.assertFalse(EmergencyProfile.objects.filter(version=version).exists())
        self.assertRedirects(self.client.post(self.sample['start'], fields), following)
        duplicate = self.client.post(self.sample['start'], {**fields, 'plan': fields['plan'] + ' Unreviewed edit.'})
        self.assertContains(duplicate, 'This request already recorded another plan.')
        self.assertEqual(ChangeRequest.objects.get(case=self.case).versions.count(), 1)

        page = self.client.get(following)
        self.assertContains(page, 'Preauthorisation requested. The incident plan is recorded.')
        self.assertContains(page, self.sample['plan'])
        self.assertContains(page, 'Record classification and start work')
        classification = {'definition': factory_emergency.DEFINITION, 'mode': 'classify', 'case': str(self.case.pk),
                          'version': version.pk, 'revision': rev(self.case), 'candidate': self.sample['candidate'],
                          'evidence': self.sample['classification'], 'p1': 'unknown', 'critical_production': 'unknown',
                          'note': 'The exact source records neither classification as confirmed.'}
        no_evidence = self.client.post(following, {**classification, 'evidence': ''})
        self.assertContains(no_evidence, 'Provide this information to record the classification.')
        self.assertFalse(EmergencyProfile.objects.filter(version=version).exists())
        Grant.objects.filter(case=self.case, user=self.viewer, action='emergency.manage').update(active=False)
        self.assertEqual(self.client.post(following, classification).status_code, 403)
        Grant.objects.filter(case=self.case, user=self.viewer, action='emergency.manage').update(active=True)
        executed = self.client.post(following, classification)
        self.assertEqual(executed.status_code, 302)
        work = FactoryWork.objects.get(case=self.case, definition=factory_emergency.DEFINITION)
        self.assertRedirects(executed, reverse('factory_detail', args=[work.pk]), fetch_redirect_response=False)
        profile, data = factory_emergency.source(work, self.viewer)
        self.assertEqual((profile.version_id, profile.candidate_id, profile.evidence_id),
                         (version.pk, self.sample['candidate'], self.sample['classification']))
        self.assertEqual((profile.critical_production, profile.p1), (None, None))
        self.assertEqual(data['inputs'], PROFILE_INPUTS)
        self.assertIn('explicit incident P1 basis', factory_emergency.report(work, self.viewer)['finding'])
        self.assertRedirects(self.client.post(following, classification), executed.url, fetch_redirect_response=False)
        self.assertEqual(FactoryWork.objects.filter(case=self.case).count(), 1)
        self.assertEqual(EmergencyProfile.objects.filter(version=version).count(), 1)
        self.assertFalse(profile.decisions.exists())
        self.assertFalse(EmergencyAuthorization.objects.filter(profile=profile).exists())
        self.assertFalse(EmergencyOutcome.objects.filter(profile=profile).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())

    def test_exact_existing_native_profile_resumes_and_rejects_an_unrelated_selection(self):
        version, following = self.requested()
        profile = native.capture_profile(self.viewer, self.case.pk, version.pk, self.sample['candidate'],
            None, None, self.sample['classification'], 'Classification proof previously recorded.', rev(self.case))
        page = self.client.get(following)
        self.assertContains(page, 'Continue with recorded classification')
        self.assertContains(page, 'Unknown')
        self.assertNotContains(page, 'Classification evidence')
        fields = {'definition': factory_emergency.DEFINITION, 'mode': 'classify', 'case': str(self.case.pk),
                  'version': version.pk, 'profile': profile.pk + 1, 'revision': rev(self.case)}
        invalid = self.client.post(following, fields)
        self.assertContains(invalid, 'The classification changed.')
        self.assertFalse(FactoryWork.objects.filter(case=self.case).exists())
        accepted = self.client.post(following, {**fields, 'profile': profile.pk})
        self.assertEqual(accepted.status_code, 302)
        current = FactoryWork.objects.get(case=self.case)
        self.assertEqual(factory_emergency.source(current, self.viewer)[0].pk, profile.pk)
        self.assertEqual(EmergencyProfile.objects.filter(version=version).count(), 1)
        legacy = self.client.get(reverse('factory_create'), {'definition': factory_emergency.DEFINITION,
                                                              'mode': 'existing', 'case': self.case.pk})
        self.assertContains(legacy, 'Start Emergency evidence work')

    def test_report_preparation_waits_for_an_explicit_audience_after_native_retrospective(self):
        from tests.test_factory_emergency import FactoryEmergencyTests

        entry = FactoryEmergencyTests()
        entry.setUp()
        entry.inputs['audience'] = None
        _, _, record = entry.ready_work()
        entry.advance()
        self.assertEqual(factory_emergency.report(entry.work)['retrospective_record'], record.pk)
        self.assertIn('Choose the retrospective report template and audience', entry.work.finding)
        self.assertIsNone(factory_emergency.document(entry.work))
        self.assertFalse(Publication.objects.filter(factory_work=entry.work).exists())
        entry.inputs['audience'] = 'client'
        factory_emergency.correct(entry.actor, entry.work.pk, entry.work.revision, rev(entry.case),
                                  entry.profile.pk, entry.inputs, 'Select the sample report’s audience explicitly.')
        entry.advance()
        self.assertEqual(factory_emergency.document(entry.work).audience, 'client')
        self.assertFalse(Publication.objects.filter(factory_work=entry.work).exists())
