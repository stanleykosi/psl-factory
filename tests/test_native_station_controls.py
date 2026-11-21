from django.db import DatabaseError, transaction
from django.test import TransactionTestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from apps.identity.models import Grant
from apps.pmo import approval_routing
from apps.pmo.models import ApprovalRouteReceipt
from apps.workflows import native_stations as stations
from apps.workflows.models import FactoryWork, NativeStation, NativeStationReceipt
from tests import approval_helpers
from tests.native_station_helpers import start_station, assert_waiting, finish_station


class NativeStationControls(TransactionTestCase):
    def test_disclosure_rule_requires_each_member_for_a_native_source(self):
        from apps.agents.specialists import routes, validate_selection
        roles = [role["id"] for role in routes()["P02"]["specialist_roles"]]
        validate_selection(["P02"], roles, ["native_station_projection"])
        with self.assertRaises(ValidationError):
            validate_selection(["P02"], roles[:-1], ["native_station_projection"])

    def test_original_source_event_permissions_and_verified_receipt(self):
        f = approval_helpers.fixture()
        actor, case, request = f["actor"], f["case"], f["request"]
        work = start_station(self, "P02", request)
        event = work.native_station
        stations.capture(type(request), request)
        self.assertEqual(NativeStation.objects.get(process="P02", subject_model=request._meta.label_lower,
                                                  subject_pk=str(request.pk)), event)
        self.assertEqual(stations.enroll(event.pk), work)
        with self.assertRaises(ValidationError):
            stations.receive_advice("P02", request, actor, case=case)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FactoryWork.objects.filter(pk=work.pk).update(status="verified")
        self.assertFalse(NativeStationReceipt.objects.filter(handoff__station=event).exists())
        assert_waiting(self, work)
        self.client.force_login(actor)
        page = reverse("factory_detail", args=[work.pk])
        self.assertContains(self.client.get(page), "Department handoff")
        acknowledgement = stations.receive_advice("P02", request, actor, case=case)
        self.assertEqual(acknowledgement.station_id, event.pk)
        job = approval_routing.reserve(actor, case.pk, request.pk)
        self.assertTrue(approval_routing.run_once(case_id=case.pk, job_id=job.pk))
        receiver = ApprovalRouteReceipt.objects.get(job=job)
        receipt = finish_station(self, work, receiver)
        self.assertContains(self.client.get(page), "The receiving record was verified")
        self.assertNotContains(self.client.get(page), "The earlier receipt needs rechecking")
        with self.assertRaises(DatabaseError), transaction.atomic():
            NativeStationReceipt.objects.filter(pk=receipt.pk).update(receiver_pk="another-record")
        Grant.objects.filter(case=case, user=actor, action="agent.extract").update(active=False)
        self.assertFalse(stations.readable(actor, work))
        response = self.client.get(page)
        self.assertNotContains(response, "The receiving record was verified", status_code=response.status_code)
