"""Native source-to-receiver bindings for monthly Finance and BU work.

The coordinator reads bounded projections. Finance retains all calculations,
adjustments, approvals, private payroll inputs and publication authority.
"""
import csv
from collections import Counter
from functools import partial
from io import StringIO

from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.models import Evidence
from apps.core.read_observation import read_observation
from apps.identity.services import require
from apps.policy.models import Configuration
from apps.policy.services import reference_values, resolve
from apps.workflows.native_station_contracts import Observation, ProjectionRevision, Route, SourceFact
from . import analysis, bu, performance
from .models import BUReceipt, FinanceAdjustment, FinancePeriod, FinanceRun, ImportValidation
from .coordinator_accounts_performance import PERFORMANCE_ROUTES
from .rules import decimal, number, total


NOTE_METRICS = {
    "F05": {"revenue", "direct_cost", "opex", "staff_cost"},
    "F06": {"asset"},
    "F08": {"liability"},
}
ALLOCATION_METRICS = {"F14": "revenue", "F15": "direct_cost", "F19": "staff_cost"}


def numbered(*lines):
    return {str(i): line for i, line in enumerate(lines, 1)}


def finance_access(actor, case):
    require(actor, case, "case.read")
    require(actor, case, "finance.read")


def current_mapping(runs, required_decision, subject_key):
    if required_decision["valid"]:
        for run in runs.order_by("-pk")[:10]:
            if run.result["status"] != "complete":
                continue
            if subject_key == "source":
                decision_ids = [run.snapshot["source_review"]["id"]]
            else:
                decision_ids = [a["review"]["id"] for a in run.snapshot["adjustments"]]
            if required_decision["id"] not in decision_ids:
                continue
            try:
                analysis.ensure_current(run)
            except ValidationError:
                continue
            return run
    return None


@read_observation
def import_observation(source, actor, *, detailed=False):
    case = source.case
    finance_access(actor, case)
    if detailed and not import_checks_enabled(source):
        raise PermissionDenied("This project has not authorised detailed trial-balance import checks.")
    require(source.actor, case, "finance.source")
    analysis.source_for(case, source.pk)
    if source.batch.source_sha256 != source.batch.evidence.sha256:
        raise ValidationError("The import does not match its recorded file.")
    receipt = None
    decision = analysis.current_review(case, "source", source=source)
    validation = ImportValidation.objects.filter(batch=source.batch).order_by("-pk").first()
    current_rules = False
    if validation and validation.policies:
        checks = {key: resolve(key, case) for key in validation.policies}
        current_rules = all(check.status == "ACTIVE" and check.configuration.pk == validation.policies[key]
                            for key, check in checks.items())
    validated = bool(current_rules and validation.status == "validated_source")
    if validated and decision["valid"]:
        receipt = current_mapping(
            FinanceRun.objects.filter(case=case, source=source, kind="mapping"), decision, "source"
        )
    lines = numbered(
        f"Controlled trial-balance import {source.batch_id} contains {len(source.batch.rows)} source rows.",
        f"Validation {validation.pk if validation else 'missing'} uses the current import rules: {validated}.",
        f"Source context {source.pk} declares {source.accounting_basis} accounting and {source.completeness} coverage.",
        f"The source declares a control total of {source.control_total if source.control_total is not None else 'unknown'}.",
        f"Extraction time {source.extracted_at.isoformat()}. Source digest {source.batch.source_sha256}.",
    )
    fact_handles = None
    if detailed:
        extra, fact_handles = _import_checks(source, validation, current_rules, validated)
        lines.update(extra)
    return Observation(case, source.batch.evidence, lines, receipt, fact_handles)


def import_checks_enabled(source):
    from apps.agents.specialist_memory import COMPONENT
    from apps.workflows.native_station_contracts import PROJECTION

    permission = resolve(COMPONENT, source.case)
    if permission.status != "ACTIVE":
        return source.case.synthetic and permission.status == "MISSING"
    value = permission.configuration.envelope["value"]
    return ("F02" in value["processes"] and PROJECTION in value["source_kinds"]
            and value.get("finance_import_checks", False))


