"""Controlled templates, publication and AF13 owner acceptance."""
from django.core.exceptions import PermissionDenied, ValidationError

from apps.core.evidence_access import public_evidence
from apps.documents import controlled, template_access, template_current, validation
from apps.documents.contracts import PMO_DOCUMENT_TYPES
from apps.documents.models import ValidationPackage, Version
from apps.identity.services import require
from apps.workflows.native_station_contracts import Observation, Route
from . import leadership_reporting, reporting
from .coordinator_commercial import version_receipt
from .coordinator_delivery import author, check, creator, lines
from .models import MinutesReportBinding


def template_allowed(template):
    return template.definition.get("document_type") in PMO_DOCUMENT_TYPES


def read_version(actor, version):
    case = version.document.case
    check(actor, case, "document.read")
    if not template_access.visible_templates(actor, case, candidate_ids=[version.template_id]).exists():
        raise PermissionDenied("This template or its source is outside the current reader's scope.")
    leadership_reporting.binding_access(actor, version)
    binding = MinutesReportBinding.objects.filter(version=version).first()
    if binding and binding.report_id:
        reporting.report_source_access(actor, case, binding.manifest)
    if version.document.current_id != version.pk:
        raise ValidationError("This document has a newer version.")
    controlled.current_version(case, version.pk)


def document_source(version):
    case = version.document.case
    pinned = {row["id"]: row for row in version.source_manifest}
    for source in public_evidence(case.evidence.filter(pk__in=pinned)).order_by("pk"):
        if pinned[source.pk]["sha256"] == source.sha256 and pinned[source.pk]["version"] == source.version:
            return source
    # A source-free template or private native document can still supply its
    # schema and revision as scoped evidence. No document body is projected.
    if version.template.case_id != case.pk:
        raise ValidationError("The document refers to a template from a different project.")
    return version.template.evidence


def document_lines(version):
    return lines(f"{version.template.definition['document_type']} document version {version.number}.",
                 f"Audience {version.audience}; template version {version.template.version}.",
                 f"The version declares {len(version.source_manifest)} source records.",
                 f"The reviewed document digest is {version.payload_sha256}.")


def document_station(version, actor):
    read_version(actor, version)
    return Observation(version.document.case, document_source(version), document_lines(version), version_receipt(version))


def period_report(binding, actor):
    version = binding.version
    read_version(actor, version)
    report = binding.report
    facts = document_lines(version)
    facts.update({"5": f"Period from {report.start_at.date()} to {report.end_at.date()}.",
                  "6": f"Reporting purpose: {report.kind}."})
    return Observation(report.case, document_source(version), facts, version_receipt(version))


def selected_template(scope, actor):
    template_access.require_scope(actor, scope)
    current = template_current.status(scope)
    result = None
    if current["status"] == "CURRENT":
        manifest = current["manifest"]
        result = Version.objects.filter(document__case=scope.case, audience=scope.audience,
            template_id=manifest["template_id"], template_current_manifest=manifest).order_by("-pk").first()
        if result:
            read_version(actor, result)
    return Observation(scope.case, scope.evidence,
            lines(f"Scope for {scope.document_type}, audience {scope.audience}.",
                  "An application of this template must pin the exact current scope and owner's selection."), result)


def governed_template(template, actor):
    from apps.documents.models import TemplateClaim
    if not template_access.visible_templates(actor, template.case, candidate_ids=[template.pk]).exists():
        raise PermissionDenied("Current access to the template's source is required.")
    claims = TemplateClaim.objects.filter(template=template, retraction__isnull=True).select_related("scope").order_by("-pk")
    receipt = None
    for claim in claims[:20]:
        template_access.require_scope(actor, claim.scope)
        current = template_current.status(claim.scope)
        if current["status"] == "CURRENT" and current["manifest"]["template_id"] == template.pk:
            manifest = current["manifest"]
            if manifest["resolution_id"]:
                receipt = claim.scope.resolutions.get(pk=manifest["resolution_id"])
            elif manifest["owner_claim_id"] == claim.pk:
                receipt = claim
            if receipt:
                break
    return Observation(template.case, template.evidence, lines(f"Registered template revision {template.version}.",
            f"Document type {template.definition['document_type']}.",
            f"The template specifies {len(template.definition['required_fields'])} required sections."), receipt)


def sop(source, actor):
    case = source.case
    check(actor, case, "validation.read")
    validation.source_current(source)
    packages = ValidationPackage.objects.filter(case=case, payload__process_ids__contains=["P13"],
            payload__source_ids__contains=[source.pk]).order_by("-pk")
    receipt = None
    for package in packages[:20]:
        validation._private_access(actor, package)
        if validation.latest_review(package, "meaning"):
            receipt = validation.approved_review(package, "meaning")
            break
    clauses = [entry for entry in source.metadata['clauses'] if "P13" in entry["process_ids"]]
    facts = [f"Controlled source revision {source.version}.", f"{len(clauses)} recorded clauses concern PMO procedure.",
             "Owner validation is required before those clauses are used as approved procedure."]
    for entry in clauses[:8]:
        facts.append(f"Procedure excerpt at {entry['locator'][:180]}: {entry['quote'][:450]}")
    return Observation(case, source.evidence, lines(*facts), receipt)


def package_acceptance(package, actor):
    check(actor, package.case, "validation.read")
    validation._private_access(actor, package)
    validation.package_current(package)
    receipt = validation.approved_review(package, "acceptance") if validation.latest_review(package, "acceptance") else None
    return Observation(package.case, package.evidence, lines(f"Validation package revision {package.version}.",
            f"The selected level is {package.payload['level']}.",
            f"Owner review covers {len(package.payload['process_ids'])} selected processes and {len(package.payload['example_ids'])} examples."), receipt)


ROUTES = [
    Route("P04", "pmo.MinutesReportBinding", lambda r: r.report_id is not None, lambda r: r.version.created_by, period_report),
    Route("P10", "documents.TemplateScope", lambda r: r.document_type in PMO_DOCUMENT_TYPES, author, selected_template),
    Route("P11", "documents.Template", template_allowed, creator, governed_template),
    Route("P13", "documents.DiscoverySource", lambda r: r.metadata.get("document_kind") == "pmo_sop"
          and "P13" in r.metadata.get("process_ids", []), author, sop),
    Route("P15", "documents.ValidationPackage", lambda r: "P15" in r.payload.get("process_ids", []), author, package_acceptance),
    Route("P52", "documents.Version", lambda r: template_allowed(r.template), creator, document_station),
    Route("P53", "documents.Version", lambda r: r.audience == "client" and template_allowed(r.template), creator, document_station),
]
