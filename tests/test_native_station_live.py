import os
from unittest import skipUnless

from django.test import TransactionTestCase

from adapters import case_uploads
from apps.agents.specialist_models import SpecialistReading
from apps.pmo import approval_routing
from apps.pmo.models import ApprovalRouteReceipt
from tests import approval_helpers, hrfinance_helpers
from tests.native_station_helpers import assert_waiting, finish_station, start_station


@skipUnless(os.getenv("PSL_STATION_LIVE") == "1", "Explicit synthetic Railway provider acceptance only.")
class NativeProviderAcceptance(TransactionTestCase):
    live_provider = True

    def station(self, process, subject):
        work = start_station(self, process, subject)
        self.assertTrue(work.case.synthetic)
        self.addCleanup(self.remove_reports, work)
        assert_waiting(self, work)
        return work

    @staticmethod
    def remove_reports(work):
        client, bucket = case_uploads.bucket()
        try:
            for row in SpecialistReading.objects.filter(work=work).exclude(sha256=""):
                client.delete_object(Bucket=bucket, Key=row.key)
        finally:
            client.close()

    def test_department_routing_from_source_to_receipt(self):
        fixture = approval_helpers.fixture()
        actor, case, request = fixture["actor"], fixture["case"], fixture["request"]
        work = self.station("P02", request)
        job = approval_routing.reserve(actor, case.pk, request.pk)
        self.assertTrue(approval_routing.run_once(case_id=case.pk, job_id=job.pk))
        receipt = ApprovalRouteReceipt.objects.get(job=job)
        self.assertFalse(receipt.payload["approval_granted"])
        finish_station(self, work, receipt)

    def test_restricted_hr_handoff_to_named_finance_recipient(self):
        fixture = hrfinance_helpers.fixture()
        work = start_station(self, "F35", fixture["contract"])
        self.addCleanup(self.remove_reports, work)
        snapshot = hrfinance_helpers.capture(fixture)
        assert_waiting(self, work)
        receipt = hrfinance_helpers.receive(fixture, snapshot)
        self.assertEqual(receipt.actor_id, fixture["finance"].pk)
        finish_station(self, work, receipt)
