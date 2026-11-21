"""O01 fan-out, evidence join, independent business approval and scoped reuse."""

import hashlib
import os
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from adapters import case_uploads, openrouter
from adapters.factory_invoices import MockFactoryInvoiceAdapter
from apps.agents import specialist_memory as memory, specialist_packets as packets, specialists
from apps.agents.specialist_models import SpecialistPacket, SpecialistReading
from apps.finance.models import Invoice, InvoiceDelivery, InvoiceIssue
from apps.identity.models import Grant
from apps.workflows import factory_progress
from apps.workflows.models import FactoryAttempt, FactoryProgress
from tests.factory_helpers import approve, fixture
from tests.obligation_helpers import identified


class LoopSetup:
    def pmo_group(self, process):
        from tests.test_engagement_intake import activate

        if process == "P16":
            from tests.test_factory_engagement import setup

            f = setup(configured=False)
            actor, work = f["a"], f["w"]
            activate(
                actor,
                f["c"],
                "OPS.factory_engagement_execution",
                dict(f["values"], tokens_per_call=650),
                f["policy"],
            )
        elif process == "P43":
            from tests.test_factory_minutes import FactoryMinutesTests

            f = FactoryMinutesTests()
            f.setUp()
            activate(
                f.actor, f.case, "OPS.factory_minutes_execution", dict(f.value, tokens_per_call=650), f.owner
            )
            actor, work = f.actor, f.start()
        elif process == "P28":
            from django.utils import timezone
            from apps.pmo import progress
            from tests.helpers import rev
            from tests.test_factory_delivery import setup

            f = setup(configure=False)
            profile = json.loads(Path("fixtures/factory-delivery.json").read_text())
            profile.pop("classification")
            activate(
                f.actor,
                f.case,
                "OPS.factory_delivery_execution",
                dict(profile, tokens_per_call=650),
                f.e["policy_decision"],
            )
            source = progress.configure(
                f.actor,
                f.case.pk,
                f.d.pk,
                "Engineering",
                "Synthetic board",
                "M2",
                f.actor.pk,
                "synthetic_mock",
                f.e["requirements"].pk,
                rev(f.case),
            )
            progress.observe(
                f.actor,
                f.case.pk,
                source.pk,
                None,
                "r1",
                timezone.now(),
                "available",
                {
                    "activity_ref": "M2",
                    "dependency_ref": "D1",
                    "summary": "M2 waits for D1.",
                    "timeline_impact": True,
                    "scope_change": False,
                },
                rev(f.case),
            )
            actor, work = f.actor, f.work
        else:
            from tests.test_factory_reporting import FactoryReportingTests

            f = FactoryReportingTests()
            f.setUp()
            f.configure(tokens_per_call=650)
            actor, work = f.actor, f.start_work()
        self.assertTrue(work.case.synthetic)
        job = factory_progress.set_progress(actor, work.pk, work.revision, True)
        self.assertEqual(factory_progress.run_once(), job.pk)
        work.refresh_from_db()
        self.assertTrue(SpecialistPacket.objects.filter(work=work, process=process).exists(), work.finding)
        packet = SpecialistPacket.objects.get(work=work, process=process)
        try:
            while memory.run_once():
                pass
            expected = {role["id"] for role in specialists.routes()[process]["specialist_roles"]}
            self.assertEqual(set(packet.members.values_list("role", flat=True)), expected)
            for result in packet.members.all():
                self.assertEqual(result.status, "ready", (result.process, result.role, result.finding))
                self.assertEqual(hashlib.sha256(case_uploads.read(result)).hexdigest(), result.sha256)
            self.assertIn(packets.inspect(packet, actor)["state"], {"ready", "review"})
            print("Checked source work:", process, sorted(expected))
        finally:
            if getattr(self, "live_provider", False):
                for row in packet.members.exclude(sha256=""):
                    case_uploads.discard_unbound(row.key)

    def start_invoice(self):
        data = fixture(tokens_per_call=650, username="specialist-source-preparer")
        self.actor, self.work = data["actor"], data["work"]
        self.client.force_login(self.actor)
        data["case"].refresh_from_db()
        request = {
            "case": data["case"].pk,
            "key": self.work.key,
            "revision": data["case"].revision,
            "reference": self.work.request["reference"],
            "handoff": data["handoff"].pk,
            "coverage": data["coverage"].pk,
        }
        self.assertRedirects(
            self.client.post(reverse("factory_create"), request),
            reverse("factory_detail", args=[self.work.pk]),
            fetch_redirect_response=False,
        )
        self.job = FactoryProgress.objects.get(work=self.work)
        return data

    def reach_wait(self):
        for _ in range(35):
            self.assertEqual(factory_progress.run_once(), self.job.pk)
            self.job.refresh_from_db()
            if self.job.status != "queued":
                return self.job.status
        self.fail("Factory did not stop within the step allowance.")

    def resolve(self, packet):
        state = packets.inspect(packet, self.actor)
        self.assertEqual(state["state"], "review")
        url = reverse("resolve_source_findings", args=[self.work.pk, packet.pk])
        self.assertRedirects(
            self.client.post(
                url,
                {
                    "digest": state["digest"],
                    "reason": "I checked the synthetic source against the milestone. Finance must review the invoice.",
                },
            ),
            reverse("factory_detail", args=[self.work.pk]),
            fetch_redirect_response=False,
        )
        packet.refresh_from_db()
        self.assertEqual(packet.reviewer, self.actor)

    def complete_review_groups(self):
        for _ in range(15):
            while memory.run_once():
                pass
            for packet in SpecialistPacket.objects.filter(work=self.work, consumed_at=None):
                if packets.inspect(packet, self.actor)["state"] == "review":
                    self.resolve(packet)
            factory_progress.wake_waiting(self.work.pk)
            status = self.reach_wait()
            if not SpecialistPacket.objects.filter(work=self.work, consumed_at=None).exists():
                return status
        self.fail("Source reviews did not reach the native decision.")

    def verify_outcome(self, data):
        self.assertEqual(self.complete_review_groups(), "waiting")
        self.assertFalse(InvoiceIssue.objects.filter(invoice__case=self.work.case).exists())
        self.work.refresh_from_db()
        identified(self.actor, self.work.case, self.work.invoice, configuring_actor=self.actor)
        factory_progress.wake_waiting(self.work.pk)
        self.assertEqual(self.complete_review_groups(), "waiting")
        approve(data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.observation, "")
        with (
            TemporaryDirectory() as directory,
            override_settings(FACTORY_ADAPTERS={str(self.work.case_id): MockFactoryInvoiceAdapter(directory)}),
        ):
            status = self.complete_review_groups()
            self.work.refresh_from_db()
            self.assertEqual(
                status,
                "finished",
                (
                    self.work.status,
                    self.work.finding,
                    list(self.work.activities.filter(status="failed").values_list("kind", flat=True)),
                ),
            )
        self.work.refresh_from_db()
        self.assertEqual(self.work.status, "verified", self.work.finding)
        self.assertTrue(InvoiceDelivery.objects.filter(invoice=self.work.invoice).exists())
        self.assertTrue(memory.outcome_sources(self.actor, [self.work.case_id], [self.work.definition]))
        from apps.agents.assistant import tool_context
        from apps.agents.assistant_models import AssistantConversation

        conversation = AssistantConversation.objects.create(
            actor=self.actor, case=self.work.case, persona="chidi"
        )
        records, _ = tool_context(conversation, question="Was the invoice delivered?")
        self.assertIn("factory_outcome", [row.get("record", {}).get("field") for row in records])
        self.assertTrue(
            FactoryAttempt.objects.filter(
                activity__work=self.work, result__specialist__has_key="source_handoffs"
            ).exists()
        )


