"""Legacy native publication contracts remain outside stricter factory recovery."""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from adapters.publications import InternalPublicationAdapter
from apps.documents.controlled import request_review,review_version,reserve_publication
from apps.documents.delivery import run_publication_once,receipt_only_recovery
from apps.documents.models import PublicationJob,PublicationReceipt
from apps.pmo.reporting import draft_minutes,draft_period_report
from tests.meeting_helpers import meetings_fixture
from tests.helpers import rev

class LegacyPublicationRecoveryTests(TestCase):
    def setUp(self):
        self.a,self.c,self.owner,self.notes,self.minutes,self.report,self.meeting,self.recipient=meetings_fixture()
    def recover(self,binding):
        request_review(self.a,self.c.pk,binding.version_id,rev(self.c))
        review_version(self.a,self.c.pk,binding.version_id,'approve','Exact legacy native projection',rev(self.c))
        p=reserve_publication(self.a,self.c.pk,binding.version_id,rev(self.c))
        self.assertFalse(receipt_only_recovery(p));self.assertNotIn('source_mode',binding.manifest)
        class Counter(InternalPublicationAdapter):
            calls=0
            def deliver(self,*args):self.calls+=1;return super().deliver(*args)
        PublicationJob.objects.filter(publication=p).update(status='unknown')
        adapter=Counter();run_publication_once(adapter,job_id=p.job.pk)
        self.assertEqual(adapter.calls,1);self.assertEqual(PublicationJob.objects.get(publication=p).status,'confirmed')
        self.assertEqual(PublicationReceipt.objects.filter(publication=p).count(),1)
    def test_legacy_unbound_native_minutes_keeps_idempotent_recovery(self):
        self.recover(draft_minutes(self.a,self.c.pk,self.meeting.meeting_id,self.minutes.pk,'client',rev(self.c)))
    def test_legacy_full_weekly_report_keeps_idempotent_recovery(self):
        end=timezone.now();self.recover(draft_period_report(self.a,self.c.pk,'weekly_client',end-timedelta(days=7),end,self.report.pk,'client',rev(self.c)))
