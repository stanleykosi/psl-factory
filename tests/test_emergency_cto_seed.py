import json
from contextlib import redirect_stdout
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Audit, Case
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.models import Grant
from apps.pmo import emergencies as native
from apps.pmo.models import EmergencyAuthorization, EmergencyDecision, EmergencyOutcome, EmergencyProfile
from apps.workflows.models import FactoryWork
from tests import railway_emergency_cto_seed as seed
from tests.helpers import rev


class EmergencyCTOWalkthroughSeedTests(TestCase):
    def test_exact_third_approver_refuses_current_request_without_authorizing_or_attesting(self):
        self.assertEqual(connection.vendor, 'postgresql')
        trial = get_user_model().objects.create_user('psl-agent-trial')
        environment = {'RAILWAY_PROJECT_ID': seed.PREVIEW_PROJECT, 'RAILWAY_ENVIRONMENT_NAME': 'design-acceptance',
                       'PGDATABASE': 'isolated-preview', seed.GUARD: '1'}
        with patch.dict('os.environ', environment | {seed.GUARD: '0'}):
            with self.assertRaisesMessage(RuntimeError, 'emergency technology fixture guard'):
                seed.run()
        self.assertFalse(Case.objects.filter(pk=seed.CASE_ID).exists())
        with patch.dict('os.environ', environment), redirect_stdout(StringIO()) as output:
            seed.run()
        prefix, raw = output.getvalue().strip().split('=', 1)
        self.assertEqual(prefix, seed.GUARD)
        sample = json.loads(raw)
        case = Case.objects.get(pk=sample['case'])
        work = FactoryWork.objects.get(pk=sample['work'])
        profile = EmergencyProfile.objects.get(pk=sample['profile'])
        self.assertEqual((profile.version.incident_id, profile.candidate_id), (sample['incident'], sample['candidate']))
        self.assertEqual(list(profile.decisions.order_by('pk').values_list('actor_id', flat=True)), sample['approvers'])
        self.assertEqual(len({trial.pk, sample['owner'], *sample['approvers']}), 4)
        self.assertEqual(native.glpi_snapshot(case, profile.candidate), sample['glpi'])
        with self.assertRaisesMessage(ValidationError, 'Current prescribed emergency approval required: CTO'):
            native.preauthorization_inputs(case, profile)

        self.client.force_login(trial)
        page = self.client.get(sample['decision'])
        self.assertContains(page, 'Chief technology officer decision')
        self.assertContains(page, 'Incident Lead')
        self.assertContains(page, 'Engineering Lead')
        self.assertContains(page, 'Reject emergency change')
        self.assertNotContains(page, 'Return emergency change')
        self.assertNotContains(page, 'name="role" value="Incident Lead"')
        self.assertNotContains(page, 'Check and record preauthorization')
        self.assertNotContains(self.client.get(sample['response']), 'Attest actual implementation evidence')
        fields = {'action': 'preauthorization_decision', 'role': 'CTO', 'authority_role': 'CTO', 'verdict': 'reject',
                  'revision': work.revision, 'case_revision': rev(case), 'profile': profile.pk,
                  'evidence': sample['evidence'], 'note': 'The simulated rollback rehearsal was not evidenced.'}
        for change in ({'role': 'Engineering Lead', 'authority_role': 'Engineering Lead'}, {'verdict': 'return'}):
            rejected = self.client.post(sample['decision'], {**fields, **change})
            self.assertContains(rejected, 'Choose a currently available emergency decision for this exact request.')
        self.assertEqual(profile.decisions.count(), 2)
        grant = Grant.objects.get(user=trial, case=case, action='emergency.decide')
        Grant.objects.filter(pk=grant.pk).update(active=False)
        self.assertNotContains(self.client.get(sample['decision']), 'Reject emergency change')
        self.assertEqual(self.client.post(sample['decision'], fields).status_code, 403)
        Grant.objects.filter(pk=grant.pk).update(active=True)
        response = self.client.post(sample['decision'], fields)
        self.assertRedirects(response, sample['decision'], fetch_redirect_response=False)
        refusal = EmergencyDecision.objects.get(profile=profile, role='CTO')
        self.assertEqual((refusal.actor_id, refusal.evidence_id, refusal.verdict), (trial.pk, sample['evidence'], 'reject'))
        page = self.client.get(sample['decision'])
        self.assertContains(page, 'Emergency preauthorization refused')
        self.assertContains(page, f'Decision {refusal.pk} remains in the history')
        self.assertNotContains(page, 'Reject emergency change')
        fields['case_revision'] = rev(case)
        self.assertContains(self.client.post(sample['decision'], fields), 'Choose a currently available emergency decision')
        self.assertEqual(self.client.post(sample['decision'], {**fields, 'action': 'authorize'}).status_code, 403)
        actual = (timezone.localtime() - timedelta(minutes=1)).replace(tzinfo=None, microsecond=0)
        outcome = {**fields, 'action': 'capture_outcome', 'implemented_at': actual.isoformat(),
                   'evidence': sample['implementation_evidence']}
        self.assertEqual(self.client.post(sample['response'], outcome).status_code, 403)
        self.assertFalse(EmergencyAuthorization.objects.filter(profile=profile).exists())
        self.assertFalse(EmergencyOutcome.objects.filter(profile=profile).exists())
        self.assertFalse(Publication.objects.filter(factory_work=work).exists())
        self.assertFalse(PublicationReceipt.objects.filter(publication__factory_work=work).exists())
        self.assertFalse(Audit.objects.filter(case=case, action='emergency.preauthorized').exists())
        self.assertEqual(seed.prepare(trial), sample | {'preserved': True})