class SpecialistLoopTests(LoopSetup, TransactionTestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, OPENROUTER_MODEL="test-only", OPENROUTER_API_KEY="test-only"))
        self.objects = {}
        self.enterContext(patch.object(case_uploads, "put", side_effect=self.objects.__setitem__))
        self.enterContext(patch.object(case_uploads, "read", side_effect=lambda row: self.objects[row.key]))
        self.provider = self.enterContext(
            patch.object(
                openrouter,
                "completion",
                return_value={
                    "summary": "The milestone source was reviewed.",
                    "quotes": ["1"],
                    "gaps": [],
                    "assessment": "supported",
                },
            )
        )

    def test_multi_specialist_loop(self):
        data = self.start_invoice()
        self.assertEqual(self.reach_wait(), "waiting")
        packet = SpecialistPacket.objects.get(work=self.work)
        self.assertSetEqual(set(packet.members.values_list("role", flat=True)), {"A04", "A07"})
        self.assertTrue(memory.run_once())
        self.assertEqual(packets.inspect(packet, self.actor)["state"], "waiting")
        self.assertFalse(Invoice.objects.filter(case=self.work.case).exists())
        self.verify_outcome(data)
        self.assertEqual(self.provider.call_count, SpecialistReading.objects.count())
        first = packet.members.order_by("pk").first()
        link = reverse("specialist_report", args=[self.work.pk, first.pk])
        self.assertEqual(hashlib.sha256(self.client.get(link).content).hexdigest(), first.sha256)
        Grant.objects.filter(case=self.work.case, user=self.actor, action="agent.extract").update(active=False)
        self.assertEqual(self.client.get(link).status_code, 404)

    def test_conflict_review_is_fenced_and_does_not_approve(self):
        self.start_invoice()
        self.reach_wait()
        packet = SpecialistPacket.objects.get(work=self.work)
        self.provider.side_effect = [
            {"summary": "Two source dates conflict.", "quotes": [1], "gaps": [], "assessment": "conflicting"},
            {"summary": "Evidence is present.", "quotes": [1], "gaps": [], "assessment": "supported"},
        ]
        while memory.run_once():
            pass
        self.assertEqual(self.reach_wait(), "waiting")
        with self.assertRaises(ValidationError):
            packets.acknowledge(self.actor, self.work.pk, packet.pk, "stale", "review")
        page = self.client.get(reverse("factory_detail", args=[self.work.pk]))
        self.assertContains(page, "Resolve source findings")
        self.resolve(packet)
        self.assertFalse(InvoiceIssue.objects.exists())
        self.assertEqual(packets.inspect(packet, self.actor)["state"], "ready")

    def test_uncertain_call_is_never_replayed_and_foreign_lines_are_rejected(self):
        self.start_invoice()
        self.reach_wait()
        self.provider.side_effect = [
            TimeoutError(),
            {"summary": "Unsupported", "quotes": [999], "gaps": [], "assessment": "supported"},
        ]
        while memory.run_once():
            pass
        self.assertSetEqual(
            set(SpecialistReading.objects.values_list("status", flat=True)), {"uncertain", "held"}
        )
        self.assertFalse(self.objects)
        self.assertEqual(self.provider.call_count, 2)
        packet = SpecialistPacket.objects.get(work=self.work)
        result = packets.inspect(packet, self.actor)
        self.assertEqual(result["state"], "unavailable")
        with self.assertRaises(ValidationError):
            packets.acknowledge(self.actor, self.work.pk, packet.pk, result["digest"], "Checked the missing reports")
        self.assertIsNone(packets.review_for(self.work, self.actor))
        self.assertEqual(self.reach_wait(), "waiting")
        self.assertFalse(InvoiceIssue.objects.exists())

    def test_concurrent_workers_take_distinct_tasks_and_retry_identical_storage_bytes(self):
        self.start_invoice()
        self.reach_wait()

        def consume():
            close_old_connections()
            try:
                return memory.run_once()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertEqual(list(workers.map(lambda _: consume(), range(2))), [True, True])
        self.assertEqual(self.provider.call_count, 2)
        self.assertEqual(SpecialistReading.objects.filter(status="storing").count(), 2)
        with patch.object(case_uploads, "put", side_effect=OSError("test bucket unavailable")):
            self.assertTrue(memory.run_once())
        while memory.run_once():
            pass
        self.assertEqual(self.provider.call_count, 2)
        self.assertEqual(SpecialistReading.objects.filter(status="ready").count(), 2)
        self.assertEqual(packets.inspect(SpecialistPacket.objects.get(), self.actor)["state"], "ready")

    def test_conflicting_anchors_require_a_decision_even_if_both_workers_report_support(self):
        self.start_invoice()
        self.reach_wait()
        packet = SpecialistPacket.objects.get()
        line = packet.members.first().source.body.splitlines()[0]
        self.provider.side_effect = [
            {
                "summary": "Source cited.",
                "quotes": [1],
                "gaps": [],
                "assessment": "supported",
                "facts": [{"field": "reference", "line": 1, "value": value}],
            }
            for value in (line[:2], line[-2:])
        ]
        while memory.run_once():
            pass
        result = packets.inspect(packet, self.actor)
        self.assertEqual(result["state"], "review")
        self.assertEqual(
            result["disagreements"], [{"source": packet.members.first().source_id, "field": "reference"}]
        )

    def test_route_coverage_and_deferred_processes(self):
        from apps.workflows.factory_definitions import DEFINITIONS
        from apps.workflows.factory_processes import PROCESS_IDS

        routes = specialists.routes()
        self.assertEqual(set(PROCESS_IDS), set(DEFINITIONS))
        self.assertTrue(
            all(
                pid in routes and routes[pid]["department"] != "BaaS"
                for ids in PROCESS_IDS.values()
                for pid in ids
            )
        )
        self.assertEqual(len(routes), 122)
        self.assertEqual(sum(row["department"] == "BaaS" for row in routes.values()), 14)
        self.assertEqual(
            {member["id"] for row in routes.values() for member in row["specialist_roles"]},
            {f"A{i:02}" for i in range(1, 9)},
        )
        with self.assertRaises(ValidationError):
            specialists.assignment("B14", "ACT04")

    def test_project_model_permission_needs_matching_roles_source_and_approval(self):
        from django.utils import timezone
        from apps.policy.project_use import ProjectUseForm
        from apps.policy.services import transition
        from tests.helpers import setup_case
        from tests.billing_helpers import evidence

        actor, case = setup_case(synthetic=False)
        proof = evidence(
            actor, case, "policy_decision", "Synthetic evidence of the test data owner's decision."
        )
        value = json.loads(Path("fixtures/specialist-source-reading.json").read_text())["value"]
        fields = dict(value, proof=proof.pk, effective=timezone.now().isoformat())
        invalid = ProjectUseForm(actor, case, memory.COMPONENT, dict(fields, roles=["A08"]))
        self.assertFalse(invalid.is_valid())
        self.assertIn("matching release specialist", str(invalid.errors))
        form = ProjectUseForm(actor, case, memory.COMPONENT, fields)
        self.assertTrue(form.is_valid(), form.errors)
        config = form.save(actor)
        from types import SimpleNamespace

        work = SimpleNamespace(case=case)
        with self.assertRaises(PermissionDenied):
            memory.permission(work, "A07", "P34", "completion", value["model"])
        transition(actor, config.pk, "validated")
        transition(actor, config.pk, "active")
        self.assertEqual(memory.permission(work, "A07", "P34", "completion", value["model"]), config.pk)
        with self.assertRaises(PermissionDenied):
            memory.permission(work, "A07", "P34", "meeting_notes", value["model"])

    def test_engagement_roles(self):
        self.pmo_group("P16")

    def test_minutes_roles(self):
        self.pmo_group("P43")

    def test_weekly_roles(self):
        self.pmo_group("P41")

    def test_four_specialists_join_the_native_delivery_progress_investigation(self):
        self.pmo_group("P28")

    def test_partial_membership_cannot_be_presented_as_a_complete_source_review(self):
        self.start_invoice()
        self.reach_wait()
        packet = SpecialistPacket.objects.get()
        packet.members.remove(packet.members.first())
        with self.assertRaisesMessage(PermissionDenied, "remaining assigned specialists"):
            packets.inspect(packet, self.actor)
        self.assertFalse(Invoice.objects.filter(case=self.work.case).exists())

    def test_replaced_source_reopens_the_group_without_reusing_its_review(self):
        from django.db import transaction
        from apps.workflows import factory
        from tests.billing_helpers import evidence

        self.start_invoice()
        self.reach_wait()
        packet = SpecialistPacket.objects.get()
        while memory.run_once():
            pass
        replacement = evidence(self.actor, self.work.case, "completion", "Corrected synthetic completion record.")
        with transaction.atomic():
            work = type(self.work).objects.select_for_update().get(pk=self.work.pk)
            _, profile = factory.profile(work)
            _, sources, *_ = factory.snapshot(work, profile)
            state, released = packets.join(work, self.actor, sources, profile)
            work.save(update_fields=["budget_used"])
        self.assertEqual((state, released), ("waiting", []))
        packet.refresh_from_db()
        self.assertIsNotNone(packet.superseded_by_id)
        successor = packet.superseded_by
        self.assertEqual(set(successor.members.values_list("source_id", flat=True)), {replacement.pk})
        self.assertEqual(set(successor.members.values_list("role", flat=True)), {"A04", "A07"})
        self.assertIsNone(successor.reviewed_at)
        self.assertIsNone(packet.consumed_at)
        self.assertFalse(InvoiceIssue.objects.exists())