IMPORT_VALIDATION = ProjectionRevision(
    2, import_checks_enabled, partial(import_observation, detailed=True), {
        "A01": "Check the supplied header, file inventory and native row findings. "
               "A resubmission requires an original comparison file.",
        "A03": "Compare the stated and computed source controls. Distinguish a discrepancy "
               "from an unknown value and cite the check you used.",
        "A05": "Explain the computed file total, its reporting currency and period and its comparison with "
               "the supplied control. Quote the actual amount in your summary if it is known and select the "
               "corresponding available fact names for the quantities you use. Assess the file "
               "check on its own evidence. Account mapping and conversions are later tasks.",
    },
)


def _import_checks(source, validation, current_rules, validated):
    from adapters.finance_inputs import COLUMNS

    rows = source.batch.rows
    header = next(csv.reader(StringIO(source.batch.evidence.body)), [])
    codes = Counter(issue.get("field") for issue in validation.findings) if current_rules else None
    findings = (", ".join(f"{key}={codes[key]}" for key in COLUMNS) if codes is not None
                else "unknown until the file has a current validation")
    # Only a successfully validated file establishes a homogeneous currency
    # and period. Never sum heterogeneous, missing or malformed amounts.
    currency, period, actual = "unknown", "unknown", None
    if validated and rows:
        currency, period = rows[0]["currency"], rows[0]["period"]
        actual = total(row["amount"] for row in rows)
    supplied = source.control_total
    compared = "unknown" if actual is None or supplied is None else (
        "matches" if actual == decimal(supplied) else "differs"
    )
    # No account names, per-account values, HR rows or internal file contents
    # leave the reader. These are checks on the one already selected import.
    lines = {
        "6": "Accepted input columns: " + (", ".join(COLUMNS) if header == COLUMNS else "unconfirmed") + ".",
        "7": f"Current native row findings by column: {findings}.",
        "8": f"Validated file currency: {currency}. Reporting period: {period}.",
        "9": f"Sum of validated amounts as stated in the file: {number(actual) if actual is not None else 'unknown'}. "
             f"Comparison with the source's declared control total: {compared}.",
        "10": "This source check precedes mapping, adjustments and unit conversion. It grants no posting authority.",
    }
    handles = {"import_reference": SourceFact("reference", "1", f"import {source.batch_id}")}
    if supplied is not None:
        handles["declared_total"] = SourceFact("total", "4", supplied)
    if validated and rows:
        handles["file_currency"] = SourceFact("currency", "8", currency)
        handles["file_period"] = SourceFact("period", "8", period)
    if actual is not None:
        handles["file_total"] = SourceFact("total", "9", number(actual))
    return lines, handles


@read_observation
def adjustment_observation(adjustment, actor):
    source = adjustment.source
    case = source.case
    finance_access(actor, case)
    require(adjustment.actor, case, "finance.adjust")
    analysis.source_for(case, source.pk)
    if FinanceAdjustment.objects.filter(source=source, reference=adjustment.reference, number__gt=adjustment.number).exists():
        raise ValidationError("Use the successor adjustment on this source.")
    decision = analysis.current_review(case, "adjustment", adjustment=adjustment)
    candidates = FinanceRun.objects.filter(
        case=case, source=source, kind="mapping", request__adjustment_ids__contains=[adjustment.pk]
    )
    receipt = current_mapping(candidates, decision, "adjustment")
    return Observation(case, adjustment.evidence, numbered(
        f"Reporting adjustment {adjustment.pk}, revision {adjustment.number}, belongs to source {source.pk}.",
        f"It contains {len(adjustment.lines)} {adjustment.kind} reporting lines.",
        f"Net movement across the selected adjustment lines is {number(total(line['amount'] for line in adjustment.lines))}.",
        "A reporting adjustment has no authority to post to the ledger.",
    ), receipt)


