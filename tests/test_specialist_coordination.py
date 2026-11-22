from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.agents import specialist_coordination
from apps.agents.specialist_models import SpecialistCoordination
from apps.pmo import rfp
from apps.workflows import factory_progress
from tests.helpers import rev
from tests.native_station_helpers import start_station
from tests.test_rfp import fixture


class CoordinatorBoundaries(TestCase):
    @patch.dict("os.environ", {"PSL_OPENROUTER_COORDINATION": "1"})
    def test_operational_source_permission_is_explicit_and_revocable(self):
        from types import SimpleNamespace
        from django.utils import timezone
        from apps.core.services import add_evidence
        from apps.policy.project_use import ProjectUseForm
        from apps.policy.services import transition
        from tests.helpers import setup_case

        actor, case = setup_case(username="operational-coordinator-scope", synthetic=False)
        work = SimpleNamespace(case=case)
        proof = add_evidence(actor, case.pk, "policy_decision", "Recorded synthetic policy test evidence", "test")
        data = {"roles": ["A01", "A03", "A05"], "processes": ["F02"],
                "source_kinds": ["native_station_projection"], "model": "scoped-test-model",
                "effective": timezone.now().isoformat(), "proof": proof.pk}
        component = specialist_coordination.memory.COMPONENT
        self.assertFalse(specialist_coordination.enabled_model(work, data["model"]))
        form = ProjectUseForm(actor, case, component, data)
        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save(actor)
        for state in ("validated", "active"):
            transition(actor, rule.pk, state)
        self.assertFalse(specialist_coordination.enabled_model(work, data["model"]))
        form = ProjectUseForm(actor, case, component, {**data, "coordinate_specialists": True})
        self.assertTrue(form.is_valid(), form.errors)
        approved = form.save(actor)
        for state in ("validated", "active"):
            transition(actor, approved.pk, state)
        self.assertEqual(specialist_coordination.enabled_model(work, data["model"]), data["model"])
        transition(actor, approved.pk, "revoked")
        self.assertFalse(specialist_coordination.enabled_model(work, data["model"]))

    def test_model_cannot_add_or_remove_a_specialist_or_invent_a_citation(self):
        route = {"roles": {"A01": "Intake", "A02": "Source"}, "sources": {"7": {"1": "Current source"}}}
        self.assertEqual(specialist_coordination.validated("route", {"order": ["A02", "A01"]}, route),
                         {"order": ["A02", "A01"]})
        for order in (["A01"], ["A01", "Admin"], ["A01", "A01"]):
            with self.assertRaises(ValidationError):
                specialist_coordination.validated("route", {"order": order}, route)
        focus = {"A01": [{"source": "7", "line": "1"}]}
        self.assertEqual(specialist_coordination.validated("route", {"order": ["A02", "A01"], "focus": focus},
                                                           route)["focus"], focus)
        with self.assertRaises(ValidationError):
            specialist_coordination.validated("route", {"order": ["A02", "A01"],
                "focus": {"A01": [{"source": "8", "line": "1"}]}}, route)
        review = {"reports": {"5": {"cited_evidence": {"1": "Current source"}}}}
        for report, line in (("6", "1"), ("5", "2")):
            with self.assertRaises(ValidationError):
                specialist_coordination.validated("review", {"findings": [
                    {"report": report, "line": line, "issue": "Unverified"}
                ]}, review)
        with self.assertRaises(ValidationError):
            specialist_coordination.validated("review", {"findings": [], "approve": True}, review)

    @patch.dict("os.environ", {"PSL_OPENROUTER_COORDINATION": "1"})
    def test_uncertain_dispatch_waits_for_current_owner_and_charges_one_explicit_retry(self):
        from django.utils import timezone
        from apps.identity.models import Grant
        from django.contrib.auth import get_user_model

        owner, case, proof, _, _ = fixture(record_intake=False)
        intake = rfp.intake(owner, case.pk, "COORDINATOR-RECOVERY", proof["rfp_intake"].pk, timezone.now(),
                            "not_stated", None, None, "Synthetic bid intake", rev(case))
        work = start_station(self, "P45", intake)
        factory_progress.run_once(work_id=work.pk)
        job = SpecialistCoordination.objects.get(packet__work=work, phase="route")
        with patch("adapters.openrouter.completion", side_effect=TimeoutError) as provider:
            self.assertTrue(specialist_coordination.run_once())
            self.assertFalse(specialist_coordination.run_once())
            self.assertEqual(provider.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.status, "uncertain")
        self.assertFalse(job.packet.members.exclude(status="awaiting_route").exists())
        other = get_user_model().objects.create_user("unassigned-coordinator-retry")
        Grant.objects.create(case=case, user=other, action="case.read")
        url = f"/api/v1/work/{work.pk}/coordination/{job.pk}/retry"
        work.refresh_from_db()
        revision = work.revision
        spent = work.budget_used
        data = {"revision": revision, "reason": "Confirmed a fresh synthetic model check is needed."}
        self.client.force_login(other)
        self.assertEqual(self.client.post(url, data, content_type="application/json").status_code, 403)
        self.client.force_login(owner)
        self.assertEqual(self.client.post(url, data, content_type="application/json").status_code, 202)
        self.assertNotEqual(self.client.post(url, data, content_type="application/json").status_code, 202)
        self.assertTrue(specialist_coordination.run_once())
        job.refresh_from_db()
        work.refresh_from_db()
        self.assertEqual(job.status, "ready", job.finding)
        self.assertEqual(job.attempts, 2)
        self.assertEqual(work.budget_used - spent, job.packet.members.first().token_limit)
        self.assertFalse(job.packet.members.exclude(status="queued").exists())
        first = job.packet.members.get(role=job.result["order"][0])
        allowed = specialist_coordination.memory.current(first, owner)
        self.assertEqual(specialist_coordination.focus_lines(first, allowed), [next(iter(allowed))])
