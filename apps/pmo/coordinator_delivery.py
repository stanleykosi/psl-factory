"""Planning and delivery readings backed by the project's own cumulative gate records."""
from functools import partial

from django.core.exceptions import ValidationError
from django.db.models import F

from apps.identity.services import require
from apps.workflows.native_station_contracts import Observation, Route
from . import delivery, delivery_closure, planning
from .models import DeliveryDossier, DeliveryDocumentBinding, DeliveryRecord


def author(row):
    return row.actor


def creator(row):
    return row.created_by


def lines(*facts):
    return {str(index): fact for index, fact in enumerate(facts, 1)}


def check(actor, case, *permissions):
    require(actor, case, "case.read")
    for permission in permissions:
        require(actor, case, permission)


def planning_packet(source):
    return source.kind == planning.KINDS["packet"] and source.source == "psl:planning-v1"


def planning_station(process, source, actor):
    case = source.case
    planning.readable(actor, case)
    _, packet = planning.packet(case, source.pk)
    payload = packet["payload"]
    ready = planning.latest(case, "ready")
    receipt = None
    if ready and planning.read(case, ready, "ready", "prepare").get("packet_id") == source.pk:
        current = planning.current_readiness(case, ready.pk)
        # A reader of a planning packet cannot use the preparer's department visibility.
        planning.requests(case, source, actor)
        if payload.get("collect_department_inputs"):
            from .planning_inputs import required
            required(case, source, actor)
        if current["packet_sha256"] == source.sha256:
            receipt = ready
    if process == "P17":
        facts = [f"Requirements source {payload['prd_id']}; scope source {payload['scope_id']}.",
                 f"Stakeholders cover {', '.join(sorted(row['team'] for row in payload['stakeholders']))}.",
                 f"Planning recorded {len(payload['questions'])} scope questions."]
    elif process == "P18":
        facts = [f"Engineering estimate source {payload['engineering_estimate_id']}.",
                 f"Security estimate source {payload['security_estimate_id']}.",
                 "The referenced owners supply estimates; approval is a separate department decision."]
    elif process == "P21":
        facts = [f"Both PRD walkthrough and scope/estimate alignment must use planning packet {source.pk}.",
                 f"The packet references {len(payload['questions'])} alignment questions."]
    else:
        facts = [f"Scope baseline source {payload['scope_id']}.",
                 f"Estimate source references {payload['engineering_estimate_id']} and {payload['security_estimate_id']}.",
                 "Readiness requires separate accepted department observations on this packet."]
    if process in ("P17", "P21"):
        for item in payload["questions"][:8]:
            facts.append(f"Question {item['key']} ({item['state']}) — {item['detail'][:350]}")
    if process in ("P18", "P25"):
        for item in payload.get("source_correlations", [])[:8]:
            facts.append(f"Declared {item['source_field']} version {item['document_version'] or 'unknown'} "
                         f"has correlation {item['state']} to requirements {item['target_prd_id']}.")
    return Observation(case, source, lines(*facts), receipt)


def planning_gate(source, actor):
    dossier = delivery.dossier_for(source.dossier.case, source.dossier_id)
    case = dossier.case
    check(actor, case, "delivery.read")
    require(source.actor, case, "delivery.source")
    decision = delivery.latest(dossier, "planning_decision", False)
    receipt = None
    if decision and decision.data.get("verdict") == "approve":
        plan = delivery.approved_plan(dossier)
        pin = plan.snapshot["sources"].get(source.kind)
        if pin and pin[0] == source.pk:
            receipt = plan
    facts = [f"Delivery candidate {dossier.candidate_id}.", f"Recorded design or test source: {source.kind}.",
             f"Owning team: {delivery.SOURCE_OWNERS[source.kind]}.",
             f"Original evidence version {source.evidence.version}."]
    if source.kind == "ui_applicability":
        facts.append(f"UI required: {source.payload['requires_ui']}. Client sign-off required: {source.payload['client_signoff_required']}.")
    return Observation(case, source.evidence, lines(*facts), receipt)


