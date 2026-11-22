"""Synthetic domain acceptance, including the exact receiving record for each station."""

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from adapters.finance import TimeoutAfterAccept
from apps.documents.controlled import reserve_publication
from apps.documents.delivery import run_publication_once
from apps.documents.models import PublicationReceipt
from apps.finance import contract_coverage, forecast, forecast_documents, hrfinance, receivables, usage_intake
from apps.finance.coordinator_operations import private_disclosure, receivable
from apps.finance.coordinator_operations_cash import publication as publication_observation
from apps.finance.models import ForecastBinding, Handoff, UsageIntakeAcceptance
from apps.pmo.services import complete_milestone
from apps.workflows.services import run_once as deliver_milestone
from apps.workflows.native_station_models import NativeStationUse
from . import forecast_helpers as forecasts
from . import hrfinance_helpers as disclosures
from . import recognition_helpers as recognition
from . import usage_intake_helpers as usage
from .billing_helpers import evidence
from .helpers import rev, setup_case, signed
from .native_station_helpers import assert_waiting, finish_station as verify_station, start_station
from .settlement_helpers import receipt as report_cash
from .test_contract_coverage import ContractCoverageFixture


def finish_station(test, work, expected, receiver=None):
    receipt = verify_station(test, work, expected)
    uses = NativeStationUse.objects.filter(handoff=receipt.handoff)
    if receiver is not None:
        uses = uses.filter(actor=receiver)
    test.assertTrue(uses.exists(), f"{work.native_station.process} must be consumed by the receiving command")


