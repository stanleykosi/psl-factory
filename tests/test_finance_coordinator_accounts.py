"""Finance's 15 station receipts use real source, decision and receiving services."""
import copy
import json
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.core.services import add_evidence
from apps.documents import controlled, delivery
from apps.documents.models import PublicationReceipt
from apps.finance import analysis, bu, documents, performance, services
from apps.finance.coordinator_accounts import allocation_consumed, ROUTES
from apps.identity.models import Grant
from apps.policy.services import reference_values
from . import bu_helpers, finance_analysis_helpers as accounts, finance_performance_helpers as fiscal
from .helpers import rev
from .native_station_helpers import assert_waiting, finish_station, start_station


def finish_received(test, work, receiver):
    from apps.workflows.native_station_models import NativeStationUse

    receipt = finish_station(test, work, receiver)
    test.assertTrue(NativeStationUse.objects.filter(handoff=receipt.handoff, actor=work.actor).exists())


def finance_note(actor, case, template, metric, raw, coefficient, expected):
    rule = copy.deepcopy(template)
    rule.update(
        key=metric + "_note", scope="company_only", divisor="1000", output_unit="thousands_currency",
        terms=[{"kind": "line", "key": metric, "coefficient": coefficient, "value_stage": "base_value"}],
    )
    rule["oracles"] = [
        {"key": "known", "inputs": [{"kind": "line", "key": metric, "value": raw}], "expected": expected},
        {"key": "missing", "inputs": [{"kind": "line", "key": metric, "value": None}], "expected": None},
    ]
    oracle = add_evidence(actor, case.pk, "finance_oracle", json.dumps(rule["oracles"]), "synthetic:note-" + metric)
    rule["oracle_evidence_id"] = oracle.pk
    return rule


