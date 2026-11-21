"""Process-scoped fan-out and evidence-bound join at O01's native command boundary."""

import os

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.services import resolve
from apps.workflows import factory
from apps.workflows.factory_progress import wake_waiting
from apps.workflows.models import FactoryProgress, FactoryWork
from . import specialist_memory as memory
from .specialist_models import SpecialistPacket, SpecialistReading
from .specialists import routes


INDEPENDENT = {"ACT04", "ACT05", "ACT12"}


def schedule(work, child, process, sources, profile):
    """Called with the work lock held. Reserve the complete group or none of it."""
    model = os.environ.get("OPENROUTER_MODEL")
    if not FactoryProgress.objects.filter(work=work, status__in=("running", "queued", "waiting")).exists():
        return None
    try:
        require(work.execution_actor, work.case, "agent.extract")
    except PermissionDenied:
        return None
    if not work.case.synthetic:
        resolution = resolve(memory.COMPONENT, work.case)
        if resolution.status != "ACTIVE":
            return None
        rule = resolution.configuration.envelope["value"]
        if process not in rule["processes"]:
            return None
        model = rule["model"]
    if not model or len(model) > 160:
        return None
    # The invoice snapshot can see other records in the project. Select only
    # configured inputs and the source attached to this native intake.
    assignments = []
    for source, purpose, lines in memory.inputs_for(work, sources, profile, work.execution_actor, process):
        for responsibility in routes()[process]["specialist_roles"]:
            role = responsibility["id"]
            try:
                grant = memory.permission(work, role, process, purpose, model)
            except PermissionDenied:
                continue
            key = digest(
                [
                    2,
                    work.pk,
                    work.execution_actor_id,
                    process,
                    role,
                    responsibility["process_responsibility"],
                    work.source_head_id,
                    source.pk,
                    source.sha256,
                    digest(lines),
                    model,
                    work.policy_id,
                    grant,
                ]
            )
            assignments.append((key, role, source, grant, digest(lines)))
    if not assignments:
        return None
    keys = [key for key, *_ in assignments]
    packet_key = digest([work.pk, child.pk, process, keys])
    packet = SpecialistPacket.objects.filter(identity=packet_key).first()
    if packet:
        return packet
    existing = SpecialistReading.objects.in_bulk(keys, field_name="identity")
    count = len(assignments) - len(existing)
    reserve = count * profile["tokens_per_call"]
    if work.budget_used + reserve > min(work.budget_limit, profile["max_tokens"]):
        raise ValidationError("The work allowance cannot cover its complete source review.")
    if count and task_count(work) + count > profile["max_children"]:
        raise ValidationError("The work reached its specialist task limit.")
    for key, role, source, grant, projection in assignments:
        if key not in existing:
            existing[key] = SpecialistReading.objects.create(
                work=work,
                child=child,
                actor=work.execution_actor,
                process=process,
                role=role,
                source=source,
                source_hash=source.sha256,
                projection_sha256=projection,
                policy_id=work.policy_id,
                permission_id=grant,
                identity=key,
                model=model,
                token_limit=profile["tokens_per_call"],
            )
    packet = SpecialistPacket.objects.create(work=work, child=child, identity=packet_key, process=process)
    packet.members.add(*existing.values())
    work.budget_used += reserve
    return packet


def task_count(work):
    return work.activities.count() + SpecialistReading.objects.filter(work=work).count()


