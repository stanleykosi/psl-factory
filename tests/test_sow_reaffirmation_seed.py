"""The hosted sample leaves same-identity signature rechecking to the browser."""

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.agents.models import AgentJob, CaseUpload
from apps.core.models import Case
from apps.documents.models import PublicationReceipt
from apps.finance.models import SignedBaselineIntake
from apps.pmo import signatures
from apps.pmo.models import BaselineAdoption, ClientResponse, CommercialSignatureReaffirmation
from tests import railway_sow_reaffirmation_seed as seed
from tests.helpers import rev
from tests.test_commercial_client_response import PrivateStore


class SowReaffirmationFixtureTests(TestCase):
    def test_same_exact_sources_need_a_new_human_packet_and_separate_reaffirmation(self):
        self.assertEqual(connection.vendor, 'postgresql')
        recorder = get_user_model().objects.create_user(seed.RECORDER)
        with patch('adapters.case_uploads.bucket', return_value=(PrivateStore(), 'private-sample')):
            sample = seed.prepare(recorder)
            case = Case.objects.get(pk=sample['case'])
            original = signatures.latest(case)
            self.assertEqual(original.pk, sample['original_packet'])
            self.assertIsNone(sample['confirmed_packet'])
            self.assertNotEqual(sample['original_role'], sample['renewed_role'])
            self.assertNotEqual(sample['original_contract'], sample['renewed_contract'])
            self.assertFalse(CommercialSignatureReaffirmation.objects.exists())

            self.client.force_login(recorder)
            page = self.client.get(sample['path'])
            self.assertContains(page, 'their current signature checks need fresh review')
            self.assertContains(page, 'Finance received its intake')
            premature = self.client.post(sample['path'], {'action': 'reaffirm', 'packet': original.pk,
                                                        'revision': rev(case)})
            self.assertContains(premature, 'Signature recorder authority changed')

            form = {'action': 'signatures', 'operation_key': uuid4(), 'predecessor': original.pk,
                    'revision': rev(case), 'commercial_revision': sample['proposal'], 'prd': sample['prd'],
                    'note': 'Rechecked both unchanged synthetic copies against the original proof and current authority.'}
            for kind, check in sample['signature_checks'].items():
                form.update({f'{kind}_signature': check['evidence_id'], f'{kind}_party': check['party_ref'],
                             f'{kind}_method': check['method'], f'{kind}_locator': check['locator'], f'{kind}_verified': 'on'})
            self.assertEqual(self.client.post(sample['path'], form).status_code, 302)
            fresh = signatures.latest(case)
            self.assertEqual((fresh.predecessor_id, fresh.sources, fresh.signatures),
                             (original.pk, original.sources, original.signatures))
            self.assertEqual((fresh.authority_id, fresh.policy_id), (sample['renewed_role'], sample['renewed_contract']))
            self.assertFalse(CommercialSignatureReaffirmation.objects.exists())
            self.assertContains(self.client.get(sample['path']), 'their current signature checks need fresh review')

            accepted = self.client.post(sample['path'], {'action': 'reaffirm', 'packet': fresh.pk, 'revision': rev(case)})
            self.assertEqual(accepted.status_code, 302)
            self.assertEqual(signatures.assert_current_signed_baseline(case).pk, fresh.pk)
            self.assertContains(self.client.get(sample['path']), 'The signed documents pass the current signature checks.')
            retained = seed.prepare(recorder)

        self.assertEqual(retained['confirmed_packet'], fresh.pk)
        for model in (ClientResponse, PublicationReceipt, BaselineAdoption, SignedBaselineIntake,
                      CaseUpload, CommercialSignatureReaffirmation):
            self.assertEqual(model.objects.count(), 1, model.__name__)
        finance = SignedBaselineIntake.objects.get(pk=sample['finance_intake'])
        self.assertEqual(finance.payload['signature_packet']['id'], original.pk)
        self.assertFalse(finance.payload['invoice_created'])
        self.assertFalse(AgentJob.objects.exists())
