"""Native PostgreSQL application tests; execution requires coordinator clearance."""
import copy
import json
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, Client
from django.core.exceptions import ValidationError, PermissionDenied
from apps.core.evidence_access import public_evidence, public_timeline
from apps.finance import quickbooks_read as service
from apps.finance.models import LedgerCheck, LedgerDecision
from apps.identity.models import Grant
from apps.policy.ledger_validators import RULES
from adapters import quickbooks_online as adapter
from .ledger_helpers import fixture, capture, policy, evidence


class QBOFixtureMixin:
    def setUp(self):
        self.f = fixture()
        self.f['v']['source'].update(realm='123', entity='Invoice', target_reference='42')
        self.f['v']['rules'].update(realm='123', entity='Invoice')
        policy(self.f, RULES, self.f['v']['rules'])
        self.lineage = capture(self.f)
        self.binding = dict(enabled=True, environment='sandbox', realm='123', entity='Invoice',
                            minor_version='75', credential_ref='secret:qbo', credential_revision='v1',
                            principal_ref='principal:synthetic')
        self.override = self.settings(QUICKBOOKS_READS={'optional':self.binding},
                                      READINESS_SECRET_REFS={'secret:qbo':{'env':'SYNTHETIC_QBO_TEST','revision':'v1'}})
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.env = patch.dict('os.environ', {'SYNTHETIC_QBO_TEST':'synthetic-test-token'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def reserve(self):
        return service.reserve(self.f['actor'], self.f['case'].pk, self.lineage.pk, 'optional')

    def execute(self, intent, during=None, status=200):
        def send(url, token):
            if during: during()
            return status, 'application/json', json.dumps({'Invoice':{'Id':'42','SyncToken':'0','TxnDate':'2026-11-07'}}).encode()
        def read(*args): return adapter.read(*args, send=send)
        with patch.object(service, 'read', side_effect=read):
            return service.execute(self.f['actor'], self.f['case'].pk, intent.pk)


class NativeQBOReadTests(QBOFixtureMixin, TransactionTestCase):
    def test_read_link_is_not_finance_verification(self):
        intent = self.reserve()
        result = self.execute(intent)
        body = json.loads(result.body)
        self.assertEqual(body['link_status'], 'current_at_capture')
        self.assertEqual(body['observation']['status'], 'observed_object')
        self.assertFalse(body['business_verification'])
        self.assertEqual(LedgerCheck.objects.count(), 0)
        self.assertEqual(LedgerDecision.objects.count(), 0)
        with self.assertRaises(ValidationError): self.execute(intent)

    def test_forged_evidence_cannot_be_executed(self):
        intent = self.reserve()
        from apps.core.services import add_evidence
        forged = add_evidence(self.f['actor'], self.f['case'].pk, service.INTENT, intent.body, 'native:qbo-read/v1')
        with self.assertRaises(ValidationError): self.execute(forged)

    def test_permission_revoked_before_read(self):
        intent = self.reserve()
        Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='ledger.verify').update(active=False)
        with self.assertRaises(PermissionDenied): self.execute(intent)

    def test_revocation_inflight_preserves_fact_without_link(self):
        intent = self.reserve()
        result = self.execute(intent, during=lambda: Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='ledger.read').update(active=False))
        self.assertEqual(json.loads(result.body)['link_status'], 'stale_or_access_changed')
        with self.assertRaises(PermissionDenied): service.visible(self.f['actor'], self.f['case'])

    def test_policy_changed_inflight_retains_separate_fact(self):
        intent = self.reserve()
        result = self.execute(intent, during=lambda: policy(self.f,RULES,self.f['v']['rules']))
        self.assertEqual(json.loads(result.body)['link_status'], 'stale_or_access_changed')

    def test_private_evidence_and_audit_not_in_generic_workspace(self):
        intent = self.reserve()
        result = self.execute(intent)
        self.assertFalse(public_evidence(self.f['case'].evidence.all()).filter(pk__in=[intent.pk,result.pk]).exists())
        self.assertFalse(public_timeline(self.f['case']).filter(action__startswith=service.PREFIX).exists())

    def test_throttle_prevents_immediate_repeat_read(self):
        self.execute(self.reserve(), status=429)
        later = self.reserve()
        with self.assertRaises(ValidationError): self.execute(later)

    def test_rotation_or_conflict_holds_reserved_read(self):
        intent = self.reserve()
        with patch.dict('os.environ', {'SYNTHETIC_QBO_TEST':'rotated-synthetic-token'}):
            with self.assertRaises(ValidationError): self.execute(intent)
        source = copy.deepcopy(self.lineage.payload)
        source['source_reference'] = 'synthetic-other-source'
        capture(self.f, source)
        with self.assertRaises(ValidationError): self.execute(intent)


