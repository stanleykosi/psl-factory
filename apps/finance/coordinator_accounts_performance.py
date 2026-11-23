"""Evidence and receipts for budgets, sealed period inventories and performance reports."""
from functools import partial

from django.core.exceptions import ValidationError

from apps.core.models import Evidence
from apps.core.read_observation import observed_fact, read_observation
from apps.documents import controlled
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.services import require
from apps.workflows.native_station_contracts import Observation, Route
from . import documents, performance
from .models import FinancePerformance, FinancePeriod


def author(row):
    return row.actor


def finance_read(actor, case):
    require(actor, case, "case.read")
    require(actor, case, "finance.read")


def lines(*items):
    return {str(n): text for n, text in enumerate(items, 1)}


@read_observation
def budget_observation(budget, actor):
    case = budget.case
    finance_read(actor, case)
    require(budget.actor, case, "finance.budget")
    if type(budget).objects.filter(case=case, reference=budget.reference, number__gt=budget.number).exists():
        raise ValidationError("This budget has a newer revision.")
    receipt = None
    decision = performance.current_decision(case, "budget", budget=budget)
    if decision["valid"]:
        reports = FinancePerformance.objects.filter(case=case, request__budget_id=budget.pk).order_by("-pk")
        for report in reports[:10]:
            if (
                report.result["status"] == "complete" and report.result["budget_version"] == budget.number
                and report.snapshot["budget_review"]["id"] == decision["id"]
            ):
                performance.ensure_current(report)
                receipt = report
                break
    return Observation(case, budget.evidence, lines(
        f"Budget {budget.pk}, revision {budget.number}, records {len(budget.rows)} input rows.",
        f"Cadence {budget.cadence}. Coverage {budget.completeness}. Accounting basis {budget.accounting_basis or 'unknown'}.",
        f"Original approval source {budget.approval_evidence_id}. Native budget findings {len(budget.findings)}.",
    ), receipt)


@observed_fact
def income_columns(report):
    """Follow each selected month's formula operands back to classified account lines."""
    shared = None
    periods = FinancePeriod.objects.filter(case=report.case, pk__in=report.request["period_ids"])
    for trace in periods.values_list("manifest__result__note_lineage", flat=True):
        if not trace:
            return set()
        incomes = {
            key for key, detail in trace.get("report_lines", {}).items() if detail["rows"] and
            all(row["metric"] in ("revenue", "direct_cost", "staff_cost", "opex") for row in detail["rows"])
        }
        eligible = set()
        formulas = trace.get("formulas", {})
        # Source-validated formula graphs have at most 30 dependency levels.
        for _ in range(31):
            newer = {
                key for key, formula in formulas.items()
                if formula["operands"] and all(
                    term["key"] in (incomes if term["kind"] == "line" else eligible)
                    for term in formula["operands"]
                )
            }
            if newer == eligible:
                break
            eligible = newer
        shared = eligible if shared is None else shared & eligible
    return (shared or set()) & report.result["company"].keys()


def projection_covers(report, process, projection):
    columns = set(projection.get("columns", ["actual"]))
    if not projection["formula_keys"]:
        return False
    if process == "F10":
        return (
            projection["include_company"] and {"actual", "budget", "variance"} <= columns
            and bool(income_columns(report).intersection(projection["formula_keys"]))
        )
    if process == "F24":
        return bool(projection["bu_keys"]) and "actual" in columns
    if process == "F25":
        return bool(projection["bu_keys"]) and {"actual", "budget"} <= columns
    return bool(projection["bu_keys"] and projection.get("charts")) and "actual" in columns