class FinanceHandoffStations(TransactionTestCase):
    def test_f28_reconciled_usage_handoff_to_pricing(self):
        actor, case, coverages, source, controls = usage.fixture()
        received = usage.receive(actor, case, source, controls)
        work = start_station(self, "F28", received.source)
        with self.assertRaisesMessage(ValidationError, "specialist findings"):
            usage_intake.accept(actor, case.pk, received.source_id, rev(case))
        self.assertFalse(UsageIntakeAcceptance.objects.filter(source=received.source).exists())
        assert_waiting(self, work)
        accepted = usage_intake.accept(actor, case.pk, received.source_id, rev(case))
        finish_station(self, work, accepted)
        self.assertEqual(set(accepted.partitions.values_list("coverage_id", flat=True)), {c.pk for c in coverages})

    def test_f32_reported_unverified_cash_goes_to_receivables(self):
        actor, case = setup_case()
        cash, _ = report_cash(actor, case, verify=False)
        work = start_station(self, "F32", cash)
        assert_waiting(self, work)
        position = receivables.snapshot(actor, case.pk, timezone.localdate(), rev(case))
        finish_station(self, work, position)
        self.assertIn(cash.pk, [r["receipt"] for r in position.result["reported_unverified"]])
        self.assertFalse(cash.cashverification_set.exists())
        report_cash(actor, case, ref="later-cash", verify=False)
        self.assertIsNone(receivable(cash, actor).receipt)
        refreshed = receivables.snapshot(actor, case.pk, timezone.localdate(), rev(case))
        self.assertEqual(receivable(cash, actor).receipt, refreshed)

    def test_f33_pmo_attestation_then_independent_finance_disposition(self):
        f = recognition.fixture()
        work = start_station(self, "F33", f["packet"])
        recognition.received(f)
        assert_waiting(self, work)
        reviewed = recognition.record(f, "review", verdict="reviewed", decision_evidence_id=f["decision"].pk)
        finish_station(self, work, reviewed, f["finance"])
        self.assertNotEqual(reviewed.actor_id, f["packet"].actor_id)

    def test_f34_uncertain_milestone_delivery_reconciles_original_finance_receipt(self):
        actor, case = setup_case()
        proof = signed(actor, case)["completion"]
        milestone = complete_milestone(actor, case.pk, "Station test milestone", proof.pk, rev(case))
        work = start_station(self, "F34", milestone)
        deliver_milestone(TimeoutAfterAccept(), case_id=case.pk)
        original = Handoff.objects.get(milestone=milestone)
        assert_waiting(self, work)
        deliver_milestone(case_id=case.pk)
        from apps.finance.services import begin_invoice_preparation
        preparation = begin_invoice_preparation(actor, case.pk, original.pk, rev(case))
        self.assertEqual(preparation.handoff_id, original.pk)
        finish_station(self, work, original)
        self.assertEqual(Handoff.objects.filter(milestone=milestone).count(), 1)

    def test_f35_private_hr_source_remains_with_its_named_finance_recipient(self):
        f = disclosures.fixture()
        work = start_station(self, "F35", f["contract"])
        snapshot = disclosures.capture(f)
        assert_waiting(self, work)
        with self.assertRaises(PermissionDenied):
            private_disclosure(f["contract"], f["hr"])
        ack = disclosures.receive(f, snapshot)
        finish_station(self, work, ack, f["finance"])
        projected = " ".join(private_disclosure(f["contract"], f["finance"]).lines.values())
        self.assertNotIn("private-staff-", projected)
        hrfinance.decide(f["hr"], f["case"].pk, f["contract"].pk, "revoke", "revoke-for-test",
                         f["e"]["hr_disclosure_decision"].pk, rev(f["case"]))
        with self.assertRaises(ValidationError):
            private_disclosure(f["contract"], f["finance"])

    def test_f35_return_and_revocation_hide_pre_capture_period_and_assistant_sources(self):
        from apps.agents.specialist_memory import outcome_sources, sources_for
        from apps.policy.hrfinance_validators import AUTHORITY, DISCLOSURE

        f = disclosures.fixture(configure=False)
        hr, reader, case, proof = f["hr"], f["finance"], f["case"], f["e"]
        disclosures.policy(hr, case, AUTHORITY, f["config"]["authority"], proof["owner"])
        disclosures.policy(hr, case, DISCLOSURE, f["config"]["disclosure"], proof["owner"])
        contract = hrfinance.contract(reader, case.pk, f["need"].pk, "pending-disclosure",
                                      proof["hr_contract_source"].pk, rev(case))
        work = start_station(self, "F35", contract)
        assert_waiting(self, work)
        self.client.force_login(reader)
        project = reverse("project_handoffs", args=[case.pk])
        detail = reverse("factory_detail", args=[work.pk])
        period = f["need"].payload["period"]
        definitions = ["finance-accounts/v1"]
        self.assertContains(self.client.get(project), f'href="{detail}"')
        self.assertContains(self.client.get(detail), period)
        self.assertTrue(sources_for(reader, [case.pk], definitions, work_id=work.pk))
        self.assertFalse(contract.snapshots.exists())

        for verdict in ("return", "revoke"):
            hrfinance.decide(hr, case.pk, contract.pk, "approve", "grant-before-" + verdict,
                             proof["hr_disclosure_decision"].pk, rev(case))
            hrfinance.decide(hr, case.pk, contract.pk, verdict, verdict + "-before-capture",
                             proof["hr_disclosure_decision"].pk, rev(case))
            with self.subTest(verdict=verdict):
                self.assertNotContains(self.client.get(project), f'href="{detail}"')
                self.assertIn(self.client.get(detail).status_code, (403, 404))
                self.assertFalse(sources_for(reader, [case.pk], definitions, work_id=work.pk))
                self.assertFalse(outcome_sources(reader, [case.pk], definitions))

    def test_f35_other_nominated_recipient_cannot_read_a_completed_receipt(self):
        from django.contrib.auth import get_user_model
        from apps.agents.specialist_memory import outcome_sources
        from apps.identity.models import Grant
        from apps.policy.hrfinance_validators import AUTHORITY, DISCLOSURE
        from apps.policy.services import register_reference
        from .helpers import activate

        f = disclosures.fixture(configure=False)
        hr, first, case, proof = f["hr"], f["finance"], f["case"], f["e"]
        second = get_user_model().objects.create_user(username="second-F35-recipient")
        for action in ("case.read", "hrfinance.read", "hrfinance.snapshot.read", "hrfinance.receive",
                       "factory.read", "agent.extract"):
            Grant.objects.create(case=case, user=second, action=action)
        principals = []
        for user, role in ((hr, "HR"), (first, "Finance"), (second, "Finance")):
            principals.append(register_reference(
                hr, case.pk, f"test-f35-role-{user.pk}", "schema:psl/role-assignment/v1",
                {"role": role, "user_id": user.pk}, proof["owner"].pk,
            ).ref)
        activate(hr, case, "D05.role_principal_assignments", principals, proof["owner"])
        cfg = f["config"]
        cfg["authority"]["assignments"].append({"user_id": second.pk, "role": "Finance", "purpose": "receive"})
        cfg["disclosure"]["recipient_ids"] = [first.pk, second.pk]
        cfg["need"]["recipient_ids"] = [first.pk, second.pk]
        disclosures.policy(hr, case, AUTHORITY, cfg["authority"], proof["owner"])
        disclosures.policy(hr, case, DISCLOSURE, cfg["disclosure"], proof["owner"])
        need = hrfinance.need(first, case.pk, "two-authorised-recipients", cfg["need"],
                              proof["hr_finance_need"].pk, rev(case))
        contract = hrfinance.contract(first, case.pk, need.pk, "two-party-contract", proof["hr_contract_source"].pk, rev(case))
        f["contract"] = contract
        hrfinance.decide(hr, case.pk, contract.pk, "approve", "approve-both", proof["hr_disclosure_decision"].pk, rev(case))
        work = start_station(self, "F35", contract)
        assert_waiting(self, work)
        self.client.force_login(second)
        project = reverse("project_handoffs", args=[case.pk])
        detail = reverse("factory_detail", args=[work.pk])
        self.assertContains(self.client.get(project), f'href="{detail}"')
        snapshot = disclosures.capture(f)
        received = disclosures.receive(f, snapshot)
        finish_station(self, work, received, first)
        # The second nominee still has current native read authority for this
        # snapshot. The completed receipt belongs exclusively to the first.
        self.assertEqual(hrfinance.snapshot_access(second, snapshot).pk, snapshot.pk)
        self.assertFalse(contract.records.filter(kind="receipt", actor=second).exists())
        self.assertNotContains(self.client.get(project), f'href="{detail}"')
        self.assertIn(self.client.get(detail).status_code, (403, 404))
        self.assertFalse(outcome_sources(second, [case.pk], ["finance-accounts/v1"]))
        self.assertTrue(outcome_sources(first, [case.pk], ["finance-accounts/v1"]))


