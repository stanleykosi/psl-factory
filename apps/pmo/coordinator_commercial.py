"""Costing, controlled submission and handovers follow immutable business references."""
from django.core.exceptions import ValidationError

from apps.documents.contracts import digest
from apps.documents.models import PublicationReceipt
from apps.finance.models import Handoff, SignedBaselineIntake
from apps.identity.services import require
from apps.workflows.models import Outbox
from apps.workflows.native_station_contracts import Observation, Route
from . import approvals, commercial, rfp, signatures
from .coordinator_delivery import author, check, lines
from .models import ApprovalRouteReceipt, BaselineAdoption, CommercialDocumentBinding


def version_receipt(version):
    """All intended recipients must have readback of the same bytes."""
    from apps.documents.models import Publication
    from apps.documents.controlled import validate_review

    pub = Publication.objects.filter(version=version, job__status="confirmed").first()
    if not pub:
        return None
    validate_review(version.document.case, version)
    originals = list(PublicationReceipt.objects.filter(publication=pub).order_by("recipient_id"))
    if (not originals or set(pub.recipient_ids) != {r.recipient_id for r in originals}
            or any(r.payload_sha256 != version.payload_sha256 or digest(r.payload) != r.payload_sha256 for r in originals)):
        raise ValidationError("Delivery receipts do not match the intended recipients and reviewed version.")
    return originals[0]


def check_submission_revision(revision):
    """An actual adoption can close this transaction before the coordinator polls it."""
    case = revision.dossier.case
    adoption = BaselineAdoption.objects.filter(revision=revision).first()
    if adoption is None:
        commercial.current_revision(case, revision.pk)
        return
    baseline, use = signatures.baseline_use(case)
    signatures.current_baseline_documents(case, baseline, use)
    if use.adoption_id != adoption.pk or use.packet.revision_id != revision.pk:
        raise ValidationError("A later adoption superseded the submitted revision.")


def current_submission(binding):
    revision = binding.revision
    check_submission_revision(revision)
    return (binding.version.document.current_id == binding.version_id and
            not commercial.terminal(revision) and binding.decision_ids == commercial.valid_approvals(revision))


def commercial_packet(revision, actor):
    case = revision.dossier.case
    check(actor, case, "commercial.read")
    check_submission_revision(revision)
    binding = CommercialDocumentBinding.objects.filter(revision=revision).order_by("-pk").first()
    if binding and not current_submission(binding):
        binding = None
    facts = lines(f"Commercial revision {revision.number}.",
                  f"Plan source {revision.sources['plan']} and costing source {revision.sources['costing']}.",
                  f"Prior revision: {revision.previous_id or 'initial'}.",
                  f"Documented reason for this revision: {revision.reason[:500]}",
                  "The client document must carry the ordered decisions for this revision.")
    return Observation(case, revision.context, facts, binding)


def shared_submission(binding, actor):
    case, version = binding.revision.dossier.case, binding.version
    check(actor, case, "commercial.read", "document.read")
    if not current_submission(binding):
        raise ValidationError("The current statement must match the approved costing revision.")
    return Observation(case, binding.revision.context,
        lines(f"Statement version {version.number} uses costing revision {binding.revision.number}.",
              f"The statement pins {len(binding.decision_ids)} commercial approvals.", f"Audience: {version.audience}."),
        version_receipt(version))


def client_response(publication_receipt, actor):
    from .models import ClientResponse

    version = publication_receipt.publication.version
    binding = CommercialDocumentBinding.objects.get(version=version)
    case = version.document.case
    check(actor, case, "commercial.read", "document.read")
    if not version_receipt(version) or not current_submission(binding):
        raise ValidationError("Current approved statement and confirmed original publication required.")
    response = ClientResponse.objects.filter(revision=binding.revision, receipt=publication_receipt).order_by("-pk").first()
    if response:
        require(response.actor, case, "commercial.response")
    return Observation(case, binding.revision.context, lines(f"Submitted statement version {version.number}.",
            f"Publication receipt {publication_receipt.pk} proves delivery to its named recipient.",
            "The client response must cite this same receipt and proposal."), response)