def published(report, process):
    deliveries = Publication.objects.filter(
        version__financeperformancebinding__run=report, job__status="confirmed"
    ).select_related("version__financeperformancebinding").order_by("-pk")
    for publication in deliveries[:10]:
        version = publication.version
        binding = version.financeperformancebinding
        if not projection_covers(report, process, binding.snapshot["projection"]):
            continue
        controlled.current_version(report.case, version.pk)
        documents.sender(publication.actor, version)
        review = controlled.validate_review(report.case, version)
        policies, recipients, retention = controlled.publication_requirements(report.case, version)
        if (policies, recipients, retention, getattr(review, "pk", None)) != (
            publication.policies, publication.recipient_ids, publication.retention_days, publication.review_id
        ):
            continue
        receipts = list(PublicationReceipt.objects.filter(publication=publication).order_by("recipient_id"))
        if (
            receipts and [r.recipient_id for r in receipts] == recipients
            and all(r.payload_sha256 == version.payload_sha256 and r.payload == version.payload for r in receipts)
        ):
            return receipts[0]
    return None


@read_observation
def performance_observation(process, report, actor):
    case = report.case
    finance_read(actor, case)
    performance.ensure_current(report)
    result = report.result
    source = Evidence.objects.get(case=case, pk=result["method"]["oracle_evidence_id"], kind="finance_oracle")
    receipt = published(report, process) if result["status"] == "complete" else None
    if process == "F10":
        data = lines(
            f"Company comparison {report.pk} for {result['cutoff']} uses {len(result['actual_manifest'])} sealed periods.",
            f"Income metrics traceable in every selected seal: {len(income_columns(report))}. Compared budget revision {result['budget_version']}.",
            f"Declared variance and ratio method {result['method']['ratio']}. Findings {len(result['findings'])}.",
        )
    elif process == "F24":
        data = lines(
            f"Year-to-date calculation {report.pk} covers {len(result['by_bu'])} business units through {result['cutoff']}.",
            f"Expected months: {', '.join(result['included_periods'])}.",
            f"Included period seals: {', '.join(str(row['id']) for row in result['actual_manifest'])}.",
        )
    elif process == "F25":
        data = lines(
            f"Business-unit budget comparison {report.pk} covers {len(result['included_periods'])} months.",
            f"Budget {result['budget_id']}, revision {result['budget_version']}, uses {result['budget_method']}.",
            f"The reviewed fiscal method is recorded at configuration {report.snapshot['method']}.",
        )
    else:
        data = lines(
            f"Performance calculation {report.pk} for {result['year_key']} through {result['cutoff']}.",
            f"There are {len(result['chart'])} chart data points and {len(result['by_bu'])} business units.",
            f"Ratio method {result['method']['ratio']}. Native findings {len(result['findings'])}.",
        )
    return Observation(case, source, data, receipt)


@read_observation
def restatement_observation(request, actor):
    case = request.case
    finance_read(actor, case)
    require(request.actor, case, "finance.restatement")
    period = FinancePeriod.objects.filter(
        case=case, restatement=request, predecessor=request.original, run=request.proposed
    ).first()
    if period:
        if performance.period_acceptance(period)["current_head"] != period.pk:
            raise ValidationError("This replacement period has a later successor.")
    return Observation(case, request.evidence, lines(
        f"Historical replacement request {request.pk} concerns sealed period {request.original_id}.",
        f"Proposed run {request.proposed_id}. Affected performance reports {len(request.impact['performance_ids'])}.",
        f"Original business-unit count {len(request.impact['old_bu_keys'])}. Proposed count {len(request.impact['new_bu_keys'])}.",
        "The original seal and its reviewed figures remain in the historical record.",
    ), period)


def has_performance_input(process, report):
    result = report.result
    if process == "F10":
        return bool(result["company"] and result["budget_id"] and result["actual_manifest"] and income_columns(report))
    if process == "F24":
        return bool(result["by_bu"] and result["actual_manifest"])
    if process == "F25":
        return bool(result["by_bu"] and result["budget_id"])
    return any(row["scope"] != "company" for row in result["chart"])


PERFORMANCE_ROUTES = (
    Route("F11", "finance.FinanceBudget", lambda row: True, author, budget_observation),
    Route("F27", "finance.FinanceRestatement", lambda row: True, author, restatement_observation),
    *(Route(pid, "finance.FinancePerformance", partial(has_performance_input, pid), author,
            partial(performance_observation, pid)) for pid in ("F10", "F24", "F25", "F26")),
)
