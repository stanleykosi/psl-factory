from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import timedelta
from django.test import TransactionTestCase
from django.db import close_old_connections,transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import Case
from apps.finance import payments as domain
from apps.finance.models import PaymentReleaseReservation,PaymentDecision
from .payment_helpers import fixture,configure
from .helpers import rev

class PaymentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.f=fixture();f=self.f;configure(f.actor,f.case,f.cov,f.approver)
        self.assessment=domain.assess(f.actor,f.case.pk,f.d.pk,f.cov.pk,rev(f.case))
        self.request=domain.request_exception(f.actor,f.case.pk,self.assessment.pk,'request-race','Exact synthetic release review',f.e['requirements'].pk,timezone.now()-timedelta(seconds=1),timezone.now()+timedelta(minutes=10),rev(f.case))
        domain.decide(f.approver,f.case.pk,self.request.pk,'approve',f.e['policy_decision'].pk,'Human shortfall decision',rev(f.case))

    def test_concurrent_reservations_have_one_immutable_receipt(self):
        def work(_):
            close_old_connections()
            try:return domain.reserve(self.f.actor,self.f.case.pk,self.assessment.pk,'same-release-intent',None,self.request.pk).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(work,[1,2]))
        self.assertEqual(results[0],results[1]);self.assertEqual(PaymentReleaseReservation.objects.count(),1)

    def test_revocation_committed_before_reservation_prevents_use(self):
        locked=Event();commit=Event()
        def revoke():
            close_old_connections()
            try:
                with transaction.atomic():
                    Case.objects.select_for_update().get(pk=self.f.case.pk);locked.set()
                    if not commit.wait(10):raise AssertionError('Test coordination timed out')
                    domain.decide(self.f.approver,self.f.case.pk,self.request.pk,'revoke',self.f.e['policy_decision'].pk,'Revoked before release reservation',None)
            finally:close_old_connections()
        def reserve():
            close_old_connections()
            try:
                try:domain.reserve(self.f.actor,self.f.case.pk,self.assessment.pk,'revoked-release',None,self.request.pk)
                except ValidationError:return 'held'
                return 'reserved'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(revoke);self.assertTrue(locked.wait(10));second=pool.submit(reserve);commit.set();first.result(timeout=30);self.assertEqual(second.result(timeout=30),'held')
        self.assertEqual(PaymentReleaseReservation.objects.count(),0);self.assertEqual(PaymentDecision.objects.count(),2)
