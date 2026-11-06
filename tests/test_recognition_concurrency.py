from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import recognition as domain
from apps.finance.recognition_models import RecognitionRecord
from .recognition_helpers import fixture,received

class RecognitionConcurrencyTests(TransactionTestCase):
    def setUp(self):self.f=fixture()
    def test_two_connections_record_one_owner_decision_for_same_operation(self):
        f=self.f
        def work(_):
            close_old_connections()
            try:return domain.record(f['actor'],f['case'].pk,f['packet'].pk,'attest','same-owner-intent',f['evidence']['completion'].pk,'Exact owner decision',None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(work,[1,2]))
        self.assertEqual(rows[0],rows[1]);self.assertEqual(RecognitionRecord.objects.count(),1)

    def test_grant_revocation_before_acceptance_serializes_and_holds_decision(self):
        f=self.f;received(f);locked=Event();commit=Event()
        def revoke():
            close_old_connections()
            try:
                with transaction.atomic():
                    Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
                    if not commit.wait(10):raise AssertionError('Test coordination timed out')
                    Grant.objects.filter(case=f['case'],user=f['finance'],action='recognition.review').update(active=False)
            finally:close_old_connections()
        def accept():
            close_old_connections()
            try:
                try:domain.record(f['finance'],f['case'].pk,f['packet'].pk,'review','review-race',f['evidence']['completion'].pk,'Explicit Finance review',None,'reviewed',f['decision'].pk)
                except PermissionDenied:return 'held'
                return 'accepted'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(accept);commit.set();first.result(timeout=30);self.assertEqual(second.result(timeout=30),'held')
        self.assertEqual(RecognitionRecord.objects.filter(kind='review').count(),0)
