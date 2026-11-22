import json
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, SimpleTestCase, TransactionTestCase
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.identity.models import Grant
from apps.pmo import delivery_closure
from apps.pmo.handover_replies import COMPONENT, record_reply
from apps.pmo.models import DeliveryRecord
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import register_reference, transition
from apps.workflows import factory, factory_handover as handover
from .helpers import activate, rev
from .test_factory_handover import setup, ready, receipt


def prepare():
    f = setup()
    for action in ['document.receive:internal', 'delivery.support_receive']:
        Grant.objects.get_or_create(case=f.case, user=f.publisher, action=action)
    references = []
    for audience, user in [('internal', f.publisher), ('client', f.actor)]:
        reference = register_reference(f.actor, f.case.pk, 'synthetic:handover-reply-' + audience,
            'schema:psl/document-recipient/v1', {'audience': audience, 'user_id': user.pk}, f.e['policy_decision'].pk)
        references.append(reference.ref)
    activate(f.actor, f.case, 'D11.recipient_grant_refs', references, f.e['policy_decision'])
    ready(f)
    factory.run_until_wait(f.work.pk)
    f.work.refresh_from_db()
    f.reply_proof = f.evidence('handover_receipt', 'SAMPLE Support reply and runbook acknowledgement proof.')
    return f


def configure(f):
    value = json.loads(Path('fixtures/handover-reply-capture.json').read_text())
    value.pop('classification')
    configuration = draft_operator_policy(f.actor, f.case.pk, COMPONENT, value,
        f.e['policy_decision'].pk, timezone.now())
    transition(f.actor, configuration.pk, 'validated')
    transition(f.actor, configuration.pk, 'active')
    return configuration


class HandoverReplyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.f = prepare()

    def reply(self, status='received', predecessor=0, **changes):
        f = self.f
        values = dict(status=status, evidence_id=f.reply_proof.pk, note='Synthetic Support reply proof reviewed.',
            party='SAMPLE Support lead', channel='email', responded_at=timezone.now(), role='PM', predecessor=predecessor)
        values.update(changes)
        f.work.refresh_from_db()
        return handover.record_support_reply(f.actor, f.work.pk, f.work.revision, rev(f.case), receipt(f).pk, **values)

    def test_configured_recorder_can_record_distinct_recipient_and_native_downstream_verifies(self):
        f = self.f
        configure(f)
        Grant.objects.filter(case=f.case, user=f.actor, action='delivery.support_receive').update(active=False)
        from apps.workflows.factory_views import presentation
        row = presentation(f.actor, f.work)
        self.assertTrue(row['needs_me'])
        self.assertIn('Support', row['next_action'])
        self.client.force_login(f.actor)
        api = f'/api/v1/work/{f.work.pk}/support-replies'
        options = self.client.get(api)
        self.assertEqual(options.status_code, 200, options.content)
        packet = options.json()
        self.assertTrue(packet['can_record'])
        command = {**{key: packet[key] for key in ('expected_revision', 'case_revision')},
            'receipt_id': receipt(f).pk, 'previous_id': None, 'status': 'received', 'evidence_id': f.reply_proof.pk,
            'note': 'Synthetic Support reply proof reviewed.', 'party': 'SAMPLE Support lead', 'channel': 'email',
            'responded_at': timezone.now().isoformat(), 'role': 'PM'}
        issued = self.client.post(api, command, content_type='application/json')
        self.assertEqual(issued.status_code, 201, issued.content)
        actual = DeliveryRecord.objects.get(pk=issued.json()['record_id'])
        self.assertEqual(actual.actor_id, f.actor.pk)
        self.assertEqual(actual.data['recipient_id'], f.publisher.pk)
        self.assertEqual(actual.data['attestation']['party'], 'SAMPLE Support lead')
        self.assertEqual(delivery_closure.received_handover(f.d), [actual.pk])
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        self.assertEqual(handover.verify(f.work)['handover_ids'], [actual.pk])
        reply = self.client.get(api).json()['receipts'][0]
        self.assertEqual((reply['status'], reply['previous_id'], reply['reply']['party']),
                         ('received', actual.pk, command['party']))
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertContains(page, 'SAMPLE Support lead replied by Email')
        self.assertContains(page, 'Recorded by')

    def test_missing_rules_keep_native_delivery_and_only_hold_external_recording(self):
        f = self.f
        with self.assertRaisesMessage(ValidationError, 'Review who may record Support replies'):
            self.reply()
        self.assertIsNotNone(receipt(f))
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d, kind='handover').exists())
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertContains(page, 'Who may record Support replies')
        self.assertNotContains(page, 'Record received without gaps</button>')

    def test_gaps_source_successor_and_exact_received_reply_preserve_original_history(self):
        f = self.f
        configure(f)
        self.client.force_login(f.actor)
        work_url = f'/api/v1/work/{f.work.pk}'
        reply_url = work_url + '/support-replies'

        def record_current_reply(status, note):
            response = self.client.get(reply_url)
            self.assertEqual(response.status_code, 200, response.content)
            options = response.json()
            self.assertTrue(options['can_record'])
            delivery = next(item for item in options['receipts'] if item['id'] == receipt(f).pk)
            body = {key: options[key] for key in ('expected_revision', 'case_revision')}
            body.update(receipt_id=delivery['id'], previous_id=delivery['previous_id'], status=status,
                        evidence_id=f.reply_proof.pk, note=note, party='SAMPLE Support lead',
                        channel='email', responded_at=timezone.now().isoformat(), role='PM')
            saved = self.client.post(reply_url, body, content_type='application/json')
            self.assertEqual(saved.status_code, 201, saved.content)
            return saved.json()['record_id']

        gaps = record_current_reply('gaps', 'Synthetic runbook needs an export restart instruction.')
        with self.assertRaises(ValidationError):
            handover.verify(f.work)
        previous_receipt = receipt(f)
        previous_document = handover.document(f.work)
        updated = f.evidence('support_document', 'SAMPLE runbook v2 includes the reviewed export restart instruction.')
        f.work.refresh_from_db()
        correction = self.client.post(work_url + '/corrections', {
            'expected_revision': f.work.revision, 'case_revision': rev(f.case), 'line': f.work.definition,
            'source': {'inputs': dict(f.inputs, support_document=updated.pk)},
            'reason': 'Address the exact evidenced Support gap.',
        }, content_type='application/json')
        self.assertEqual(correction.status_code, 200, correction.content)
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertNotEqual(receipt(f).pk, previous_receipt.pk)
        current_document = handover.document(f.work)
        self.assertEqual(current_document.document_id, previous_document.document_id)
        self.assertEqual(current_document.number, previous_document.number + 1)
        received = record_current_reply('received', 'Synthetic corrected handover received.')
        factory.run_until_wait(f.work.pk)
        f.work.refresh_from_db()
        self.assertEqual(f.work.status, 'verified', f.work.finding)
        self.assertEqual(handover.verify(f.work)['handover_ids'], [received])
        self.assertTrue(DeliveryRecord.objects.filter(pk=gaps, data__status='gaps').exists())
        projected = self.client.get(work_url).json()
        self.assertEqual((projected['state'], projected['output_url']), ('verified', work_url + '/support-receipt'))
        current_reply = self.client.get(reply_url).json()['receipts'][0]
        self.assertEqual((current_reply['previous_id'], current_reply['status']), (received, 'received'))

    def test_current_role_policy_source_permission_and_reply_predecessor_are_rechecked(self):
        f = self.f
        configuration = configure(f)
        first = self.reply('gaps')
        with self.assertRaisesMessage(ValidationError, 'newer Support reply'):
            self.reply()
        received = self.reply(predecessor=first.pk)
        self.assertEqual(delivery_closure.received_handover(f.d), [received.pk])
        Grant.objects.filter(case=f.case, user=f.actor, action='evidence.add').update(active=False)
        with self.assertRaises(PermissionDenied):
            handover.verify(f.work)
        self.client.force_login(f.actor)
        page = self.client.get(reverse('factory_detail', args=[f.work.pk]))
        self.assertNotContains(page, 'SAMPLE Support lead replied')
        self.assertNotContains(page, 'Synthetic Support reply proof reviewed.')
        self.assertContains(page, 'The recorded reply proof needs authorised review.')
        Grant.objects.filter(case=f.case, user=f.actor, action='evidence.add').update(active=True)
        transition(f.actor, configuration.pk, 'revoked')
        with self.assertRaises(ValidationError):
            handover.verify(f.work)
        self.assertTrue(DeliveryRecord.objects.filter(pk=received.pk).exists())
        configure(f)
        Grant.objects.filter(case=f.case, user=f.actor, action='delivery.record_support_reply').update(active=False)
        with self.assertRaises(PermissionDenied):
            self.reply(predecessor=received.pk)

    def test_future_reply_wrong_channel_and_before_delivery_do_not_record_receipt(self):
        f = self.f
        configure(f)
        for changes in [{'responded_at': timezone.now()+timedelta(days=1)}, {'channel': 'unreviewed'},
                        {'responded_at': receipt(f).created_at-timedelta(seconds=1)}, {'predecessor': True}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.reply(**changes)
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d, kind='handover').exists())

    def test_database_rejects_forged_recorder_facts_and_factory_verification_after_revocation(self):
        f = self.f
        configure(f)
        record = self.reply()
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_handover_recorded_reply(h,%s) FROM pmo_deliveryrecord h WHERE h.id=%s',
                [receipt(f).pk, record.pk])
            self.assertTrue(cursor.fetchone()[0])
        forged = dict(record.data)
        forged['attestation'] = {**forged['attestation'], 'role': 'Finance', 'predecessor': record.pk}
        with self.assertRaises(DatabaseError), transaction.atomic():
            DeliveryRecord.objects.create(dossier=f.d, kind='handover', evidence=f.reply_proof,
                actor=f.actor, parent=record, data=forged, snapshot=record.snapshot)
        factory.run_until_wait(f.work.pk)
        Grant.objects.filter(case=f.case, user=f.actor, action='delivery.record_support_reply').update(active=False)
        with connection.cursor() as cursor:
            cursor.execute('SELECT psl_handover_recorded_reply(h,%s) FROM pmo_deliveryrecord h WHERE h.id=%s',
                [receipt(f).pk, record.pk])
            self.assertFalse(cursor.fetchone()[0])
        with self.assertRaises(DatabaseError), transaction.atomic():
            from apps.workflows.models import FactoryWork
            FactoryWork.objects.filter(pk=f.work.pk).update(finding='SAMPLE forged verified claim after authority revocation')

    def test_rule_ui_saves_draft_and_invalid_reply_keeps_entered_details(self):
        f = self.f
        self.client.force_login(f.actor)
        url = reverse('factory_detail', args=[f.work.pk])
        response = self.client.post(url, {'action': 'support_reply_rules', 'case_revision': rev(f.case),
            'revision': f.work.revision, 'recorder_roles': ['PM'], 'channels': ['email'],
            'evidence_id': f.e['policy_decision'].pk})
        self.assertRedirects(response, url)
        from apps.policy.models import Configuration
        draft = Configuration.objects.filter(case=f.case, component=COMPONENT).latest('pk')
        self.assertEqual(draft.states.latest('pk').state, 'draft')
        configure(f)
        response = self.client.post(url, {'action': 'record_support_reply', 'case_revision': rev(f.case),
            'revision': f.work.revision, 'receipt': receipt(f).pk, 'predecessor': 0, 'status': 'received',
            'evidence': f.e['policy_decision'].pk, 'note': 'SAMPLE retained reply wording.',
            'party': 'SAMPLE Support responder', 'channel': 'email', 'role': 'PM',
            'responded_at': (timezone.now()+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')})
        self.assertContains(response, 'SAMPLE retained reply wording.')
        self.assertContains(response, 'SAMPLE Support responder')
        self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d, kind='handover').exists())


class HandoverReplyConcurrencyTests(TransactionTestCase):
    def test_competing_recorders_preserve_one_reply_successor(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections

        f = prepare()
        configure(f)
        case_revision = rev(f.case)
        receipt_id = receipt(f).pk
        barrier = Barrier(2)

        def record(_):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                try:
                    row = handover.record_support_reply(f.actor, f.work.pk, f.work.revision, case_revision,
                        receipt_id, status='received', evidence_id=f.reply_proof.pk,
                        note='SAMPLE concurrent actual reply.', party='SAMPLE Support lead', channel='email',
                        responded_at=timezone.now(), role='PM', predecessor=0)
                    return row.pk
                except ValidationError:
                    return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(record, range(2)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d, kind='handover').count(), 1)


class HandoverReplyValidatorTests(SimpleTestCase):
    def test_connected_reply_and_archive_templates_compile(self):
        from django.template.loader import get_template

        for name in ['factory/handover_detail.html', 'factory/handover_replies.html',
                     'factory/archive_detail.html', 'factory/archive_files.html']:
            self.assertIsNotNone(get_template(name))

    def test_roles_channels_and_closed_configuration_are_typed(self):
        from apps.documents.contracts import validate
        from apps.policy.handover_reply_validators import VALUE

        validate(VALUE, {'recorder_roles': ['PM'], 'channels': ['email']})
        for value in [{'recorder_roles': [], 'channels': ['email']},
                      {'recorder_roles': ['Anyone'], 'channels': ['email']},
                      {'recorder_roles': ['PM'], 'channels': ['email'], 'automatic_accept': True}]:
            with self.assertRaises(ValidationError):
                validate(VALUE, value)
