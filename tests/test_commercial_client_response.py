import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from adapters import commercial_client_response as contract
from apps.agents.upload_views import upload_file
from apps.core.evidence_access import public_evidence, public_timeline
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.pmo import commercial_client_response as domain
from apps.pmo.commercial import adopt_signed
from apps.pmo.models import BaselineAdoption, ClientResponse
from tests.helpers import rev
from tests.signature_helpers import contract as signature_contract, packet_for
from tests.test_commercial_changes import fixture, proposal, approvals, delivered


class PrivateStore:
    def __init__(self):
        self.files = {}

    def put_object(self, **values):
        self.files[values['Key']] = values['Body']

    def get_object(self, **values):
        return {'Body': BytesIO(self.files[values['Key']])}


class CommercialClientFixture:
    def setup_client_response(self):
        self.actor, self.case, self.e, self.template = fixture(username='sample-commercial-witness')
        self.proposal = proposal(self.actor, self.case, self.e)
        approvals(self.actor, self.case, self.proposal)
        self.receipt = delivered(self.actor, self.case, self.proposal, self.template)
        self.store = PrivateStore()
        self.storage = patch('adapters.case_uploads.bucket', return_value=(self.store, 'private-sample'))
        self.storage.start()
        self.addCleanup(self.storage.stop)
        self.source = b'SAMPLE client proof only. No operating policy or actual client signature is supplied.\n'
        self.proof = upload_file(self.actor, self.case, SimpleUploadedFile('SAMPLE-signed-statement.txt', self.source))
        self.url = reverse('commercial_client_response', args=[self.case.pk])

    def configure(self):
        return signature_contract(self.actor, self.case, self.e['policy_decision'])

    def record(self, **values):
        data = {'client_name': 'Synthetic client representative', 'responded_at': timezone.now(),
            'outcome': 'signed', 'genuine': True, 'proof_ids': [self.proof.pk],
            'note': 'SAMPLE actual human witness record for the exact delivered document.',
            'operation_key': uuid4(), 'expected': rev(self.case), 'predecessor': None}
        data.update(values)
        return domain.record(self.actor, self.case.pk, self.proposal.pk, self.receipt.pk, **data)

    def packet(self, response, configure=True):
        return packet_for(self.actor, self.case, {**self.e, 'signature': response.evidence}, self.proposal, configure=configure)