class CoverageStations(ContractCoverageFixture, TransactionTestCase):
    def test_f45_terms_assessed_then_f31_received_by_named_finance_preparer(self):
        terms = self.terms(active=False)
        register = start_station(self, "F45", terms)
        assert_waiting(self, register)
        contract_coverage.transition(self.a, self.c.pk, terms.pk, "active", self.decision.pk, rev(self.c))
        assessment = self.assess(terms)
        finish_station(self, register, assessment)
        key = assessment.result["obligations"][0]["key"]
        request = contract_coverage.request_preparation(self.a, self.c.pk, assessment.pk, key, self.b.pk, rev(self.c))
        scheduled = start_station(self, "F31", request)
        assert_waiting(self, scheduled)
        with self.assertRaises(PermissionDenied):
            contract_coverage.receive_preparation(self.a, self.c.pk, request.pk, None, rev(self.c))
        receipt = contract_coverage.receive_preparation(self.b, self.c.pk, request.pk, None, rev(self.c))
        finish_station(self, scheduled, receipt, self.b)
        self.assertFalse(receipt.payload["invoice_issued"])


class CashForecastStations(TransactionTestCase):
    def setUp(self):
        self.actor, self.case, _ = forecasts.fixture()

    def test_f36_f37_f38_approve_one_calculation_with_three_distinct_source_analyses(self):
        actor, case = self.actor, self.case
        scenario = forecasts.scenario(actor, case)
        works = [start_station(self, process, scenario) for process in ("F36", "F37", "F38")]
        calculation = forecast.prepare(actor, case.pk, scenario.pk, rev(case))
        for work in works:
            assert_waiting(self, work)
        forecasts.review(actor, case, calculation)
        for work in works:
            finish_station(self, work, calculation)

    def test_f40_management_priority_hands_off_an_action_with_owner_and_deadline(self):
        actor, case = self.actor, self.case
        run = forecasts.run(actor, case)
        review = forecasts.review(actor, case, run)
        work = start_station(self, "F40", review)
        assert_waiting(self, work)
        proof = evidence(actor, case, "forecast_review", "Synthetic decision on the verified near-term forecast.")
        priority = forecast.prioritize(actor, case.pk, run.pk, "Finance", "forecast-item-owner", "Verify timing",
                                       actor.pk, timezone.now() + timedelta(days=1), proof.pk,
                                       "Assign this follow-up to its accountable owner.", rev(case))
        finish_station(self, work, priority.action.current)

    def test_f41_verified_actual_match_reaches_updated_forecast(self):
        actor, case = self.actor, self.case
        scenario = forecasts.scenario(actor, case)
        actual = forecasts.actual(actor, case)
        link = forecasts.match(actor, case, scenario, actual)
        work = start_station(self, "F41", link)
        assert_waiting(self, work)
        recalculated = forecast.prepare(actor, case.pk, scenario.pk, rev(case))
        forecasts.review(actor, case, recalculated)
        finish_station(self, work, recalculated)
        self.assertIn(link.pk, recalculated.manifest["matches"])

    def test_f42_new_horizon_requires_fresh_opening_and_new_human_review(self):
        actor, case = self.actor, self.case
        prior = timezone.localdate().replace(day=1) - timedelta(days=1)
        with patch("django.utils.timezone.localdate", return_value=prior):
            old = forecasts.run(actor, case)
            forecasts.review(actor, case, old)
        new = forecasts.payload(actor, case)
        new["items"] = []
        new["rollover"] = [{"key": item["key"], "disposition": "cancel", "reason": "Explicit synthetic cancellation."}
                           for item in old.scenario.payload["items"]]
        successor = forecasts.scenario(actor, case, new, parent=old)
        work = start_station(self, "F42", successor)
        result = forecast.prepare(actor, case.pk, successor.pk, rev(case))
        assert_waiting(self, work)
        forecasts.review(actor, case, result)
        finish_station(self, work, result)

    def test_f43_scoped_forecast_publication_has_exact_recipient_receipt(self):
        actor, case = self.actor, self.case
        run = forecasts.run(actor, case)
        forecasts.review(actor, case, run)
        template, recipient = forecasts.publication(actor, case)
        version = forecast_documents.draft(actor, case.pk, run.pk, template.pk, "management", rev(case))
        work = start_station(self, "F43", ForecastBinding.objects.get(version=version))
        with self.assertRaisesMessage(ValidationError, "specialist findings"):
            reserve_publication(actor, case.pk, version.pk, rev(case))
        assert_waiting(self, work)
        publication = reserve_publication(actor, case.pk, version.pk, rev(case))
        run_publication_once()
        receipt = PublicationReceipt.objects.get(publication=publication, recipient=recipient)
        finish_station(self, work, receipt)
        self.assertEqual(receipt.payload_sha256, version.payload_sha256)


class GroupForecastStation(TransactionTestCase):
    def test_f43_group_report_needs_its_own_disclosure_decision_and_recipient(self):
        from apps.finance import group_forecast
        from .test_group_forecast import configured

        actor, case, run, recipient, template, _, _ = configured()
        version = group_forecast.draft(actor, case.pk, run.pk, template.pk, rev(case))
        binding = ForecastBinding.objects.get(version=version)
        work = start_station(self, "F43", binding)
        assert_waiting(self, work)
        group_forecast.review(actor, case.pk, version.pk, "Finance", "approve",
                              "Reviewed selected group fields and the named recipient.", rev(case))
        delivery = reserve_publication(actor, case.pk, version.pk, rev(case))
        run_publication_once()
        receipt = PublicationReceipt.objects.get(publication=delivery, recipient=recipient)
        finish_station(self, work, receipt)
        projected = " ".join(publication_observation(binding, actor).lines.values())
        for field in ("PRIVATE_X", "RESTRICTED_X", "SECRET_X", "7391"):
            self.assertNotIn(field, projected)
