from concurrent.futures import ThreadPoolExecutor
from threading import Event
from django.test import TransactionTestCase,override_settings
from django.db import close_old_connections,transaction
from django.core.exceptions import PermissionDenied
from apps.core.models import Case
from apps.identity.models import Grant
from apps.finance import publication_readiness as n
from apps.workflows import readiness as r,readiness_delivery as w
from .publication_readiness_helpers import fixture,capture,configure,enrolled
from .readiness_helpers import endpoint

@override_settings(READINESS_DATABASE_REVISION='fixture-v1')
class PublicationReadinessConcurrencyTests(TransactionTestCase):
 def task(self,call):
  close_old_connections()
  try:return call()
  finally:close_old_connections()
 def test_two_connections_capture_one_binding_and_reserve_one_probe(self):
  with endpoint():
   f=fixture('native-readiness-race');configure(f)
   with ThreadPoolExecutor(max_workers=2) as pool:
    items=[pool.submit(self.task,lambda:capture(f).pk) for _ in range(2)];ids=[x.result(timeout=120) for x in items]
   self.assertEqual(ids[0],ids[1]);self.assertEqual(n.Binding.objects.count(),1);f['contract']=r.IntegrationContract.objects.get(pk=ids[0])
   with ThreadPoolExecutor(max_workers=2) as pool:
    items=[pool.submit(self.task,lambda:w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'same-health','health').pk) for _ in range(2)];ids=[x.result(timeout=120) for x in items]
   self.assertEqual(ids[0],ids[1]);self.assertEqual(r.IntegrationProbe.objects.filter(contract=f['contract']).count(),1)
 def test_foreign_source_revocation_precedes_cached_report_and_native_probe(self):
  with endpoint():
   f=fixture('native-readiness-foreign',foreign=True);enrolled(f);j=w.reserve(f['actor'],f['case'].pk,f['contract'].pk,'after-revocation','health');count=r.IntegrationObservation.objects.filter(contract=f['contract']).count();locked=Event();commit=Event()
   def revoke():
    with transaction.atomic():
     Case.objects.select_for_update().get(pk=f['foreign_case'].pk);locked.set()
     if not commit.wait(10):raise AssertionError('Coordination timeout')
     Grant.objects.filter(case=f['foreign_case'],user=f['actor'],action='ledger.private.read').update(active=False)
   def report():
    try:r.report(f['actor'],f['case'].pk,f['assessment'].pk);return 'leaked'
    except PermissionDenied:return 'denied'
   with ThreadPoolExecutor(max_workers=2) as pool:
    one=pool.submit(self.task,revoke);self.assertTrue(locked.wait(10));two=pool.submit(self.task,report);commit.set();one.result(timeout=60);self.assertEqual(two.result(timeout=90),'denied')
   w.run_once(case_id=f['case'].pk);j.refresh_from_db();self.assertEqual(j.status,'held');self.assertEqual(r.IntegrationObservation.objects.filter(contract=f['contract']).count(),count)


 def test_receipt_database_permission_error_is_sanitised(self):
  from django.db import connection
  from uuid import uuid4
  from adapters.finance_publication_readiness import FinancePublicationReadinessAdapter
  with endpoint():
   f=fixture('native-receipt-db-denial');self.assertEqual(connection.settings_dict['NAME'],'test_psl');self.assertTrue(f['case'].synthetic);f['job'].publication
   role='psl_test_receipt_'+uuid4().hex
   with connection.cursor() as cur:cur.execute('CREATE ROLE '+role+' NOLOGIN')
   try:
    with connection.cursor() as cur:
     cur.execute('GRANT USAGE ON SCHEMA public TO '+role);cur.execute('SET ROLE '+role)
     cur.execute("SELECT has_table_privilege(current_user,'documents_publicationreceipt','SELECT')");self.assertFalse(cur.fetchone()[0])
    with self.assertRaisesRegex(ConnectionError,'^Scoped native publication receipt lookup unavailable$'):FinancePublicationReadinessAdapter().receipts(f['job'])
   finally:
    with connection.cursor() as cur:
     cur.execute('RESET ROLE');cur.execute('REVOKE USAGE ON SCHEMA public FROM '+role);cur.execute('DROP ROLE '+role)
   self.assertEqual(FinancePublicationReadinessAdapter().receipts(f['job'])['state'],'not_found')