class NativeQBOHTTPTests(QBOFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.f['actor'])
        self.url = f"/cases/{self.f['case'].pk}/finance/ledger/"

    def post(self, action, **fields):
        from .helpers import rev
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        token = self.client.cookies['csrftoken'].value
        return self.client.post(self.url, dict(action=action, revision=rev(self.f['case']),
                                               csrfmiddlewaretoken=token, **fields))

    def test_csrf_workbench_reserve_execute_and_private_status(self):
        response = self.post('qbo_reserve', lineage=self.lineage.pk, binding='optional')
        self.assertEqual(response.status_code, 302)
        intent = self.f['case'].evidence.get(kind=service.INTENT)
        def send(url, token):
            return 200, 'application/json', b'{"Invoice":{"Id":"42","SyncToken":"0","TxnDate":"2026-11-07"}}'
        with patch.object(service, 'read', side_effect=lambda *args: adapter.read(*args, send=send)) as remote:
            response = self.post('qbo_execute', intent=intent.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(remote.call_count, 1)
        self.assertEqual(self.f['case'].evidence.filter(kind=service.OBSERVATION).count(), 1)
        response = self.client.get(self.url)
        self.assertContains(response, 'observed_object')
        self.assertContains(response, 'not Finance verification')
        self.assertNotContains(response, 'synthetic-test-token')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_missing_csrf_stale_revision_and_extra_fields_cannot_reserve(self):
        from .helpers import rev
        response = self.client.post(self.url, {'action':'qbo_reserve','revision':rev(self.f['case']),
                                               'lineage':self.lineage.pk,'binding':'optional'})
        self.assertEqual(response.status_code, 403)
        self.client.get(self.url)
        token = self.client.cookies['csrftoken'].value
        for fields in ({'revision':0}, {'revision':rev(self.f['case']), 'extra':'unauthorized'}):
            response = self.client.post(self.url, dict(action='qbo_reserve', lineage=self.lineage.pk,
                binding='optional', csrfmiddlewaretoken=token, **fields))
            self.assertEqual(response.status_code, 302)
        self.assertFalse(self.f['case'].evidence.filter(kind=service.INTENT).exists())

    def test_get_never_executes_and_revoked_post_is_held(self):
        intent = self.reserve()
        with patch.object(service, 'read', side_effect=AssertionError('Unexpected transport')):
            response = self.client.get(self.url, {'action':'qbo_execute','intent':intent.pk})
            self.assertEqual(response.status_code, 200)
            Grant.objects.filter(case=self.f['case'], user=self.f['actor'], action='ledger.verify').update(active=False)
            response = self.post('qbo_execute', intent=intent.pk)
            self.assertEqual(response.status_code, 302)
        self.assertFalse(self.f['case'].evidence.filter(kind=service.OBSERVATION).exists())


class NativeQBOContentionTests(QBOFixtureMixin, TransactionTestCase):
    def test_outer_transaction_rejected_before_claim_or_transport(self):
        from django.db import transaction
        from apps.core.models import Audit
        intent = self.reserve()
        with patch.object(service, 'read', side_effect=AssertionError('Unexpected transport')):
            with transaction.atomic():
                with self.assertRaises(ValidationError):
                    service.execute(self.f['actor'], self.f['case'].pk, intent.pk)
        self.assertFalse(Audit.objects.filter(case=self.f['case'],action=service.PREFIX+'started',data__intent=intent.pk).exists())
        self.assertFalse(self.f['case'].evidence.filter(kind=service.OBSERVATION).exists())

    def test_simultaneous_execute_claim_has_one_remote_read(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier, Lock
        from django.db import close_old_connections
        from apps.core.models import Audit
        intent = self.reserve()
        barrier, lock, calls = Barrier(2), Lock(), []
        def send(url, token):
            with lock: calls.append(url)
            return 200, 'application/json', b'{"Invoice":{"Id":"42","SyncToken":"0","TxnDate":"2026-11-07"}}'
        def action(_):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                try:
                    service.execute(self.f['actor'], self.f['case'].pk, intent.pk)
                    return 'recorded'
                except ValidationError:
                    return 'held'
            finally:
                close_old_connections()
        with patch.object(service, 'read', side_effect=lambda *args: adapter.read(*args, send=send)):
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(action, [0,1]))
        self.assertCountEqual(outcomes, ['recorded','held'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(Audit.objects.filter(case=self.f['case'], action=service.PREFIX+'started',data__intent=intent.pk).count(), 1)
        self.assertEqual(self.f['case'].evidence.filter(kind=service.OBSERVATION).count(), 1)

    def test_other_connection_revocation_during_read_retains_unlinked_observation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import close_old_connections
        intent = self.reserve()
        reading, changed = Event(), Event()
        def send(url, token):
            reading.set()
            if not changed.wait(15): raise AssertionError('Revocation coordination timeout')
            return 200, 'application/json', b'{"Invoice":{"Id":"42","SyncToken":"0","TxnDate":"2026-11-07"}}'
        def action():
            close_old_connections()
            try:
                return service.execute(self.f['actor'], self.f['case'].pk, intent.pk).pk
            finally:
                close_old_connections()
        with patch.object(service, 'read', side_effect=lambda *args: adapter.read(*args, send=send)):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(action)
                try:
                    self.assertTrue(reading.wait(15))
                    Grant.objects.filter(case=self.f['case'],user=self.f['actor'],action='ledger.read').update(active=False)
                finally:
                    changed.set()
                result_id = future.result(timeout=30)
        result = self.f['case'].evidence.get(pk=result_id)
        self.assertEqual(json.loads(result.body)['link_status'], 'stale_or_access_changed')
        with self.assertRaises(PermissionDenied): service.visible(self.f['actor'], self.f['case'])
        self.assertEqual(LedgerCheck.objects.count(), 0)