def signed_finance(packet, actor):
    case = packet.case
    check(actor, case, "commercial.read")
    if actor.pk != packet.actor_id:
        require(actor,case,"finance.read")
    signatures.validate_packet_policy(packet)
    from .models import CommercialSignatureUse
    use = CommercialSignatureUse.objects.filter(packet=packet, adoption__isnull=False).first()
    receipt = None
    if use and signatures.assert_current_signed_baseline(case).pk == packet.pk:
        baseline, current_use = signatures.baseline_use(case)
        if current_use.pk == use.pk:
            row = SignedBaselineIntake.objects.filter(case=case, adoption_id=use.adoption_id).first()
            pins = {k: {"id": getattr(baseline,k).pk, "sha256": getattr(baseline,k).sha256} for k in ("plan", "sow", "signed")}
            if (row and row.payload.get("adoption_id") == use.adoption_id and row.payload.get("sources") == pins
                    and row.payload.get("signature_packet", {}).get("id") == packet.pk):
                receipt = row
    proof = case.evidence.get(pk=packet.signatures["sow"]["evidence_id"])
    return Observation(case, proof, lines(f"Signature packet {packet.pk} binds a statement of work and requirements.",
            "Finance must receive the plan, statement and signed evidence for this adoption."), receipt)


def milestone(row, actor):
    case = row.case
    check(actor, case)
    if actor.pk != row.completed_by_id:
        require(actor,case,"finance.read")
    require(row.completed_by, case, "milestone.complete")
    job = Outbox.objects.filter(case=case, milestone=row).first()
    receipt = Handoff.objects.filter(case=case, milestone=row).first()
    if receipt and (not job or receipt.payload != job.payload or receipt.operation_key != job.operation_key):
        raise ValidationError("Finance received a different milestone handoff.")
    return Observation(case, row.evidence, lines(f"PMO completed milestone {row.pk} ({row.name}) on {row.completed_at.date()}.",
            "Finance receives the completion for billing review. Payment and invoice issuance remain separate."), receipt)


def approval_request(row, actor):
    approvals.readable(actor, row.case)
    approvals.current_request(row)
    receipt = ApprovalRouteReceipt.objects.filter(job__request=row, job__purpose="request", job__status="confirmed").order_by("-pk").first()
    if receipt:
        from .approval_routing import intent
        job = receipt.job
        expected = intent(job.actor, row, job.purpose, job.intent.get("factory_execution", {}).get("work"))
        if (expected != job.intent or receipt.payload != expected["public"] or receipt.recipient_id != expected["recipient"]
                or receipt.operation_key != job.operation_key):
            raise ValidationError("The routed original and its department recipient no longer match.")
    return Observation(row.case, row.evidence, lines(f"Department request {row.pk} of kind {row.kind}, version {row.version}.",
            f"The request concerns release candidate {row.candidate_id}.", "A routing receipt grants no approval."), receipt)


def bid_intake(intake, actor):
    root = intake.rfp
    check(actor, root.case, "rfp.read")
    require(intake.actor, root.case, "rfp.intake")
    if root.current_intake_id != intake.pk:
        raise ValidationError("This bid intake has a successor.")
    assigned = rfp.current_assignment(root, metadata_only=True) if intake.assignments.exists() else None
    return Observation(root.case, intake.evidence, lines(f"Bid intake revision {intake.number}.",
            f"Received {intake.received_at.isoformat()}. Deadline status: {intake.deadline_status}.",
            f"Recorded deadline: {intake.deadline_at.isoformat() if intake.deadline_at else 'unknown'}.",
            "The receiving assignment must identify an active project manager."), assigned)


def is_statement_receipt(row):
    return CommercialDocumentBinding.objects.filter(version_id=row.publication.version_id).exists()


def cost_revision(row):
    if not row.previous_id or row.context.kind == "rfp_response":
        return False
    return row.sources["costing"] != row.previous.sources["costing"]


ROUTES = [
    Route("P01", "pmo.CommercialDocumentBinding", lambda row: True, lambda row: row.version.created_by, shared_submission),
    Route("P02", "pmo.ApprovalRequest", lambda row: True, author, approval_request),
    Route("P08", "pmo.CommercialRevision", cost_revision, author, commercial_packet),
    Route("P09", "pmo.CommercialRevision", lambda row: row.context.kind != "rfp_response", author, commercial_packet),
    Route("P12", "pmo.Milestone", lambda row: True, lambda row: row.completed_by, milestone),
    Route("P19", "documents.PublicationReceipt", is_statement_receipt, lambda row: row.publication.version.created_by, client_response),
    Route("P20", "pmo.CommercialSignaturePacket", lambda row: row.revision_id is not None, author, signed_finance),
    Route("P45", "pmo.RFPIntake", lambda row: True, author, bid_intake),
]
