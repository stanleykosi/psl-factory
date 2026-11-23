"""Issue-owner evidence, closure logs and change classification."""
from django.core.exceptions import ValidationError

from apps.identity.services import require
from apps.policy.services import decision_authority
from apps.workflows.native_station_contracts import Observation, Route
from . import change_execution, changes, issue_access, issue_references
from .coordinator_delivery import author, check, lines
from .models import ChangeAuthorization


def referenced(observation, actor):
    issue = observation.issue
    case = issue.case
    issue_references.check_observation(actor, case, observation)
    if issue_references.source_superseded(observation):
        raise ValidationError("The owning system supplied a newer observation.")
    revision = issue_references.head(issue)
    receipt = None
    if revision:
        report = issue_references.report(actor, issue)
        linked = any(row.get("observation_id") == observation.pk and row["currentness"] == "current"
                     for row in report["references"])
        if linked and observation.availability == "available":
            receipt = revision
    facts = [f"Source-owned {observation.contract.kind} reference on issue {issue.pk}.",
        f"Source availability: {observation.availability}. Permitted fields present: {len(observation.fields)}.",
        f"Owner source observed at {observation.observed_at.isoformat()}.",
        "Confirmed links are recorded by the issue owner. No external record is modified."]
    for key in ("status", "severity", "opened_at", "resolved_at"):
        if key in observation.contract.allowed_fields and key in observation.fields:
            value = observation.fields[key]
            facts.append(f"Source-reported {key}: {value[:200] if value else 'unknown'}.")
    return Observation(case, observation.evidence, lines(*facts), receipt)


def issue_closure(state, actor):
    issue = state.issue
    case = issue.case
    check(actor, case, "issue.read")
    if not issue_access.state_public(state):
        raise ValidationError("The issue evidence requires its source-owned reader.")
    receipt = None
    closed = issue.states.filter(number=state.number + 1, status="Closed").first()
    if closed and issue.current_id == closed.pk and issue_access.state_public(closed):
        entries = list(state.closure_entries.all())
        if {entry.role for entry in entries} == {"QA", "PM"}:
            for entry in entries:
                require(entry.actor, case, "issue.close_log")
                decision_authority(entry.actor, case, entry.role)
                issue_access.issue_subject(case, entry.evidence_id)
            receipt = closed
    return Observation(case, state.evidence, lines(f"Issue resolution version {state.number}, severity {state.severity or 'unknown'}.",
        f"Root cause evidence {'present' if state.root_cause_id else 'not recorded'}.",
        f"Resolved at {state.resolved_at.isoformat() if state.resolved_at else 'unknown'}.",
        "Closure requires the QA and project-manager log entries for this resolution."), receipt)


def classified(version, actor):
    case = version.change.case
    check(actor, case, "change.read")
    changes.current_change(case, version.pk)
    if version.category == "Emergency":
        receipt = version.emergency_profiles.order_by("-pk").first()
        if receipt:
            from .emergencies import profile_for
            profile_for(case, receipt.pk)
    else:
        receipt = version.assessments.order_by("pk").first()
        if receipt:
            require(receipt.actor, case, "change.assess:" + receipt.contributor)
    return Observation(case, version.evidence, lines(f"Change version {version.number} was classified {version.category}.",
        f"Affected module: {version.module}. Requested change excerpt: {version.description[:400]}",
        f"Incident source {'present' if version.incident_id else 'not recorded'}.",
        "Only the matching emergency intake or ordinary impact assessment can receive the change."), receipt)


def approved_change(version, actor):
    case = version.change.case
    check(actor, case, "change.read")
    receipt = ChangeAuthorization.objects.filter(version=version).order_by("-pk").first()
    if receipt:
        change_execution.validate_authorization(case, receipt)
    else:
        changes.current_change(case, version.pk)
    return Observation(case, version.evidence, lines(f"Approval subject is change revision {version.number} ({version.category}).",
        f"Reason given for the change: {version.reason[:400]}",
        "Current assessments determine the decision roles and conditional costing requirement.",
        "A project plan update must use the exact human-approved authorization."), receipt)


ROUTES = [
    Route("P51", "pmo.IssueReferenceObservation", lambda r: r.contract.kind == "risk", author, referenced),
    Route("P54", "pmo.IssueState", lambda r: r.status == "Resolved" and r.kind.casefold() == "production", author, issue_closure),
    Route("P55", "pmo.IssueReferenceObservation", lambda r: r.contract.kind == "incident", author, referenced),
    Route("P56", "pmo.ChangeVersion", lambda r: True, author, classified),
    Route("P58", "pmo.ChangeVersion", lambda r: r.category in ("Normal", "Standard"), author, approved_change),
]