class FinanceCoordinatorAccountsTests(TransactionTestCase):
    def test_reviewed_import_adjustment_notes_and_allocations_enter_the_exact_period(self):
        actor, case, evidence, fixture, configs, _, _, outsider = accounts.fixture()
        review_note = evidence["finance_review"].pk
        owner_note = evidence["policy_decision"]
        maps = fixture["mapping"] + [dict(
            fixture["mapping"][-1], key="liability_line", report_line="liability",
            account="liability", metric="liability",
        )]
        mapping_rules = accounts.policy(actor, case, "D06.account_bu_maps", maps, owner_note)
        analysis.review(actor, case.pk, "mapping", mapping_rules.pk, "Finance", "approve",
                        review_note, "Reviewed selected accounts and their classifications.", rev(case))
        rules = reference_values(configs["D06.rule_oracle_refs"])
        methods = rules + [
            finance_note(actor, case, rules[0], "asset", "500", "1", "0.50"),
            finance_note(actor, case, rules[0], "liability", "-300", "-1", "0.30"),
        ]
        formulas = accounts.policy(actor, case, "D06.rule_oracle_refs", methods, owner_note)
        analysis.review(actor, case.pk, "formula", formulas.pk, "Finance", "approve", review_note,
                        "Reviewed sign conversion, source units and independent golden examples.", rev(case))
        file = add_evidence(actor, case.pk, "financial_input", fixture["csv"] + "liability,-300,NGN,2026-10\n",
                            "synthetic:controlled-extended-export")
        batch = services.capture_import(actor, case.pk, file.pk, rev(case))
        services.validate_import(actor, case.pk, batch.pk, rev(case))
        units = accounts.declared_units(actor, case, batch)
        source = analysis.capture_source(
            actor, case.pk, batch.pk, "synthetic-company", "accrual", timezone.now() - timedelta(hours=1),
            "complete", "-409.99", evidence["finance_source"].pk, rev(case),
            unit_declaration=units,
        )
        intake = start_station(self, "F02", source)
        assert_waiting(self, intake)
        analysis.review(actor, case.pk, "source", source.pk, "Finance", "approve", review_note,
                        "Source file, context and controlled totals verified.", rev(case))
        adjustment = analysis.adjustment(
            actor, case.pk, source.pk, "test-report-only", "additive", [{"account": "sales", "amount": "-1"}],
            evidence["finance_adjustment"].pk, "Correction to this report only.", rev(case),
        )
        correction = start_station(self, "F04", adjustment)
        assert_waiting(self, correction)
        analysis.review(actor, case.pk, "adjustment", adjustment.pk, "Finance", "approve", review_note,
                        "Reviewed this exact correction.", rev(case))
        mapping = analysis.map_source(actor, case.pk, source.pk, [adjustment.pk], rev(case))
        finish_received(self, intake, mapping)
        finish_received(self, correction, mapping)
        allocation = analysis.allocate(actor, case.pk, mapping.pk, accounts.METRICS, rev(case))
        allocation_work = [start_station(self, pid, allocation) for pid in ("F14", "F15", "F19")]
        formula = analysis.calculate(actor, case.pk, allocation.pk, rev(case))
        notes = [start_station(self, pid, formula) for pid in ("F05", "F06", "F08")]
        self.assertEqual(formula.result["company"]["asset_note"]["value"], "0.50")
        self.assertEqual(formula.result["company"]["liability_note"]["value"], "0.30")
        for work in allocation_work + notes:
            assert_waiting(self, work)
        analysis.review(actor, case.pk, "output", formula.pk, "Finance", "approve", review_note,
                        "Reviewed classifications, conservation, sign, scaling and control total.", rev(case))
        period = performance.seal_period(actor, case.pk, formula.pk, None, rev(case))
        for work in allocation_work + notes:
            finish_received(self, work, period)
        with self.assertRaises(PermissionDenied):
            next(r for r in ROUTES if r.process == "F06").observe(formula, outsider)

    def test_budget_and_year_to_date_comparisons_require_actual_audience_receipts(self):
        data = fiscal.fixture_performance()
        actor, case, evidence, fixture = data[:4]
        budget, template, recipient = data[9:12]
        budget_work = start_station(self, "F11", budget)
        with self.assertRaisesMessage(ValidationError, "specialist findings have not reached"):
            fiscal.build(data)
        assert_waiting(self, budget_work)
        comparison = fiscal.build(data)
        finish_received(self, budget_work, comparison)
        pids = ("F10", "F24", "F25", "F26")
        works = [start_station(self, pid, comparison) for pid in pids]
        for work in works:
            assert_waiting(self, work)
        projection = copy.deepcopy(fixture["projection"])
        projection["audiences"][0].update(columns=["actual", "budget", "variance", "prior", "ratio"], charts=True)
        accounts.policy(actor, case, "D10.audience_projection_rules", projection, evidence["policy_decision"])
        performance.decide(actor, case.pk, "performance", comparison.pk, "Finance", "approve",
                           evidence["finance_review"].pk, "Reviewed figures and exact chart projection.", rev(case))
        document = documents.draft_report(actor, case.pk, comparison.pk, template.pk, "internal", rev(case), performance=True)
        publication = controlled.reserve_publication(actor, case.pk, document.pk, rev(case))
        self.assertTrue(delivery.run_publication_once(case_id=case.pk, job_id=publication.job.pk))
        receipt = PublicationReceipt.objects.get(publication=publication, recipient=recipient)
        for work in works:
            finish_received(self, work, receipt)
        Grant.objects.filter(user=recipient, case=case, action="finance.read").update(active=False)
        with self.assertRaises((ValidationError, PermissionDenied)):
            next(r for r in ROUTES if r.process == "F26").observe(comparison, actor)

    def test_restatement_preserves_the_predecessor_and_requires_review_before_sealing(self):
        data = fiscal.fixture_performance()
        actor, case, evidence, _, fixture, _, _, source, original = data[:9]
        note = evidence["finance_review"].pk
        adjustment = analysis.adjustment(actor, case.pk, source.pk, "correction", "additive",
                                         [{"account": "sales", "amount": "-1"}], evidence["finance_adjustment"].pk,
                                         "Reviewed revision to the company reporting source.", rev(case))
        analysis.review(actor, case.pk, "adjustment", adjustment.pk, "Finance", "approve", note, "Reviewed.", rev(case))
        mapping = analysis.map_source(actor, case.pk, source.pk, [adjustment.pk], rev(case))
        split = analysis.allocate(actor, case.pk, mapping.pk, accounts.METRICS, rev(case))
        revised = analysis.calculate(actor, case.pk, split.pk, rev(case))
        analysis.review(actor, case.pk, "output", revised.pk, "Finance", "approve", note, "Reviewed.", rev(case))
        proof = add_evidence(actor, case.pk, "finance_restatement", "Synthetic restatement request.", "synthetic:rework")
        request = performance.request_restatement(actor, case.pk, original.pk, revised.pk, proof.pk,
                                                  "Retain prior scope and original figures.", rev(case))
        work = start_station(self, "F27", request)
        assert_waiting(self, work)
        with self.assertRaises(ValidationError):
            performance.seal_period(actor, case.pk, revised.pk, request.pk, rev(case))
        accounts.policy(actor, case, "D10.restatement_rule_id", fixture["restatement"], evidence["policy_decision"])
        performance.decide(actor, case.pk, "restatement", request.pk, "Finance", "approve", note,
                           "Authorise a distinct historical successor.", rev(case))
        successor = performance.seal_period(actor, case.pk, revised.pk, request.pk, rev(case))
        self.assertEqual(successor.predecessor_id, original.pk)
        finish_received(self, work, successor)

    def test_standard_staff_allocation_waits_for_its_named_aggregate_recipient(self):
        data = bu_helpers.fixture()
        case = data["case"]
        staff = bu_helpers.staff(data)
        work = start_station(self, "F20", staff)
        assert_waiting(self, work)
        route = next(r for r in ROUTES if r.process == "F20")
        initial = route.observe(staff, data["preparer"])
        self.assertNotIn("E900", str(initial.lines))
        self.assertNotIn("E002", str(initial.lines))
        with self.assertRaises(PermissionDenied):
            route.observe(staff, data["manager"])
        report = bu_helpers.publish(data, staff)
        self.assertIsNone(route.observe(staff, data["preparer"]).receipt)
        receipt = bu.receive(data["manager"], case.pk, report.pk, rev(case))
        finish_received(self, work, receipt)


class FinanceCoordinatorAudienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.data = fiscal.fixture_performance()

    def test_actuals_only_receipt_cannot_substitute_for_budget_variance_or_chart_delivery(self):
        actor, case, evidence = self.data[:3]
        report = fiscal.build(self.data)
        performance.decide(actor, case.pk, "performance", report.pk, "Finance", "approve",
                           evidence["finance_review"].pk, "Reviewed the comparison.", rev(case))
        version = documents.draft_report(actor, case.pk, report.pk, self.data[10].pk, "internal",
                                         rev(case), performance=True)
        publication = controlled.reserve_publication(actor, case.pk, version.pk, rev(case))
        self.assertTrue(delivery.run_publication_once(case_id=case.pk, job_id=publication.job.pk))
        receipt = PublicationReceipt.objects.get(publication=publication)
        by_id = {r.process: r for r in ROUTES}
        self.assertEqual(by_id["F24"].observe(report, actor).receipt, receipt)
        for pid in ("F10", "F25", "F26"):
            with self.subTest(process=pid):
                self.assertIsNone(by_id[pid].observe(report, actor).receipt)

    def test_income_and_asset_lineage_cannot_supply_a_missing_liability_note(self):
        run = self.data[8].run
        by_id = {r.process: r for r in ROUTES}
        self.assertTrue(by_id["F05"].matches(run))
        self.assertTrue(by_id["F06"].matches(run))
        self.assertFalse(by_id["F08"].matches(run))
        with self.assertRaises(ValidationError):
            by_id["F08"].observe(run, self.data[0])
        self.assertEqual(by_id["F05"].observe(run, self.data[0]).receipt, self.data[8])
        self.assertTrue(allocation_consumed(run, {"revenue", "staff_cost", "direct_cost"}))
        self.assertFalse(allocation_consumed(run, {"asset"}))