class CommercialClientResponseTests(CommercialClientFixture, TestCase):
    def setUp(self):
        self.setup_client_response()
        self.client.force_login(self.actor)

    def test_api_private_witness_attachment_and_original_authority(self):
        self.configure()
        url = f'/api/v1/projects/{self.case.pk}/commercial-response'
        new = self.client.post(f'{url}/files', {'case_revision': rev(self.case),
            'file': SimpleUploadedFile('SAMPLE-proof.txt', self.source + b'API')})
        self.assertEqual(new.status_code, 201, new.content)
        proof = new.json()['id']
        evidence = self.client.post(url, {'case_revision': rev(self.case), 'action': 'witness',
            'revision_id': self.proposal.pk, 'receipt_id': self.receipt.pk, 'client_name': 'Synthetic client representative',
            'responded_at': timezone.now().isoformat(), 'outcome': 'signed', 'genuine': True, 'proof_ids': [proof],
            'note': 'SAMPLE actual source received', 'operation_key': str(uuid4()), 'predecessor_id': None,
            'party_ref': 'synthetic-client'}, content_type='application/json')
        self.assertEqual(evidence.status_code, 201, evidence.content)
        metadata = evidence.json()['record_ids'][0]
        path = f'{url}/{metadata}/files/{proof}'
        download = self.client.get(path)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), self.source + b'API')
        desk = self.client.get(url).json()
        self.assertEqual(desk['witness']['id'], metadata)
        self.assertIsNone(desk['adoption'])
        Grant.objects.filter(case=self.case, user=self.actor, action='commercial.response').update(active=False)
        self.assertIsNone(self.client.get(url).json()['witness'])
        self.assertEqual(self.client.get(path).status_code, 403)

    def test_exact_private_witness_dual_signatures_adoption_and_native_finance_receipt(self):
        self.configure()
        metadata, response = self.record(party_ref='synthetic-client')
        value, actual = domain.read(self.actor, self.case, metadata)
        self.assertEqual(actual, response)
        self.assertEqual(value['document_sha256'], self.receipt.payload_sha256)
        with self.assertRaises(ValidationError):
            domain.current_for_signature(self.actor, self.case, response.evidence, None)
        self.assertFalse(public_evidence(Evidence.objects.filter(pk=metadata.pk)).exists())
        self.assertFalse(public_timeline(self.case).filter(action='commercial.client_witness').exists())
        self.assertNotIn(value['client_name'], response.evidence.body)
        self.assertNotIn(self.source.decode().strip(), response.evidence.body)
        with self.assertRaises(ValidationError):
            adopt_signed(self.actor, self.case.pk, self.proposal.pk, response.pk, rev(self.case))
        self.packet(response)
        adoption = adopt_signed(self.actor, self.case.pk, self.proposal.pk, response.pk, rev(self.case))
        self.assertEqual(adoption.response_id, response.pk)
        self.assertFalse(adoption.signedbaselineintake.payload['invoice_created'])
        self.assertEqual(adoption.signedbaselineintake.payload['signature_packet']['sources']['sow']['id'], self.proposal.sources['sow'])
        self.assertEqual(BaselineAdoption.objects.count(), 1)

    def test_missing_owner_contract_allows_recording_but_not_signature_qualification(self):
        metadata, response = self.record()
        self.assertIsNone(domain.read(self.actor, self.case, metadata)[0]['signature_policy'])
        self.packet(response, configure=False)
        with self.assertRaises(ValidationError):
            adopt_signed(self.actor, self.case.pk, self.proposal.pk, response.pk, rev(self.case))
        self.configure()
        self.packet(response)
        with self.assertRaisesMessage(ValidationError, 'owner-eligible signer'):
            adopt_signed(self.actor, self.case.pk, self.proposal.pk, response.pk, rev(self.case))
        corrected, current = self.record(predecessor=metadata.pk, party_ref='synthetic-client')
        self.packet(current)
        self.assertIsNotNone(adopt_signed(self.actor, self.case.pk, self.proposal.pk, current.pk, rev(self.case)))
        self.assertEqual(domain.read(self.actor, self.case, corrected)[0]['predecessor'], metadata.pk)
        self.assertTrue(ClientResponse.objects.filter(pk=response.pk).exists())

    def test_changes_and_decline_keep_history_and_stale_the_old_signed_claim(self):
        self.configure()
        first, response = self.record(party_ref='synthetic-client')
        packet = self.packet(response)
        for outcome in ['changes_requested', 'declined']:
            proof = upload_file(self.actor, self.case, SimpleUploadedFile('SAMPLE-' + outcome + '.txt',
                ('SAMPLE client ' + outcome + ' this document.').encode()))
            newer, current = self.record(outcome=outcome, proof_ids=[proof.pk], predecessor=first.pk)
            with self.assertRaises(ValidationError):
                domain.current_for_signature(self.actor, self.case, response.evidence, self.proposal.pk)
            with self.assertRaises(ValidationError):
                adopt_signed(self.actor, self.case.pk, self.proposal.pk, current.pk, rev(self.case))
            self.assertEqual(domain.read(self.actor, self.case, newer)[0]['outcome'], outcome)
            self.assertContains(self.client.get(self.url), 'Asked for changes' if outcome == 'changes_requested' else 'The client declined')
            first = newer
        self.assertEqual(ClientResponse.objects.count(), 3)
        self.assertEqual(packet.signatures['sow']['evidence_id'], response.evidence_id)

    def test_permission_before_private_body_or_storage_and_original_recorder_revocation(self):
        metadata, _ = self.record()
        other = get_user_model().objects.create_user(username='sample-commercial-reader')
        for action in ['case.read', 'commercial.read']:
            Grant.objects.create(user=other, case=self.case, action=action)
        deferred = domain.latest(self.case)
        self.assertIn('body', deferred.get_deferred_fields())
        with self.assertRaises(PermissionDenied):
            domain.read(other, self.case, deferred)
        self.assertIn('body', deferred.get_deferred_fields())
        Grant.objects.create(user=other, case=self.case, action='commercial.proof.read')
        self.assertEqual(domain.read(other, self.case, deferred)[0]['response'], ClientResponse.objects.get().pk)
        Grant.objects.filter(user=self.actor, case=self.case, action='commercial.response').update(active=False)
        self.client.force_login(other)
        with patch('adapters.case_uploads.read') as storage:
            result = self.client.get(reverse('commercial_client_proof', args=[self.case.pk, metadata.pk, self.proof.pk]))
            self.assertEqual(result.status_code, 403)
            storage.assert_not_called()
        self.assertNotContains(self.client.get(self.url), 'Synthetic client representative')

    def test_malformed_future_and_non_genuine_responses_do_not_create_native_records(self):
        for values in [{'genuine': False}, {'client_name': '  '}, {'proof_ids': []},
                       {'responded_at': timezone.now() + timedelta(days=1)},
                       {'responded_at': self.receipt.created_at - timedelta(seconds=1)},
                       {'operation_key': 'not-a-key'}, {'party_ref': 'invented-person'}]:
            with self.assertRaises(ValidationError):
                self.record(**values)
            self.assertFalse(ClientResponse.objects.exists())
        wrong = get_user_model().objects.create_user(username='sample-other-proof-owner')
        from apps.agents.models import CaseUpload
        foreign = CaseUpload.objects.create(case=self.case, actor=wrong, name='other.txt', key='other-proof',
            size=1, sha256=hashlib.sha256(b'x').hexdigest())
        with self.assertRaises(PermissionDenied):
            self.record(proof_ids=[foreign.pk])

    def test_human_form_download_and_existing_agent_worker_remain_source_bound(self):
        self.configure()
        form = {'action': 'record', 'revision': rev(self.case), 'operation_key': str(uuid4()),
            'receipt': self.receipt.pk, 'client_name': 'Synthetic client representative',
            'responded_at': timezone.localtime().isoformat(), 'outcome': 'signed', 'genuine': 'on',
            'proofs': [self.proof.pk], 'party_ref': 'synthetic-client', 'note': 'SAMPLE human checked actual proof.'}
        invalid = self.client.post(self.url, {**form, 'responded_at': (timezone.now() + timedelta(days=1)).isoformat()})
        self.assertContains(invalid, 'cannot be in the future')
        self.assertContains(invalid, 'Synthetic client representative')
        self.assertFalse(ClientResponse.objects.exists())
        self.assertEqual(self.client.post(self.url, form).status_code, 302)
        metadata = domain.latest(self.case)
        self.assertContains(self.client.get(self.url), 'Review the required document signatures')
        self.assertContains(self.client.post(self.url, {'action': 'adopt', 'revision': rev(self.case)}),
                            'Check both the statement of work and product requirements signatures')
        self.assertNotContains(self.client.get(self.url), contract.PREFIX)
        download = self.client.get(reverse('commercial_client_proof', args=[self.case.pk, metadata.pk, self.proof.pk]))
        self.assertEqual(b''.join(download.streaming_content), self.source)
        self.assertEqual(download['Cache-Control'], 'no-store')
        with patch.dict(os.environ, {'OPENROUTER_MODEL': 'synthetic/model', 'OPENROUTER_API_KEY': 'fake'}), \
             patch('adapters.openrouter.review', return_value={'summary': 'SAMPLE unsupported approval remains missing.',
                                                              'quotes': ['1'], 'gaps': ['Actual client authority is not authenticated.']}):
            jobs = domain.ask_agent(self.actor, self.case, metadata)
            from apps.agents.upload_jobs import run_once
            self.assertTrue(run_once())
            jobs[0].refresh_from_db()
            self.assertEqual(jobs[0].result['source_sha256'], self.proof.sha256)
            self.assertEqual(jobs[0].status, 'draft')
        self.assertFalse(BaselineAdoption.objects.exists())

    def test_signature_and_adoption_forms_use_exact_evidence_and_show_actual_finance_intake(self):
        from apps.core.services import add_evidence
        from apps.pmo import signatures
        self.configure()
        _, response = self.record(party_ref='synthetic-client')
        prd = add_evidence(self.actor, self.case.pk, 'prd', 'SAMPLE separate actual product requirements.', 'synthetic:prd')
        prd_signature = add_evidence(self.actor, self.case.pk, 'signature', 'SAMPLE separate product requirements signature.', 'synthetic:prd-proof')
        data = {'action': 'signatures', 'revision': rev(self.case), 'operation_key': str(uuid4()),
            'prd': prd.pk, 'commercial_revision': self.proposal.pk, 'sow_signature': prd_signature.pk,
            'sow_party': 'synthetic-client', 'sow_method': 'synthetic-reviewed-file',
            'sow_locator': 'SAMPLE statement signature', 'sow_verified': 'on',
            'prd_signature': prd_signature.pk, 'prd_party': 'synthetic-client', 'prd_method': 'synthetic-reviewed-file',
            'prd_locator': 'SAMPLE product document signature', 'prd_verified': 'on',
            'note': 'SAMPLE human checked both actual document references separately.'}
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        packet = signatures.latest(self.case)
        self.assertEqual(packet.signatures['sow']['evidence_id'], response.evidence_id, 'Tampered form input must not replace the exact recorded signature')
        self.assertEqual(self.client.post(self.url, {'action': 'adopt', 'revision': rev(self.case)}).status_code, 302)
        page = self.client.get(self.url)
        self.assertContains(page, 'Finance received its intake')
        self.assertContains(page, 'The signed documents pass the current signature checks.')
        self.assertNotContains(page, 'Use the verified signed documents as the project baseline')
        self.assertNotContains(page, 'id="client-response-client_name"')
        self.assertEqual(BaselineAdoption.objects.count(), 1)
        self.assertContains(page, 'Reconfirm the unchanged signed documents')
        from apps.policy.services import active_component
        from apps.pmo.signatures import assert_current_signed_baseline
        from tests.helpers import activate
        role = active_component('D05.role_principal_assignments', self.case)
        activate(self.actor, self.case, role.component, role.envelope['value'], self.e['policy_decision'])
        with self.assertRaises(ValidationError):
            assert_current_signed_baseline(self.case)
        self.assertContains(self.client.get(self.url), 'their current signature checks need fresh review')
        data.update(revision=rev(self.case), predecessor=packet.pk, operation_key=str(uuid4()))
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        fresh = signatures.latest(self.case)
        self.assertNotEqual(fresh.pk, packet.pk)
        self.assertEqual(self.client.post(self.url, {'action': 'reaffirm', 'packet': fresh.pk,
                                                   'revision': rev(self.case)}).status_code, 302)
        self.assertEqual(assert_current_signed_baseline(self.case).pk, fresh.pk)
        self.assertEqual(BaselineAdoption.objects.count(), 1)

    def test_specific_proof_reader_sees_no_witness_or_signature_actions_and_cannot_submit_them(self):
        self.configure()
        self.record(party_ref='synthetic-client')
        reader = get_user_model().objects.create_user(username='sample-commercial-proof-reader')
        for action in ['case.read', 'commercial.read', 'commercial.proof.read']:
            Grant.objects.create(user=reader, case=self.case, action=action)
        self.client.force_login(reader)
        page = self.client.get(self.url)
        self.assertContains(page, 'Synthetic client representative')
        self.assertNotContains(page, 'id="client-response-client_name"')
        self.assertNotContains(page, 'Record the document signature checks')
        for action in ['record', 'signatures', 'adopt']:
            self.assertEqual(self.client.post(self.url, {'action': action, 'revision': rev(self.case)}).status_code, 403)

    def test_real_private_adapter_integrity_and_native_provenance_cannot_be_replaced_by_generic_evidence(self):
        from apps.core.services import add_evidence
        self.store.files[self.proof.key] = b'Incorrect private bytes'
        with self.assertRaisesMessage(ValidationError, 'integrity'):
            self.record()
        self.assertFalse(ClientResponse.objects.exists())
        self.store.files[self.proof.key] = self.source
        metadata, response = self.record()
        forged = add_evidence(self.actor, self.case.pk, contract.KIND, metadata.body, metadata.source)
        with self.assertRaisesMessage(ValidationError, 'provenance'):
            domain.read(self.actor, self.case, forged)
        self.assertEqual(ClientResponse.objects.count(), 1)
        self.assertEqual(domain.current_for_signature(self.actor, self.case, response.evidence, self.proposal.pk).pk, metadata.pk)

    def test_signature_form_choices_are_bounded_metadata_and_omit_historical_bodies(self):
        self.configure()
        self.record(party_ref='synthetic-client')
        current = Evidence.objects.filter(case=self.case, kind='signature').order_by('-version').first().version
        body = 'SAMPLE historical signature body ' + 'x' * 10000
        Evidence.objects.bulk_create([Evidence(case=self.case, kind='signature', version=current + i,
            body=body, source='synthetic:historical-proof-' + str(i), sha256=hashlib.sha256(body.encode()).hexdigest(),
            created_by=self.actor) for i in range(1, 151)])
        page = self.client.get(self.url)
        choices = page.context['signing'].fields['prd_signature']
        self.assertLessEqual(len(list(choices.choices)), 51)
        self.assertTrue(all('body' in row.get_deferred_fields() for row in choices.queryset))
        self.assertNotContains(page, body[:100])

    def test_legacy_page_checks_private_response_and_signature_notes_before_loading(self):
        from django.test.utils import CaptureQueriesContext
        self.configure()
        metadata, response = self.record(party_ref='synthetic-client', note='SAMPLE private response note sentinel')
        self.packet(response)
        reader = get_user_model().objects.create_user(username='sample-legacy-commercial-reader')
        for action in ['case.read', 'commercial.read']:
            Grant.objects.create(user=reader, case=self.case, action=action)
        self.client.force_login(reader)
        with CaptureQueriesContext(connection) as queries:
            page = self.client.get(reverse('commercial', args=[self.case.pk]))
        self.assertNotContains(page, response.note)
        self.assertContains(page, 'Private response note')
        self.assertContains(page, 'Private signature-check note')
        for query in queries:
            sql = query['sql']
            if 'FROM "pmo_clientresponse"' in sql or 'FROM "pmo_commercialsignaturepacket"' in sql:
                self.assertNotIn('"note"', sql)
            if 'FROM "core_evidence"' in sql and "agent_private_commercial_response" in sql:
                self.assertNotIn('"body"', sql)
        Grant.objects.create(user=reader, case=self.case, action='commercial.proof.read')
        self.assertContains(self.client.get(reverse('commercial', args=[self.case.pk])), response.note)
        Grant.objects.filter(user=self.actor, case=self.case, action='commercial.response').update(active=False)
        self.assertNotContains(self.client.get(reverse('commercial', args=[self.case.pk])), response.note)

    def test_browser_fixture_preserves_existing_work_and_scopes_its_publication_worker(self):
        from apps.documents.models import PublicationJob
        from tests.railway_commercial_client_seed import prepare
        get_user_model().objects.create_user(username='psl-agent-trial')
        old = PublicationJob.objects.get(publication=self.receipt.publication)
        old.status = 'unknown'  # Isolated test lost-reply state; the new sample must not consume it.
        old.save(update_fields=['status'])
        before = old.attempts, old.fence
        with patch.dict(os.environ, {'PSL_COMMERCIAL_CLIENT_FIXTURE': '1'}):
            created = prepare()
            self.assertFalse(created['client_response_recorded'])
            self.assertFalse(created['baseline_adopted'])
            repeated = prepare()
            self.assertTrue(repeated['already_prepared'])
            self.assertEqual(repeated['responses'], 0)
        old.refresh_from_db()
        self.assertEqual(old.status, 'unknown')
        self.assertEqual((old.attempts, old.fence), before)

    def test_current_same_identity_reaffirmation_keeps_history_without_reusing_old_authority(self):
        from apps.policy.services import active_component
        from apps.pmo.signatures import assert_current_signed_baseline
        from tests.helpers import activate
        from tests.signature_helpers import reaffirm_for
        self.configure()
        metadata, response = self.record(party_ref='synthetic-client')
        original = self.packet(response)
        adoption = adopt_signed(self.actor, self.case.pk, self.proposal.pk, response.pk, rev(self.case))
        captured_role = original.authority_id
        role = active_component('D05.role_principal_assignments', self.case)
        activate(self.actor, self.case, role.component, role.envelope['value'], self.e['policy_decision'])
        with self.assertRaises(ValidationError):
            assert_current_signed_baseline(self.case)
        reaffirm_for(self.actor, self.case)
        self.assertNotEqual(assert_current_signed_baseline(self.case).authority_id, captured_role)
        prior_contract = original.policy_id
        self.configure()  # Explicit new owner version with the same actual identity.
        with self.assertRaises(ValidationError):
            assert_current_signed_baseline(self.case)
        reaffirm_for(self.actor, self.case)
        self.assertNotEqual(assert_current_signed_baseline(self.case).policy_id, prior_contract)
        self.assertTrue(adoption.signedbaselineintake.pk)
        self.assertEqual(Evidence.objects.get(pk=metadata.pk).body, metadata.body)
        self.assertEqual(ClientResponse.objects.count(), 1)


class CommercialClientResponseConcurrencyTests(CommercialClientFixture, TransactionTestCase):
    def setUp(self):
        self.setup_client_response()

    def test_two_connections_record_one_response_and_keep_the_other_for_review(self):
        expected, instant = rev(self.case), timezone.now()
        def submit():
            close_old_connections()
            try:
                return self.record(expected=expected, responded_at=instant)[0].pk
            except ValidationError:
                return 'stale'
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        self.assertEqual(results.count('stale'), 1)
        self.assertEqual(ClientResponse.objects.count(), 1)
