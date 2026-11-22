"""Cash forecasting stations over the existing assumption, review and receipt records."""

from functools import partial

from django.core.exceptions import ValidationError
from django.db.models import Q

from adapters.forecast import scenario as parse_scenario
from apps.documents.controlled import current_version, publication_requirements, validate_review
from apps.documents.models import Publication, PublicationReceipt
from apps.identity.services import require
from apps.workflows.native_station_contracts import Observation, Route
from . import documents, forecast, forecast_documents
from .models import ForecastMatch, ForecastPriority, ForecastRun, ForecastScenario


def numbered(*lines):
    return {str(i): line for i, line in enumerate(lines, 1)}


def current_scenario(subject, actor):
    require(actor, subject.case, "case.read")
    require(actor, subject.case, "finance.read")
    require(subject.actor, subject.case, "finance.forecast.capture")
    if parse_scenario(subject.evidence.body) != subject.payload:
        raise ValidationError("Forecast inputs no longer match the exact captured evidence.")
    if ForecastScenario.objects.filter(case=subject.case, reference=subject.reference, number__gt=subject.number).exists():
        raise ValidationError("A newer revision of this scenario exists.")


def approved_calculation(scenario, *, match_id=None):
    runs = ForecastRun.objects.filter(scenario=scenario)
    if match_id is not None:
        runs = runs.filter(manifest__matches__contains=[match_id])
    run = runs.order_by("-pk").first()
    if run:
        review = run.forecastreview_set.order_by("-pk").first()
        if review and review.verdict == "approve":
            forecast.approved(run)
            return run
    return None


def receive_forecast_sources(run, actor):
    from apps.workflows.native_stations import receive_advice

    for process in ("F36", "F37", "F38"):
        receive_advice(process, run.scenario, actor, case=run.case)
    if run.scenario.parent_id:
        receive_advice("F42", run.scenario, actor, case=run.case)
    matches = ForecastMatch.objects.filter(
        pk__in=run.manifest["matches"], case=run.case, root=forecast.root_of(run.scenario),
        item_key__in=[item["key"] for item in run.result["items"]], reversal__isnull=True,
    )
    for match in matches.iterator(chunk_size=100):
        receive_advice("F41", match, actor, case=run.case)


def assumption(subject, actor, *, kind):
    current_scenario(subject, actor)
    value = subject.payload
    period = f"Scenario revision {subject.number}, as of {value['as_of']}, currency {value['currency']}."
    if kind == "opening":
        openings = value["openings"]
        dates = [row["observed_on"] for row in openings]
        lines = numbered(period,
            f"Declared accounts {len(value['coverage']['accounts'])}; evidenced opening balances {len(openings)}.",
            f"Opening source dates range from {min(dates)} to {max(dates)}." if dates else "No opening dates were supplied.",
            f"Opening accounts with unknown amounts {sum(row['amount'] is None for row in openings)}.",
        )
    elif kind == "rollover":
        if not subject.parent or subject.root_id != forecast.root_of(subject.parent.scenario).pk:
            raise ValidationError("A roll-forward needs its original forecast and reviewed prior calculation.")
        forecast.approved(subject.parent, current=False)
        lines = numbered(period,
            f"Reviewed prior calculation {subject.parent_id}; new horizon begins {value['months'][0]}.",
            f"Unresolved prior items with dispositions {len(value['rollover'])}; carried items {len(value['items'])}.",
        )
    else:
        chosen = [row for row in value["items"] if forecast.direction(row) == kind]
        postponed = sum(bool(row["expected_on"] and row["original_due"] and row["expected_on"] > row["original_due"])
                        for row in chosen)
        lines = numbered(period,
            f"{kind.capitalize()} coverage {value['coverage'][kind + 's']}; selected assumptions {len(chosen)}.",
            f"Missing amounts {sum(row['amount'] is None for row in chosen)}; missing expected dates {sum(not row['expected_on'] for row in chosen)}.",
            f"Recorded source omissions {len(value['coverage']['omissions'])}.",
            f"Expected later than the original due date {postponed}; separately cited evidence records {len({row['evidence_id'] for row in chosen})}.",
        )
    return Observation(subject.case, subject.evidence, lines, approved_calculation(subject))


