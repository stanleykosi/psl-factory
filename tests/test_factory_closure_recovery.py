"""Real PostgreSQL intake race and actual OS exits around local native closure commit."""
import os,sys,subprocess
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase
from django.db import connection,close_old_connections
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.core.models import Evidence
from apps.identity.models import Grant
from apps.pmo.models import DeliveryRecord
from apps.workflows import factory,factory_closure as closure
from apps.workflows.models import FactoryWork
from tests.helpers import rev
from tests.test_factory_closure import setup,configure,approve


class FactoryClosureRecoveryTests(TransactionTestCase):
    def worker(self,f,mode):
        result=subprocess.run([sys.executable,'-m','tests.factory_worker_scenario',str(f.work.pk),mode],
            env=dict(os.environ,PGDATABASE=connection.settings_dict['NAME']),capture_output=True,timeout=300)
        return result

    def expired(self,f):
        FactoryWork.objects.filter(pk=f.work.pk).update(lease_until=timezone.now()-timedelta(seconds=1));f.work.refresh_from_db()

    def test_two_real_connections_capture_one_private_intake_for_the_same_dossier(self):
        f=setup(profile=False,capture=False);barrier=Barrier(2)
        self.assertFalse(FactoryWork.objects.filter(case=f.case).exists())
        self.assertFalse(Evidence.objects.filter(case=f.case,kind=closure.KIND).exists())
        def enter(index):
            close_old_connections()
            try:
                from django.contrib.auth import get_user_model
                actor=get_user_model().objects.get(pk=f.actor.pk);barrier.wait()
                return closure.start(actor,f.case.pk,'PARALLEL-'+str(index),f.d.pk,f.inputs,'Project closure',None).pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(enter,[1,2]))
        self.assertEqual(ids[0],ids[1]);self.assertEqual(FactoryWork.objects.filter(case=f.case).count(),1)
        self.assertEqual(Evidence.objects.filter(case=f.case,kind=closure.KIND).count(),1)

    def test_actual_exit_before_commit_rolls_back_native_closure_then_one_recovery_retains_budget(self):
        f=setup();factory.run_until_wait(f.work.pk);approve(f)
        result=self.worker(f,'closure_interrupt_before_commit');self.assertEqual(result.returncode,38,result.stderr.decode())
        f.work.refresh_from_db();spent=f.work.budget_used;self.assertFalse(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').exists())
        self.expired(f);factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertEqual(f.work.status,'verified',f.work.finding)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').count(),1);self.assertEqual(f.work.budget_limit,20000)
        self.assertGreater(f.work.budget_used,spent)

    def test_actual_exit_after_commit_observes_original_closure_and_rechecks_current_authority_before_verification(self):
        f=setup();factory.run_until_wait(f.work.pk);approve(f)
        result=self.worker(f,'closure_interrupt_after_commit');self.assertEqual(result.returncode,39,result.stderr.decode())
        original=DeliveryRecord.objects.get(dossier=f.d,kind='closure');f.work.refresh_from_db();spent=f.work.budget_used
        self.assertNotEqual(f.work.status,'verified');self.expired(f)
        Grant.objects.filter(user=f.actor,case=f.case,action='delivery.closure_decide').update(active=False)
        factory.run_until_wait(f.work.pk);f.work.refresh_from_db();self.assertNotEqual(f.work.status,'verified')
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').count(),1)
        Grant.objects.filter(user=f.actor,case=f.case,action='delivery.closure_decide').update(active=True)
        factory.manage(f.actor,f.work.pk,f.work.revision,'resume');factory.run_until_wait(f.work.pk);f.work.refresh_from_db()
        self.assertEqual(f.work.status,'verified',f.work.finding);self.assertEqual(closure.verify(f.work)['closure'],original.pk)
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').count(),1);self.assertEqual(f.work.budget_limit,20000)
        self.assertGreater(f.work.budget_used,spent)

    def test_stop_after_committed_closure_records_followup_and_never_claims_it_was_cancelled(self):
        f=setup();factory.run_until_wait(f.work.pk);approve(f)
        result=self.worker(f,'closure_interrupt_after_commit');self.assertEqual(result.returncode,39,result.stderr.decode());self.expired(f)
        closure.cancel(f.actor,f.work.pk,f.work.revision);f.work.refresh_from_db();self.assertEqual(f.work.status,'followup_needed')
        self.assertEqual(DeliveryRecord.objects.filter(dossier=f.d,kind='closure').count(),1)
        with self.assertRaises(ValidationError):closure.restart(f.actor,f.work.pk,f.work.revision,rev(f.case),'Cannot reopen native closure by restarting a worker')