def release_gate(gate, actor):
    case = gate.candidate.case
    check(actor, case, "delivery.read")
    require(gate.created_by, case, "pmo.gate_record")
    dossier = DeliveryDossier.objects.filter(case=case, candidate_id=gate.candidate_id).first()
    receipt = None
    if dossier:
        delivery.dossier_for(case, dossier.pk)
        request = delivery.latest(dossier, "glpi_request", False)
        if request and any(pin[0] == gate.pk for pin in request.snapshot["gates"]):
            require(request.actor, case, "delivery.release_request")
            ready = delivery.latest(dossier, "release_ready", False)
            if (ready and ready.snapshot.get("request_id") == request.pk
                    and ready.snapshot == delivery.readiness_inputs(dossier)):
                receipt = ready
    return Observation(case, gate.evidence, lines(f"Candidate {gate.candidate_id}; gate {gate.kind}.",
                       f"The source owner is {gate.source_owner}.",
                       "The receiving readiness packet must pin the original deployment request and this verified gate."), receipt)


def meeting_station(meeting, actor):
    case = meeting.meeting.case
    check(actor, case, "meeting.read", "delivery.read")
    require(meeting.created_by, case, "meeting.record")
    if meeting.meeting.current_id != meeting.pk:
        raise ValidationError("The recorded meeting has a successor.")
    receipt = None
    if meeting.kind == "kickoff":
        row = DeliveryRecord.objects.filter(dossier__case=case, kind="kickoff", data__meeting_id=meeting.pk).order_by("-pk").first()
        if row:
            dossier = delivery.dossier_for(case, row.dossier_id)
            require(row.actor, case, "delivery.manage")
            if delivery.approved_plan(dossier).pk == row.snapshot["planning_id"] and delivery.latest(dossier, "kickoff").pk == row.pk:
                receipt = row
    else:
        binding = DeliveryDocumentBinding.objects.filter(dossier__case=case, purpose="closure",
                        data__retrospective_id=meeting.pk, version__document__current_id=F("version_id")).order_by("-pk").first()
        if binding:
            dossier = delivery.dossier_for(case, binding.dossier_id)
            delivery_closure.current_retrospective(dossier, meeting.pk)
            if delivery_closure.closure_inputs(dossier, binding.data) == binding.snapshot:
                receipt = binding
    return Observation(case, meeting.evidence, lines(f"Current {meeting.kind} meeting version {meeting.number}.",
            f"Meeting occurred {meeting.occurred_at.isoformat()}.", f"Recorded decisions: {len(meeting.decisions)}.",
            f"Meeting purpose: {meeting.purpose}.", f"Recorded summary excerpt: {meeting.summary[:450]}"), receipt)


def phase_station(plan, actor):
    dossier = delivery.dossier_for(plan.dossier.case, plan.dossier_id)
    case = dossier.case
    check(actor, case, "delivery.read")
    if delivery.approved_plan(dossier).pk != plan.pk:
        raise ValidationError("The exact Planning exit decision has changed.")
    kickoff = delivery.latest(dossier, "kickoff", False)
    receipt = None
    if kickoff and kickoff.snapshot == {"planning_id": plan.pk}:
        from .models import MeetingVersion
        require(kickoff.actor, case, "delivery.manage")
        if MeetingVersion.objects.filter(pk=kickoff.data["meeting_id"], meeting__case=case,
                meeting__current_id=kickoff.data["meeting_id"], kind="kickoff").exists():
            receipt = kickoff
    return Observation(case, plan.evidence, lines(f"Exact Planning exit for delivery candidate {dossier.candidate_id}.",
            f"This decision references {len(plan.snapshot['sources'])} verified sources.",
            "The confirmed Planning-to-kickoff transition establishes no other phase or release approval."), receipt)


ROUTES = [
    *(Route(process, "core.Evidence", planning_packet, creator, partial(planning_station, process))
      for process in ("P17", "P18", "P21", "P25")),
    *(Route(process, "pmo.DeliverySource", lambda row, kinds=kinds: row.kind in kinds, author, planning_gate)
      for process, kinds in (("P22", ("ui_applicability", "ui_design", "ui_client")),
                             ("P23", ("technical_design",)), ("P24", ("test_strategy", "uat_approach")))),
    *(Route(process, "pmo.GateRecord", lambda row, kinds=kinds: row.kind in kinds, creator, release_gate)
      for process, kinds in (("P29", ("qa_exit",)), ("P30", ("uat_product_manager", "uat_product_owner", "uat_client")),
                             ("P31", ("engineering_go",)))),
    Route("P27", "pmo.MeetingVersion", lambda row: row.kind == "kickoff", creator, meeting_station),
    Route("P38", "pmo.MeetingVersion", lambda row: row.kind == "retrospective", creator, meeting_station),
    Route("P63", "pmo.DeliveryRecord", lambda row: row.kind == "planning_decision" and row.data.get("verdict") == "approve",
          author, phase_station),
]
