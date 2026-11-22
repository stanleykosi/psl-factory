"""Finance's receiving ends for usage, service coverage, cash and private handoffs."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.documents.contracts import digest
from apps.identity.services import require
from apps.workflows.models import Outbox
from apps.workflows.native_station_contracts import Observation, Route
from . import contract_coverage as coverage
from . import hrfinance, receivables, recognition, usage_intake
from . import models
from .coordinator_operations_cash import ROUTES as FORECAST_ROUTES


def numbered(*lines):
    return {str(i): line for i, line in enumerate(lines, 1)}


def usage(source, actor):
    usage_intake.access(actor, source.case)
    usage_intake.current(source)
    state = usage_intake.inspect(source)
    acceptance = models.UsageIntakeAcceptance.objects.filter(source=source).first()
    if acceptance:
        if acceptance.receipt.source_id != source.pk or acceptance.receipt.duplicate_of_id:
            raise ValidationError("The pricing handoff must use the original received source.")
        partition = acceptance.partitions.order_by("pk").first()
        if not partition:
            raise ValidationError("The accepted usage report has no Finance partition.")
        # Checks the *entire* partition set against the collective source and control totals.
        usage_intake.origin(partition)
    return Observation(source.case, source.evidence, numbered(
        f"Usage report period {source.period}, source version {source.version}.",
        f"Declared usage rows {len(source.payload['rows'])}; expected population entries {len(source.controls['population'])}.",
        f"Control reconciliation {state['status']}; outstanding findings {len(state['findings'])}.",
        f"Unquantified rows {sum(row['quantity'] is None for row in source.payload['rows'])}; declared completeness {source.payload['completeness']}.",
    ), acceptance)


def register(terms, actor):
    coverage.terms_access(actor, terms)
    assessment = models.CoverageAssessment.objects.filter(terms=terms).order_by("-pk").first()
    if assessment:
        try:
            require(assessment.actor, terms.case, "coverage.assess")
            coverage.current_assessment(assessment.actor, assessment)
            if actor.pk != assessment.actor_id:
                coverage.current_assessment(actor, assessment)
        except (ValidationError, PermissionDenied):
            # Changed invoice coverage requires a new assessment. Keep the
            # schedule source available so the new reviewer can produce it.
            assessment = None
    return Observation(terms.case, terms.evidence, numbered(
        f"Terms revision {terms.version} links register revision {terms.register.version} to contract revision {terms.contract.version}.",
        f"Register cadence {terms.register.payload['cadence']}; contract cadence {terms.contract.payload['cadence']}.",
        f"Declared contract billing intervals {len(terms.contract.payload['schedule'])}.",
    ), assessment)


def service_obligation(request, actor):
    route = coverage.preparation_route(request)
    assessment = route["assessment"]
    terms = assessment.terms
    coverage.terms_access(actor, terms)
    coverage.current_assessment(actor, assessment)
    if route["state"] != "ready":
        raise ValidationError("Finance cancelled this preparation route.")
    matches = [r for r in assessment.result["obligations"] if r["key"] == request.obligation_key]
    if len(matches) != 1:
        raise ValidationError("The assessment does not identify the requested service interval.")
    interval = matches[0]
    receipt = models.CoveragePreparationReceipt.objects.filter(request=request).first()
    if receipt:
        coverage.receipt_identity(receipt)
        if receipt.actor_id != route["recipient"].pk or receipt.payload["assessment_id"] != assessment.pk:
            raise ValidationError("The recorded receipt belongs to a previous preparation route.")
        coverage.terms_access(receipt.actor, terms, "receive")
        require(receipt.actor, terms.case, "finance.billing.prepare")
    return Observation(terms.case, terms.evidence, numbered(
        f"Service obligation assessed on {assessment.as_of}, bill date {interval['bill_on']}.",
        f"Register cadence {terms.register.payload['cadence']}; assessed status {interval['status']}.",
        "The receiving step is Finance preparation. Invoice issuance has a separate approval.",
    ), receipt)


def receivable(receipt, actor):
    case = receipt.case
    require(actor, case, "finance.read")
    require(actor, case, "finance.receivables")
    require(receipt.actor, case, "finance.cash.record")
    snapshot = models.ReceivableSnapshot.objects.filter(
        case=case, as_of=timezone.localdate(), manifest__reported_receipts__contains=[receipt.pk],
    ).order_by("-pk").first()
    if snapshot:
        try:
            require(snapshot.actor, case, "finance.receivables")
            require(snapshot.actor, case, "finance.read")
        except PermissionDenied:
            snapshot = None
    if snapshot:
        manifest, result = receivables.calculate(case, snapshot.as_of)
        if snapshot.sha256 != digest({"manifest": manifest, "result": result}):
            snapshot = None
    return Observation(case, receipt.evidence, numbered(
        f"Reported cash currency {receipt.payload['currency']}, amount basis {receipt.payload['amount_basis']}.",
        f"Reported amount supplied: {receipt.payload['amount'] is not None}.",
        "Verification, allocation and overdue status are independently tracked in the receiving position.",
    ), snapshot)


def receive_position_sources(actor, case, receipt_ids):
    from django.db.models import Exists, OuterRef
    from apps.workflows.native_station_models import NativeStation, NativeStationAdvice
    from apps.workflows.native_stations import receive_advice

    # Legacy cases can have years of cash records. Only exact station subjects
    # present in this position take part in its handoff. A cash report is
    # immutable; its original consumed and verified handoff stays historical.
    acknowledged = NativeStationAdvice.objects.filter(
        station_id=OuterRef("pk"), nativestationuse__isnull=False,
        receipt__receiver_model="finance.receivablesnapshot",
    )
    for offset in range(0, len(receipt_ids), 250):
        selected = [str(pk) for pk in receipt_ids[offset:offset + 250]]
        stations = NativeStation.objects.filter(
            ~Exists(acknowledged), process="F32", subject_model="finance.cashreceipt", subject_pk__in=selected,
        )
        if case.synthetic:
            stations = stations.filter(work__isnull=False)
        subjects = stations.values_list("subject_pk", flat=True)
        for receipt in models.CashReceipt.objects.filter(case=case, pk__in=[int(pk) for pk in subjects]):
            receive_advice("F32", receipt, actor, case=case)


def progress(packet, actor):
    require(actor, packet.case, "recognition.read")
    require(packet.actor, packet.case, "recognition.prepare")
    recognition.packet_current(packet)
    latest = packet.records.filter(kind="review").order_by("-pk").first()
    disposition = None
    if latest and latest.payload["intent"]["verdict"] == "reviewed":
        try:
            recognition.record_current(latest)
            received = packet.records.get(kind="receive", pk=latest.payload["snapshot"]["receipt_id"])
            requested = packet.records.get(kind="request", pk=received.payload["snapshot"]["request_id"])
            require(received.actor, packet.case, "recognition.receive")
            require(requested.actor, packet.case, "recognition.request")
            recognition.record_current(requested)
            recognition.record_current(received)
        except (ValidationError, PermissionDenied):
            pass  # A replaced attestation or disposition must go through Finance again.
        else:
            disposition = latest
    return Observation(packet.case, packet.evidence, numbered(
        f"Progress packet version {packet.version} is dated {packet.payload['as_of']}.",
        f"Evidence categories: {', '.join(sorted({v['category'] for v in packet.payload['facts']}))}.",
        f"Milestones referenced {len(packet.payload['milestone_ids'])}; open evidence findings {len(recognition.findings(packet))}.",
    ), disposition)


def milestone(source, actor):
    from apps.pmo.signature_exemptions import assert_current_baseline_assurance

    case = source.case
    require(actor, case, "case.read")
    if actor.pk != source.completed_by_id:
        require(actor, case, "finance.read")
    require(source.completed_by, case, "milestone.complete")
    assert_current_baseline_assurance(case)
    key = f"milestone:{source.pk}:finance:v1"
    expected = {"milestone_id": source.pk, "name": source.name, "evidence_id": source.evidence_id,
                "evidence_sha256": source.evidence.sha256}
    job = Outbox.objects.get(case=case, milestone=source, operation_key=key, actor=source.completed_by)
    if job.payload != expected:
        raise ValidationError("The notification does not identify the recorded milestone evidence.")
    accepted = None
    if job.status == "confirmed":
        accepted = models.Handoff.objects.get(case=case, milestone=source, operation_key=key)
        if str(accepted.pk) != job.receipt or accepted.payload != expected:
            raise ValidationError("The Finance inbox receipt differs from the milestone notification.")
    return Observation(case, source.evidence, numbered(
        f"Milestone {source.name} records completion against evidence version {source.evidence.version}.",
        f"Completion date {source.completed_at.date()}; Finance notification reserves the same evidence digest.",
    ), accepted)


def private_disclosure(contract, actor):
    from .hrfinance_recipient import recipient_scope
    with recipient_scope(actor, contract.need.case, contract.payload["recipient_ids"]):
        return _private_disclosure(contract, actor)


def _private_disclosure(contract, actor):
    case = contract.need.case
    for action in ("case.read", "hrfinance.read", "hrfinance.snapshot.read", "hrfinance.receive"):
        require(actor, case, action)
    if actor.pk not in contract.payload["recipient_ids"]:
        raise PermissionDenied("The named Finance recipient is required.")
    hrfinance.authority(actor, case, "receive")
    hrfinance.current_contract(contract)
    # Finance may track its own pending request. Once HR decides, every read
    # must honour the current decision, even before the very first capture.
    if contract.records.filter(kind__in=("approve", "return", "revoke")).exists():
        hrfinance.authorized(contract)
    # Fetch only snapshot identity. The native currentness check projects two metadata fields.
    snapshot = contract.snapshots.defer("payload").filter(status="accepted").order_by("-pk").first()
    receipt = None
    if snapshot:
        hrfinance.snapshot_access(actor, snapshot)
        receipt = contract.records.filter(kind="receipt", snapshot=snapshot, actor=actor).first()
        if receipt and (receipt.authority != hrfinance.authority(actor, case, "receive")
                        or receipt.payload != {"sha256": snapshot.sha256, "receipt_only": True, "hr_write": False}):
            raise ValidationError("The read-only Finance receipt differs from the approved disclosure.")
    return Observation(case, contract.evidence, numbered(
        f"Finance requested reporting period {contract.need.payload['period']}, request revision {contract.need.version}.",
        "The source contract requires HR authorisation and an exact Finance recipient. Staff rows and pay fields remain private.",
    ), receipt)


def disclosure_recipient(contract):
    from django.contrib.auth import get_user_model

    nominated = contract.payload["recipient_ids"]
    if contract.need.actor_id in nominated:
        return contract.need.actor
    if len(nominated) == 1:
        return get_user_model().objects.filter(pk=nominated[0], is_active=True).first()
    # Ambiguous recipients cannot be assigned by user ordering. A named receipt
    # establishes a real recipient without granting the requester access to HR.
    record = contract.records.filter(kind="receipt", actor_id__in=nominated).order_by("pk").first()
    return record.actor if record else None


def always(_row):
    return True


def author(row):
    return row.actor


ROUTES = (
    Route("F28", "finance.UsageIntakeSource", always, author, usage),
    Route("F31", "finance.CoveragePreparationRequest", always, author, service_obligation),
    Route("F32", "finance.CashReceipt", always, author, receivable),
    Route("F33", "finance.ProgressPacket", always, author, progress),
    Route("F34", "pmo.Milestone", always, lambda row: row.completed_by, milestone),
    Route("F35", "finance.HRDisclosure", always, disclosure_recipient, private_disclosure),
    Route("F45", "finance.CoverageTerms", always, author, register),
    *FORECAST_ROUTES,
)
