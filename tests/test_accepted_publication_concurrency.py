from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.db import close_old_connections,transaction
from django.test import TransactionTestCase
from django.core.exceptions import PermissionDenied,ValidationError
from apps.core.models import Case
from apps.identity.models import Grant
from apps.documents.delivery import claim_publication
from apps.documents.models import PublicationReceipt
from apps.finance import accepted_documents as d
from .accepted_publication_helpers import ready,reviewed
from .readiness_helpers import endpoint

class AcceptedPublicationConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_two_publishers_reserve_one_exact_intent(self):
  with endpoint():
   f=ready('metadata-reservation-race');v=reviewed(f)
   with ThreadPoolExecutor(max_workers=2) as pool:
    tasks=[pool.submit(self.task,lambda:d.publish(f['acceptor'],f['case'].pk,v.pk).pk) for _ in range(2)]
    ids=[t.result(timeout=180) for t in tasks]
   self.assertEqual(ids[0],ids[1]);self.assertEqual(d.Publication.objects.count(),1);self.assertEqual(d.PublicationJob.objects.count(),1)
 def test_committed_source_revocation_precedes_worker_delivery(self):
  with endpoint():
   f=ready('metadata-source-race');v=reviewed(f);d.publish(f['acceptor'],f['case'].pk,v.pk);lease=claim_publication();locked=Event();commit=Event()
   def revoke():
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['case'],user=f['actor'],action='ledger.private.read').update(active=False)
   def deliver():
    try:d.deliver(*lease);return 'leaked'
    except PermissionDenied:return 'denied'
   with ThreadPoolExecutor(max_workers=2) as pool:
    one=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));two=pool.submit(self.task,deliver);commit.set();one.result(timeout=60);self.assertEqual(two.result(timeout=90),'denied')
   self.assertEqual(PublicationReceipt.objects.count(),0)