def note_outputs(process, run):
    """Select direct note formulas by their actual mapped input categories."""
    if run.kind != "formula":
        return {}
    trace = run.result.get("note_lineage") or {}
    if trace.get("implementation") != "finance-note-lineage/v1":
        return {}
    categories = {
        key: {row["metric"] for row in line["rows"]}
        for key, line in trace.get("report_lines", {}).items()
    }
    selected = {}
    for key, formula in trace.get("formulas", {}).items():
        terms = formula["operands"]
        if terms and all(
            term["kind"] == "line" and categories.get(term["key"])
            and categories[term["key"]] <= NOTE_METRICS[process]
            for term in terms
        ):
            selected[key] = formula
    return selected


def current_seal(candidates, *, required_bu_lines=None):
    for period in candidates.select_related("run").order_by("-pk")[:10]:
        if required_bu_lines and not allocation_consumed(period.run, required_bu_lines):
            continue
        if performance.period_acceptance(period)["current_head"] == period.pk:
            return period
    return None


def allocation_consumed(formula, required_lines):
    """A sealed company-only calculation cannot acknowledge a BU allocation."""
    by_bu = formula.result.get("by_bu", {})
    if not by_bu or not all(by_bu.values()):
        return False
    common = set.intersection(*(set(figures) for figures in by_bu.values()))
    formulas = formula.result.get("note_lineage", {}).get("formulas", {})
    consumed = set()
    seen = set()
    remaining = list(common)
    while remaining:
        key = remaining.pop()
        if key in seen:
            continue
        seen.add(key)
        for term in formulas.get(key, {}).get("operands", []):
            if term["kind"] == "line":
                consumed.add(term["key"])
            else:
                remaining.append(term["key"])
    return required_lines <= consumed


@read_observation
def note_observation(process, run, actor):
    finance_access(actor, run.case)
    analysis.ensure_current(run)
    outputs = note_outputs(process, run)
    if not outputs:
        raise ValidationError("No formula in this run consumes the selected note's account categories.")
    trace = run.result["note_lineage"]
    receipt = None
    if all(item["display_value"] is not None for item in outputs.values()):
        receipt = current_seal(FinancePeriod.objects.filter(case=run.case, run=run))
    lines = [
        f"Formula run {run.pk} uses mapping {trace['mapping_run']} for period {run.result['period']}.",
        f"Source sign convention {trace['source_sign_convention']}. Base unit {trace['source_unit']}.",
        f"There are {len(outputs)} formulas in the selected note. Their full calculation lineage is retained in Finance.",
    ]
    for key, item in list(sorted(outputs.items()))[:8]:
        lines.append(
            f"{key}: weighted numerator {item['weighted_numerator']}, divisor {item['divisor']}, "
            f"display {item['display_value']} {item['display_unit']}. Oracle evidence {item['oracle_evidence_id']}."
        )
    return Observation(run.case, run.source.batch.evidence, numbered(*lines), receipt)


def allocation_rows(process, run):
    if run.kind != "allocation":
        return []
    metric = ALLOCATION_METRICS[process]
    rows = [r for r in run.result.get("rows", []) if r.get("metric") == metric]
    if process == "F19":
        pools = {r["pool"] for r in rows if (r.get("basis") or {}).get("period_basis")}
        held = [r for r in rows if r["treatment"] == "pool" and not r.get("basis")]
        if held:
            # A missing denominator can prevent the allocation service from writing
            # its basis. Use the run's own rule version to identify that failed task.
            pin = run.snapshot["policies"].get("D07.allocation_pool_rules", {})
            config = Configuration.objects.filter(case=run.case, pk=pin.get("id")).first()
            if config:
                pools.update(r["pool"] for r in reference_values(config)
                             if r["method"] == "headcount_weighted" and r["metric"] == metric
                             and r["entity"] == run.result["entity"]
                             and r["from_period"] <= run.result["period"] <= r["to_period"])
        return [r for r in rows if r["treatment"] == "pool" and r["pool"] in pools]
    if process == "F14":
        return [r for r in rows if r["treatment"] in ("direct", "pool")]
    return [r for r in rows if r["treatment"] == "direct"]


