from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.utils import timezone

from apps.core.services import add_evidence
from apps.finance import analysis, services
from apps.finance.coordinator_accounts import import_observation
from apps.identity.models import Grant
from tests import finance_analysis_helpers as accounts
from tests.helpers import rev
from tests.native_station_helpers import assert_waiting, configure_station, finish_station


class FinanceImportProjectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor, cls.case, cls.proof, _, cls.policies, cls.source, _, _ = accounts.fixture(review=False)

    def test_only_aggregate_validation_evidence_from_this_import_reaches_the_reader(self):
        lines = import_observation(self.source, self.actor, detailed=True).lines
        self.assertIn("account, amount, currency, period", lines["6"])
        self.assertIn("account=0, amount=0, currency=0, period=0", lines["7"])
        self.assertIn("NGN", lines["8"])
        self.assertIn("2026-10", lines["8"])
        self.assertIn("-109.99", lines["9"])
        self.assertIn("matches", lines["9"])
        self.assertNotIn("staff_pool", str(lines))
        self.assertNotIn("-1000", str(lines))
        outsider = get_user_model().objects.create_user("unapproved-finance-reader")
        Grant.objects.create(case=self.case, user=outsider, action="case.read")
        with self.assertRaises(PermissionDenied):
            import_observation(self.source, outsider, detailed=True)

    def test_fact_handles_bind_exact_value_and_line_and_reject_invented_references(self):
        from apps.agents.specialist_memory import validate_output
        from apps.workflows.native_station_contracts import SourceFact

        reading = import_observation(self.source, self.actor, detailed=True)
        answer = {"summary": "The supplied control reconciles.", "assessment": "supported", "gaps": [],
                  "quotes": ["1"], "facts": ["file_currency", "file_period", "file_total"]}
        citations, anchors, _ = validate_output(answer, reading.lines, fact_handles=reading.fact_handles)
        self.assertEqual(citations, ["1", "8", "9"])
        actual = [(anchor["field"], anchor["line"], reading.lines[anchor["line"]][anchor["start"]:anchor["end"]])
                  for anchor in anchors]
        self.assertEqual(actual, [("currency", "8", "NGN"), ("period", "8", "2026-10"), ("total", "9", "-109.99")])
        bound_citations, _, _ = validate_output({**answer, "quotes": []}, reading.lines, fact_handles=reading.fact_handles)
        self.assertEqual(bound_citations, ["8", "9"])
        for override in ({"facts": ["invented_total"]}, {"quotes": ["999"]}, {"facts": ["file_total", "file_total"]},
                         {"facts": [{"field": "total", "line": "9", "value": "999"}]}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                validate_output({**answer, **override}, reading.lines, fact_handles=reading.fact_handles)
        for invalid in (SourceFact("total", "999", "-109.99"), SourceFact("total", "9", "1234")):
            with self.assertRaises(ValidationError):
                validate_output({**answer, "facts": ["file_total"]}, reading.lines, fact_handles={"file_total": invalid})
        with self.assertRaises(ValidationError):
            validate_output({**answer, "quotes": ["8"], "facts": [{"field": "period", "line": "8", "value": "2026-10"}]},
                            reading.lines)

    def test_incomplete_or_stale_validation_preserves_unknowns(self):
        c, a = self.case, self.actor
        raw = "account,amount,currency,period\nPRIVATE-SOURCE-ACCOUNT,,NGN,2026-10\n"
        document = add_evidence(a, c.pk, "financial_input", raw, "synthetic:incomplete")
        batch = services.capture_import(a, c.pk, document.pk, rev(c))
        services.validate_import(a, c.pk, batch.pk, rev(c))
        source = analysis.capture_source(a, c.pk, batch.pk, "synthetic-company", "accrual",
                                         timezone.now()-timedelta(hours=1), "partial", None,
                                         self.proof["finance_source"].pk, rev(c))
        lines = import_observation(source, a, detailed=True).lines
        self.assertIn("amount=1", lines["7"])
        self.assertIn("unknown", lines["8"])
        self.assertIn("file: unknown.", lines["9"])
        self.assertNotIn("PRIVATE-SOURCE-ACCOUNT", str(lines))
        from apps.policy.services import transition
        transition(a, self.policies["D06.unit_sign_currency_period"].pk, "revoked")
        stale = import_observation(self.source, a, detailed=True).lines
        self.assertIn("unknown", stale["7"])
        self.assertIn("file: unknown.", stale["9"])

    def test_mixed_currency_or_period_never_yields_a_computed_total(self):
        c, a = self.case, self.actor
        raw = ("account,amount,currency,period\n"
               "alpha,100,NGN,2026-10\nbeta,-10,USD,2026-09\n")
        document = add_evidence(a, c.pk, "financial_input", raw, "synthetic:mixed")
        batch = services.capture_import(a, c.pk, document.pk, rev(c))
        services.validate_import(a, c.pk, batch.pk, rev(c))
        source = analysis.capture_source(a, c.pk, batch.pk, "synthetic-company", "accrual",
                                         timezone.now()-timedelta(hours=1), "partial", "90",
                                         self.proof["finance_source"].pk, rev(c))
        lines = import_observation(source, a, detailed=True).lines
        self.assertIn("currency=1, period=1", lines["7"])
        self.assertIn("currency: unknown", lines["8"])
        self.assertIn("control total: unknown.", lines["9"])

    def source_rule(self, actor, case, proof, checked=None):
        from apps.agents.specialist_memory import COMPONENT
        from apps.policy.project_use import ProjectUseForm
        from apps.policy.services import transition
        value = {"model": "station-test", "roles": ["A01", "A03", "A05"], "processes": ["F02"],
                 "source_kinds": ["native_station_projection"], "effective": timezone.now().isoformat(),
                 "proof": proof.pk}
        if checked is not None:
            value["finance_import_checks"] = checked
        form = ProjectUseForm(actor, case, COMPONENT, value)
        self.assertTrue(form.is_valid(), form.errors)
        result = form.save(actor)
        transition(actor, result.pk, "validated")
        transition(actor, result.pk, "active")
        return result

    def test_existing_enrollment_keeps_old_projection_even_before_reading(self):
        from apps.workflows import native_stations
        from apps.workflows.native_station_models import NativeStation
        from apps.agents.specialist_models import SpecialistReading
        self.source_rule(self.actor, self.case, self.proof["policy_decision"])
        station = configure_station(self, "F02", self.source)
        work = native_stations.enroll(station.pk)
        self.assertFalse(SpecialistReading.objects.filter(work=work).exists())
        self.source_rule(self.actor, self.case, self.proof["policy_decision"], True)
        self.assertEqual(work.native_station.projection_version, 1)
        self.assertEqual(len(native_stations.checked_work(work, self.actor).lines), 5)
        with self.assertRaises(DatabaseError), transaction.atomic():
            NativeStation.objects.filter(pk=station.pk).update(projection_version=2)
        assert_waiting(self, work)
        for component, purpose in analysis.PURPOSE.items():
            analysis.review(self.actor, self.case.pk, purpose, self.policies[component].pk, "Finance", "approve",
                            self.proof["finance_review"].pk, "Verified this exact mapping contract.", rev(self.case))
        analysis.review(self.actor, self.case.pk, "source", self.source.pk, "Finance", "approve",
                        self.proof["finance_review"].pk, "Verified the source file.", rev(self.case))
        mapping = analysis.map_source(self.actor, self.case.pk, self.source.pk, [], rev(self.case))
        finish_station(self, work, mapping)
        current = native_stations.checked_work(work, self.actor)
        self.assertEqual(len(current.lines), 5)
        self.assertIsNotNone(native_stations.current_receipt(work, current))

    def test_operational_projection_needs_opt_in_and_stops_on_withdrawal(self):
        from apps.agents.specialist_memory import COMPONENT
        from apps.finance.coordinator_accounts import import_checks_enabled
        from apps.policy.project_use import ProjectUseForm
        from apps.policy.services import transition
        a, case, proof, _, _, source, _, _ = accounts.fixture(
            username="operational-import-owner", recipient_username="operational-import-recipient", review=False, synthetic=False,
        )
        self.assertFalse(import_checks_enabled(source))
        self.source_rule(a, case, proof["policy_decision"])
        with self.assertRaises(PermissionDenied):
            import_observation(source, a, detailed=True)
        rule = self.source_rule(a, case, proof["policy_decision"], True)
        self.assertIn("NGN", import_observation(source, a, detailed=True).lines["8"])
        transition(a, rule.pk, "revoked")
        with self.assertRaises(PermissionDenied):
            import_observation(source, a, detailed=True)
        form = ProjectUseForm(a, case, COMPONENT, {
            "model": "station-test", "roles": ["A04", "A07"], "processes": ["P02"],
            "source_kinds": ["native_station_projection"], "effective": timezone.now().isoformat(),
            "proof": proof["policy_decision"].pk, "finance_import_checks": True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("finance_import_checks", form.errors)
