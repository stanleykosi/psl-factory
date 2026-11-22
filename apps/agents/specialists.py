"""O01's closed specialist dispatcher over native process tools."""

import json
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.documents.contracts import digest


@lru_cache(maxsize=1)
def routes():
    path = settings.BASE_DIR / "reference/08-agent-architecture/process-agent-assignments.json"
    assignments = json.loads(path.read_text(encoding="utf-8"))["assignments"]
    return {row["id"]: row for row in assignments}


# Pick a supporting specialist only for the task it performs. The primary
# specialist handles investigation and any activity without a specialist match.
SUPPORT = {
    "ACT05": ("A04", "A03"),
    "ACT06": ("A02", "A04"),
    "ACT07": ("A02", "A01"),
    "ACT08": ("A05", "A06", "A02"),
    "ACT09": ("A06", "A02", "A07"),
    "ACT10": ("A07", "A04"),
    "ACT11": ("A04", "A07"),
    "ACT12": ("A03", "A07"),
    "ACT13": ("A08", "A07", "A02"),
    "ACT14": ("A03",),
    "ACT15": ("A06",),
}


def validate_selection(processes, roles, source_kinds=(), *, coordinate=False):
    from apps.workflows.native_station_contracts import PROCESSES, PROJECTION
    assigned = set()
    for process in processes:
        route = routes().get(process)
        matching = {row["id"] for row in route["specialist_roles"]} if route else set()
        if not route or route["department"] == "BaaS" or not matching.intersection(roles):
            raise ValidationError("Each process needs a matching release specialist.")
        if (coordinate or (PROJECTION in source_kinds and process in PROCESSES)) and matching.difference(roles):
            missing = ", ".join(sorted(matching.difference(roles)))
            raise ValidationError(f"The department handoff for {process} also requires {missing}.")
        assigned.update(matching)
    if set(roles) - assigned:
        raise ValidationError("Select only specialists assigned to at least one chosen process.")


def assignment(process, activity):
    route = routes()[process]
    if route["department"] == "BaaS":
        raise ValidationError("This process is outside the active specialist release.")
    candidates = {item["id"]: item for item in route["specialist_roles"]}
    role = next((code for code in SUPPORT.get(activity, ()) if code in candidates), next(iter(candidates)))
    selected = candidates[role]
    return {
        "version": 1,
        "coordinator": "O01",
        "process": process,
        "role": role,
        "activity": activity,
        "task": selected["process_responsibility"],
    }


def dispatch(work, child, assignment_record, choice, profile, sources, missing, stale, tasks, jobs):
    from apps.workflows import factory
    from apps.workflows.factory_processes import PROCESS_IDS
    from . import specialist_packets

    if (
        child.parent_id is None
        or child.parent.work_id != work.pk
        or child.parent.kind != "ACT03"
        or child.work_id != work.pk
        or child.kind != choice["activity"]
        or assignment_record["process"] not in PROCESS_IDS.get(work.definition, ())
        or assignment_record != assignment(assignment_record["process"], child.kind)
    ):
        raise ValidationError("The specialist task has lost its coordinator binding.")
    result = factory.act(work, choice, profile, sources, missing, tasks, jobs)
    if not isinstance(result, dict):
        raise ValidationError("The native specialist tool returned an invalid result.")
    # Commit the receipt with the child attempt and domain command. Private
    # native results continue to live behind the original subject's reader.
    receipt = {**assignment_record, "native_result_sha256": digest(result)}
    station = work.definition == "process-handoff/v1"
    if child.kind == "ACT04" or (not station and child.kind in ("ACT08", "ACT09")):
        packet = specialist_packets.schedule(
            work,
            child,
            receipt["process"],
            {kind: row for kind, row in sources.items() if kind not in stale},
            profile,
        )
        if packet:
            receipt["source_review"] = packet.pk
        elif station:
            raise ValidationError("Project authorization and a configured model are required for this source review.")
    if (
        work.definition == "delivery-release/v1"
        and child.kind == "ACT04"
        and result.get("progress_investigation_id")
    ):
        from .models import AgentRun

        run = AgentRun.objects.get(
            pk=result["progress_investigation_id"],
            case=work.case,
            actor=work.execution_actor,
            provider="deterministic-delivery-progress-v1",
            process_id="P28",
        )
        packet = specialist_packets.schedule(work, child, run.process_id, sources, profile)
        if packet:
            if packet.members.exclude(source_id=run.evidence_id).exists():
                raise ValidationError("Delivery progress changed during source review.")
            receipt["progress_review"] = {"investigation": run.pk, "packet": packet.pk}
    return result, receipt
