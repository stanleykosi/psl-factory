import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, connections, close_old_connections
from django.test import TransactionTestCase
from django.utils import timezone
from apps.finance import analysis
from apps.finance.models import FinanceRun
from apps.finance.documents import draft_report
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import claim_publication, deliver_internal
from apps.documents.models import PublicationJob, PublicationReceipt
from .finance_analysis_helpers import fixture, pipeline
from .helpers import rev


class FinanceWorkerTests(TransactionTestCase):
    def test_two_postgres_connections_build_one_exact_mapping(self):
        actor, case, _, _, _, source, _, _ = fixture()

        def calculate():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=actor.pk)
                return analysis.map_source(user, case.pk, source.pk, [], None).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: calculate(), range(2)))
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertEqual(results[0], results[1])
        self.assertEqual(FinanceRun.objects.filter(case=case, kind='mapping').count(), 1)

    def test_separate_process_reconciles_receipt_after_worker_loss(self):
        actor, case, evidence, _, _, source, template, _ = fixture()
        _, _, output = pipeline(actor, case, source)
        analysis.review(actor, case.pk, 'output', output.pk, 'Finance', 'approve',
                        evidence['finance_review'].pk, 'Exact aggregate reviewed', rev(case))
        document = draft_report(actor, case.pk, output.pk, template.pk, 'internal', rev(case))
        reserve_publication(actor, case.pk, document.pk, rev(case))
        job_id, fence = claim_publication()
        deliver_internal(job_id, fence)
        # Persist the crash boundary: local receipt committed, worker confirmation absent.
        PublicationJob.objects.filter(pk=job_id).update(lease_until=timezone.now()-timedelta(seconds=1))
        env = dict(os.environ, PGDATABASE=connection.settings_dict['NAME'])
        result = subprocess.run([sys.executable, str(settings.BASE_DIR/'manage.py'),
                                 'work_publications', '--limit', '1'],
                                cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('Processed 1 publication', result.stdout)
        job = PublicationJob.objects.get(pk=job_id)
        self.assertEqual(job.status, 'confirmed')
        self.assertEqual(job.fence, fence+1)
        self.assertEqual(PublicationReceipt.objects.count(), 1)