class LiveSpecialistLoop(LoopSetup, TransactionTestCase):
    live_provider = True

    def setUp(self):
        if os.getenv("PSL_SPECIALIST_LIVE_TEST") != "1":
            self.skipTest("Opt-in Railway provider acceptance.")
        self.assertEqual(os.environ["RAILWAY_ENVIRONMENT_NAME"], "design-acceptance")
        self.assertEqual(connection.settings_dict["NAME"], "test_psl_specialist_loop")
        self.enterContext(
            patch.dict(
                os.environ,
                OPENROUTER_MODEL=os.environ["PSL_ACCEPTANCE_SOURCE_MODEL"],
                OPENROUTER_API_KEY=os.environ["PSL_ACCEPTANCE_SOURCE_KEY"],
            )
        )

    def test_railway_openrouter_and_private_storage(self):
        data = self.start_invoice()
        self.assertTrue(self.work.case.synthetic)
        try:
            self.verify_outcome(data)
            readings = list(SpecialistReading.objects.filter(work=self.work))
            self.assertGreaterEqual(len(readings), 4)
            for row in readings:
                self.assertEqual(row.status, "ready", (row.process, row.role, row.finding))
                self.assertEqual(hashlib.sha256(case_uploads.read(row)).hexdigest(), row.sha256)
            print("Real provider and private readback:", [(r.process, r.role, r.disposition) for r in readings])
        finally:
            for row in SpecialistReading.objects.filter(work=self.work).exclude(sha256=""):
                case_uploads.discard_unbound(row.key)

    def test_live_engagement(self):
        self.pmo_group("P16")

    def test_live_minutes(self):
        self.pmo_group("P43")

    def test_live_client_report(self):
        self.pmo_group("P41")

    def test_live_delivery_progress(self):
        self.pmo_group("P28")
