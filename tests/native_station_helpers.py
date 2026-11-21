"""Synthetic acceptance through the source signal, O01, source readers and receiving service."""

import json
import hashlib
import os
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone

from adapters import case_uploads, openrouter
from apps.agents import specialist_memory
from apps.agents.specialists import routes
from apps.core.services import add_evidence
from apps.identity.models import Grant
from apps.policy.services import resolve
from apps.workflows import factory_progress, native_stations
from apps.workflows.models import FactoryAttempt, NativeStation, NativeStationAdvice, NativeStationReceipt
from tests.test_engagement_intake import activate


def _providers(test):
    if hasattr(test, "_station_artifacts"):
        return
    if getattr(test, "live_provider", False):
        from django.db import connection
        test.assertEqual((os.getenv("RAILWAY_SERVICE_NAME"), connection.settings_dict["NAME"]),
                         ("psl-design-checks", "test_psl_specialist_loop"))
        test.assertEqual(os.getenv("PSL_STATION_LIVE"), "1")
        test.enterContext(patch.dict(os.environ, OPENROUTER_MODEL=os.environ["PSL_ACCEPTANCE_SOURCE_MODEL"],
                                     OPENROUTER_API_KEY=os.environ["PSL_ACCEPTANCE_SOURCE_KEY"]))
        test._station_artifacts = None
        return
    test._station_artifacts = {}
    test.enterContext(patch.dict(os.environ, OPENROUTER_MODEL="station-test", OPENROUTER_API_KEY="test-only"))
    test.enterContext(patch.object(case_uploads, "put", side_effect=test._station_artifacts.__setitem__))
    test.enterContext(patch.object(case_uploads, "read", side_effect=lambda row: test._station_artifacts[row.key]))
    def interpret(model, instruction, source, **kwargs):
        lines = json.loads(source)
        return {"summary": next(iter(lines.values())), "quotes": [next(iter(lines))], "gaps": [], "assessment": "supported"}
    test.enterContext(patch.object(openrouter, "completion", side_effect=interpret))


def start_station(test, process, subject):
    _providers(test)
    # The actual source command must have created the intake durably. Don't
    # manufacture an event if a signal or bulk-insert path is missing.
    station = NativeStation.objects.get(process=process, subject_model=subject._meta.label_lower, subject_pk=str(subject.pk))
    route, fresh = native_stations.subject_for(station)
    actor = route.owner(fresh)
    case = native_stations.checked_observation(station, actor).case
    test.assertTrue(case.synthetic)
    for action in ("case.read", "factory.read", "factory.execute", "agent.extract"):
        Grant.objects.update_or_create(user=actor, case=case, action=action, defaults={"active": True})
    if resolve(native_stations.COMPONENT, case).status != "ACTIVE":
        admin = get_user_model().objects.filter(grant__case=case, grant__active=True, grant__action="policy.configure").order_by("pk").first()
        test.assertIsNotNone(admin)
        proof = case.evidence.filter(kind="policy_decision").first()
        if proof is None:
            proof = add_evidence(admin, case.pk, "policy_decision", "Synthetic coordinator limits", "synthetic:coordinator")
        profile = json.loads(Path("fixtures/factory-native-station.json").read_text())
        profile.pop("classification")
        if getattr(test, "live_provider", False):
            Grant.objects.update_or_create(user=actor, case=case, action="factory.information", defaults={"active":True})
            profile["information_resolver_id"] = actor.pk
        activate(admin, case, native_stations.COMPONENT, profile, proof)
    return native_stations.enroll(station.pk)


def _drive(test, work, *, through_receipt):
    # Drive the production progress handler for this item. Source readers select
    # their own database leases. Tests can prepare several sibling stations.
    job = work.background_progress
    for _ in range(12):
        type(job).objects.filter(pk=job.pk).update(available_at=timezone.now())
        factory_progress.run_once(work_id=work.pk)
        while specialist_memory.run_once():
            pass
        if getattr(test, "live_provider", False):
            from apps.agents import specialist_packets
            work.refresh_from_db()
            result = specialist_packets.review_for(work, work.actor)
            if result:
                test.assertTrue(all(row["status"] == "ready" for row in result["contributions"]))
                specialist_packets.acknowledge(work.actor, work.pk, result["packet"], result["digest"],
                    "Synthetic source reviewer checked the cited lines. Retain the gaps and require the native department decision.")
        work.refresh_from_db()
        job.refresh_from_db()
        status = job.status
        if work.status == "verified":
            return
        if not through_receipt and NativeStationAdvice.objects.filter(station=work.native_station).exists():
            return
        if status in ("held", "finished") or work.status in ("blocked", "configuration_needed"):
            test.fail(f"{work.native_station.process} stopped: {work.status} {work.finding}")
    test.fail(f"{work.native_station.process} did not reach its expected handoff: {work.status} {work.finding}")


def assert_waiting(test, work):
    _drive(test, work, through_receipt=False)
    station = work.native_station
    test.assertIsNone(native_stations.checked_work(work, work.actor).receipt)
    test.assertFalse(NativeStationReceipt.objects.filter(handoff__station=station).exists())
    test.assertTrue(NativeStationAdvice.objects.filter(station=station).exists())


def finish_station(test, work, expected_receipt):
    _drive(test, work, through_receipt=True)
    test.assertEqual(work.status, "verified")
    station = work.native_station
    receipt = NativeStationReceipt.objects.get(handoff__station=station)
    test.assertEqual((receipt.receiver_model, receipt.receiver_pk), (expected_receipt._meta.label_lower, str(expected_receipt.pk)))
    packet = receipt.handoff.packet
    test.assertIsNotNone(packet.consumed_at)
    test.assertSetEqual(set(packet.members.values_list("role", flat=True)), {row["id"] for row in routes()[station.process]["specialist_roles"]})
    for row in packet.members.all():
        test.assertEqual(row.status, "ready")
        test.assertEqual(hashlib.sha256(case_uploads.read(row)).hexdigest(), row.sha256)
    test.assertTrue(FactoryAttempt.objects.filter(activity__work=work, activity__kind="ACT13", phase="observed", result__station_receipt=receipt.pk).exists())
    print(f"Native station verified {station.process} -> {receipt.receiver_model}", flush=True)
    return receipt
