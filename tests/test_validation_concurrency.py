from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase
from django.db import transaction,close_old_connections
from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.documents import validation as domain
from apps.documents.validation_models import ValidationReview
from .validation_helpers import fixture,ready,review

class ValidationConcurrencyTests(TransactionTestCase):
    def setUp(self):self.f=fixture()
    def test_two_connections_record_one_owner_decision_for_same_operation(self):
        f=self.f
        def work(_):
            close_old_connections()
            try:return domain.review(f['owner'],f['case'].pk,f['package'].pk,'meaning','approve','same-owner-intent',f['decision_evidence'].pk,'Exact owner decision',None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(work,[1,2]))
        self.assertEqual(rows[0],rows[1]);self.assertEqual(ValidationReview.objects.count(),1)

    def test_grant_revocation_before_acceptance_serializes_and_holds_decision(self):
        f=self.f;ready(f);locked=Event();commit=Event()
        def revoke():
            close_old_connections()
            try:
                with transaction.atomic():
                    Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
                    if not commit.wait(10):raise AssertionError('Test coordination timed out')
                    Grant.objects.filter(case=f['case'],user=f['acceptor'],action='validation.accept').update(active=False)
            finally:close_old_connections()
        def accept():
            close_old_connections()
            try:
                try:domain.review(f['acceptor'],f['case'].pk,f['package'].pk,'acceptance','approve','accept-race',f['decision_evidence'].pk,'Explicit selected acceptance',None)
                except PermissionDenied:return 'held'
                return 'accepted'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(accept);commit.set();first.result(timeout=30);self.assertEqual(second.result(timeout=30),'held')
        self.assertEqual(ValidationReview.objects.filter(kind='acceptance').count(),0)