def priority(review, actor):
    run = review.run
    current_scenario(run.scenario, actor)
    if forecast.approved(run).pk != review.pk:
        raise ValidationError("A newer forecast decision supersedes this priority request.")
    binding = ForecastPriority.objects.filter(review=review).select_related("action__current").order_by("pk").first()
    assignment = None
    if binding:
        assignment = binding.action.states.get(number=1)
        if assignment.item.case_id != run.case_id or not assignment.owner_id or not assignment.due_at:
            raise ValidationError("The priority must bind its original owner, deadline and project.")
        require(assignment.actor, run.case, "finance.forecast.prioritize")
        require(assignment.owner, run.case, "action.own")
        current = forecast.review_authority(assignment.actor, run.case, "forecast_priority",
                                            binding.authority["finance_review_rule"]["role"], "approve", run.actor_id)
        if not forecast.review_authority_matches(current, binding.authority):
            raise ValidationError("The authority for this forecast priority has changed.")
    return Observation(run.case, review.evidence, numbered(
        f"Finance reviewed forecast revision {run.scenario.number} for {run.result['as_of']}.",
        f"{len(run.result['periods'])} forecast periods, reported coverage status {run.result['status']}.",
        "The receiving step assigns an accountable follow-up owner and deadline.",
    ), assignment)


def matched_actual(match, actor):
    require(actor, match.case, "case.read")
    require(actor, match.case, "finance.read")
    require(match.actor, match.case, "finance.forecast.match")
    if not forecast.active_matches().filter(pk=match.pk).exists() or not forecast.actual_available(match.actual):
        raise ValidationError("The match or verified actual has been reversed.")
    # A sibling scenario in the same case can reference the same cash ledger. Only the
    # same root and actual item may be used as the receiving updated forecast.
    scenario = ForecastScenario.objects.filter(
        Q(pk=match.root_id) | Q(root_id=match.root_id), case=match.case,
        reference=match.root.reference,
    ).order_by("-number").first()
    receiving = approved_calculation(scenario, match_id=match.pk) if scenario else None
    if receiving and (
        match.pk not in receiving.manifest["matches"]
        or not any(row["key"] == match.item_key for row in receiving.result["items"])
    ):
        receiving = None
    return Observation(match.case, match.evidence, numbered(
        f"Matched actual direction {match.actual.payload['direction']}; currency {match.actual.payload['currency']}.",
        f"Original forecast {match.root_id}, verified actual {match.actual_id}, recorded match {match.pk}.",
        "The downstream calculation reconciles the remaining forecast item and its actual amount.",
    ), receiving)


def publication(binding, actor):
    run, version = binding.run, binding.version
    current_scenario(run.scenario, actor)
    if version.document.case_id != run.case_id or forecast_documents.report_inputs(run, version.audience) != binding.snapshot:
        raise ValidationError("The declared audience must match the reviewed forecast projection.")
    current_version(run.case, version.pk)
    issued = Publication.objects.filter(version=version).first()
    receipt = None
    if issued and issued.job.status == "confirmed":
        review = validate_review(run.case, version)
        policies, recipients, retention = publication_requirements(run.case, version)
        if (issued.policies, issued.recipient_ids, issued.retention_days, issued.review_id) != (
            policies, recipients, retention, review.pk if review else None,
        ):
            raise ValidationError("The confirmed forecast delivery differs from the current audience decision.")
        documents.sender(issued.actor, version)
        if version.audience == "group":
            from .group_forecast import verified
            verified(version)
        receipts = list(PublicationReceipt.objects.filter(publication=issued).order_by("pk"))
        if (not receipts or sorted(r.recipient_id for r in receipts) != sorted(recipients)
            or any(r.payload_sha256 != version.payload_sha256 or r.payload != version.payload for r in receipts)):
            raise ValidationError("Every named recipient needs the reviewed forecast bytes.")
        receipt = receipts[0]
    # The group draft uses its own approved aggregate view. No internal detail or amounts
    # are exposed through this station, regardless of which audience was selected.
    return Observation(run.case, run.scenario.evidence, numbered(
        f"Document version {version.number}, selected audience {version.audience}.",
        f"Source forecast revision {run.scenario.number}, as of {run.result['as_of']}.",
        "Every approved recipient must have an exact publication receipt.",
    ), receipt)


def always(_row):
    return True


def author(row):
    return row.actor


ROUTES = (
    Route("F36", "finance.ForecastScenario", always, author, partial(assumption, kind="inflow")),
    Route("F37", "finance.ForecastScenario", always, author, partial(assumption, kind="outflow")),
    Route("F38", "finance.ForecastScenario", always, author, partial(assumption, kind="opening")),
    Route("F40", "finance.ForecastReview", lambda row: row.verdict == "approve", author, priority),
    Route("F41", "finance.ForecastMatch", always, author, matched_actual),
    Route("F42", "finance.ForecastScenario", lambda row: row.parent_id is not None, author,
          partial(assumption, kind="rollover")),
    Route("F43", "finance.ForecastBinding", always, lambda row: row.version.created_by, publication),
)