def inspect(packet, actor):
    """Only checked excerpts are joined. A material objection always reaches a person."""
    members = list(packet.members.select_related("source", "work__case", "actor").order_by("role", "source_id"))
    if not members:
        raise ValidationError("This source review is incomplete.")
    required = {role["id"] for role in routes()[packet.process]["specialist_roles"]}
    by_source = {}
    for member in members:
        by_source.setdefault(member.source_id, set()).add(member.role)
    if any(roles != required for roles in by_source.values()):
        raise PermissionDenied("The source review needs the remaining assigned specialists.")
    pins = []
    pending = False
    unavailable = False
    attention = False
    values_by_field = {}
    disagreements = []
    context = memory.read_context(packet.work, actor, packet.process)
    for reading in members:
        if reading.work_id != packet.work_id or reading.process != packet.process:
            raise ValidationError("The source task is outside this handoff.")
        lines = memory.current(reading, actor, context=context)
        if reading.status in ("queued", "reading", "storing"):
            pending = True
        elif reading.status != "ready" or not reading.sha256 or not reading.size:
            unavailable = True
        elif reading.disposition != "supported":
            attention = True
        for anchor in reading.anchors:
            field = anchor["field"]
            key = (reading.source_id, field)
            value = lines[anchor["line"]][anchor["start"] : anchor["end"]]
            previous = values_by_field.setdefault(key, value)
            if previous != value and key not in disagreements:
                disagreements.append(key)
                attention = True
        pins.append(
            {
                "task": reading.pk,
                "role": reading.role,
                "source": reading.source_id,
                "source_hash": reading.source_hash,
                "artifact": reading.sha256,
                "lines": reading.citation_lines,
                "status": reading.status,
                "assessment": reading.disposition,
                "anchors": reading.anchors,
            }
        )
    fingerprint = digest([packet.identity, pins])
    reviewed = packet.reviewed_hash == fingerprint and packet.reviewer_id is not None
    if unavailable:
        state = "unavailable"
    elif pending:
        state = "waiting"
    elif attention and not reviewed:
        state = "review"
    else:
        state = "ready"
    return {
        "packet": packet.pk,
        "process": packet.process,
        "state": state,
        "digest": fingerprint,
        "contributions": pins,
        "disagreements": [{"source": source, "field": field} for source, field in disagreements],
        "reviewer": packet.reviewer_id if reviewed else None,
    }


def join(work, actor, sources, profile):
    results = []
    outstanding = SpecialistPacket.objects.filter(work=work, consumed_at=None, superseded_by=None)
    for packet in list(outstanding.select_related("child").order_by("pk")):
        try:
            result = inspect(packet, actor)
        except (PermissionDenied, ValidationError):
            replacement = schedule(work, packet.child, packet.process, sources, profile)
            if not replacement or replacement.pk == packet.pk:
                return "source_changed", []
            old_roles = set(packet.members.values_list("role", flat=True))
            if old_roles - set(replacement.members.values_list("role", flat=True)):
                return "source_changed", []
            packet.superseded_by = replacement
            packet.save(update_fields=["superseded_by"])
            return "waiting", []
        if result["state"] != "ready":
            return result["state"], []
        results.append(result)
    return "ready", results


def review_for(work, actor):
    packet = (
        SpecialistPacket.objects.filter(work=work, consumed_at=None, superseded_by=None, reviewed_at=None)
        .order_by("pk")
        .first()
    )
    if not packet:
        return None
    try:
        result = inspect(packet, actor)
        if result["state"] != "review":
            return None
        factory.access(actor, work.case, "factory.information", work.definition)
        _, profile = factory.profile(work)
        if profile["information_resolver_id"] == actor.pk:
            return result
    except (PermissionDenied, ValidationError):
        pass
    return None


@transaction.atomic
def acknowledge(actor, work_id, packet_id, expected, reason):
    work = FactoryWork.objects.select_for_update(of=("self",)).get(pk=work_id)
    factory.access(actor, work.case, "factory.information", work.definition)
    _, profile = factory.profile(work)
    if (
        actor.pk != profile["information_resolver_id"]
        or work.cancel_requested
        or work.status in factory.TERMINAL
    ):
        raise PermissionDenied("The current information reviewer is required.")
    packet = SpecialistPacket.objects.select_for_update().get(
        pk=packet_id, work=work, consumed_at=None, superseded_by=None
    )
    result = inspect(packet, actor)
    if result["state"] != "review" or expected != result["digest"]:
        raise ValidationError("The source review changed. Open it again.")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise ValidationError("Record the evidence and how you resolved the findings.")
    packet.reviewed_hash = expected
    packet.review_reason = reason.strip()
    packet.reviewer = actor
    packet.reviewed_at = timezone.now()
    packet.save(update_fields=["reviewed_hash", "review_reason", "reviewer", "reviewed_at"])
    wake_waiting(work.pk)