@read_observation
def allocation_observation(process, run, actor):
    finance_access(actor, run.case)
    analysis.ensure_current(run)
    rows = allocation_rows(process, run)
    if not rows:
        raise ValidationError("The native allocation contains no rows for this process.")
    if process == "F19" and run.snapshot.get("hr_basis_access"):
        from .allocation import MEMBERSHIP
        from .hrfinance import allocation_basis
        from apps.policy.services import active_component

        reference = reference_values(active_component(MEMBERSHIP, run.case))[0]
        allocation_basis(actor, run.case, reference)
    metric = ALLOCATION_METRICS[process]
    conservation = run.result["conservation"][metric]
    receipt = None
    if conservation["conserved"] and all(r["status"] == "allocated" for r in rows):
        receipt = current_seal(FinancePeriod.objects.filter(case=run.case, run__parent=run),
                               required_bu_lines={r["report_line"] for r in rows})
    lines = [
        f"Allocation {run.pk} for {run.result['period']} used source mapping {run.parent_id}.",
        f"The selected {metric} population has {len(rows)} source rows and {len(run.result['bu_keys'])} business units.",
        f"The native conservation check for {metric} is {conservation['conserved']}.",
    ]
    if process == "F19":
        lines.append(f"{sum(r.get('denominator') is not None for r in rows)} selected rows have a declared denominator.")
    else:
        lines.append(f"The metric has allocated total {conservation['allocated']}, unallocated {conservation['unallocated']} and residual {conservation['residual']}.")
    return Observation(run.case, run.source.evidence, numbered(*lines), receipt)


@read_observation
def staff_observation(work, actor):
    from apps.policy.bu_validators import STAFF

    bu.private_access(actor, work)
    bu.current(work)
    _, rule = bu.config(STAFF, work.case, work.metadata["scope"])
    proof = Evidence.objects.get(case=work.case, kind="bu_pool_contract", pk=rule["pool_contract_evidence_id"])
    eligible = any(not row["exception"] for row in work.payload["rows"])
    receipt = None
    if eligible and work.payload["conserved"] and work.metadata["status"] == "complete":
        for candidate in BUReceipt.objects.filter(report__work=work).select_related("report", "actor").order_by("-pk")[:10]:
            require(candidate.actor, work.case, "bu.receive")
            bu.read_report(candidate.actor, candidate.report_id)
            receipt = candidate
            break
    return Observation(work.case, proof, numbered(
        f"Standard shared-service allocation {work.pk} applies to {work.metadata['scope']['period']}.",
        f"Configured standard method {rule['standard_method']}. Standard population present: {eligible}.",
        f"Conservation check: {work.payload['conserved']}. Employee identities and individual amounts stay in payroll.",
    ), receipt)


def author(subject):
    return subject.actor


def any_subject(subject):
    return True


def has_note(process, subject):
    return bool(note_outputs(process, subject))


def has_allocation(process, subject):
    return bool(allocation_rows(process, subject))


def has_standard_staff(work):
    return work.kind == "staff" and any(not row["exception"] for row in work.payload["rows"])


ROUTES = (
    Route("F02", "finance.FinanceSource", any_subject, author, import_observation, IMPORT_VALIDATION),
    Route("F04", "finance.FinanceAdjustment", any_subject, author, adjustment_observation),
    *(Route(pid, "finance.FinanceRun", partial(has_note, pid), author, partial(note_observation, pid)) for pid in NOTE_METRICS),
    *(Route(pid, "finance.FinanceRun", partial(has_allocation, pid), author, partial(allocation_observation, pid)) for pid in ALLOCATION_METRICS),
    Route("F20", "finance.BUWork", has_standard_staff, author, staff_observation),
    *PERFORMANCE_ROUTES,
)
