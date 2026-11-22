"""Source-owned process events, specialist handoffs and native receiver verification."""

from collections import defaultdict
from datetime import timedelta
from functools import lru_cache
from hashlib import sha256
import os

from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.models import Case, Evidence
from apps.core.read_observation import observation_scope
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.policy.services import reference_values
from .native_station_contracts import COMPONENT, DEFINITION, PROJECTION, registry
from .native_station_models import NativeStation, NativeStationAdvice, NativeStationReceipt, NativeStationUse

# A recipient's independent acknowledgement and a customer's incoming response
# can arrive before any internal command consumes advice. Never hold those facts.
INCOMING_RECEIPTS = frozenset({"P05", "P19"})

@lru_cache(maxsize=1)
def by_model():
    index = defaultdict(list)
    for route in registry().values():
        index[route.model.lower()].append(route)
    return index


def capture(sender, instance, raw=False, using="default", **kwargs):
    if raw:
        return
    label = sender._meta.label_lower
    entries = [
        NativeStation(process=route.process, subject_model=label, subject_pk=str(instance.pk))
        for route in by_model().get(label, ()) if route.matches(instance)
    ]
    if entries:
        NativeStation.objects.using(using).bulk_create(entries, ignore_conflicts=True)


def subject_for(station):
    route = registry()[station.process]
    if route.model.lower() != station.subject_model:
        raise ValidationError("The source type has changed.")
    subject = apps.get_model(route.model)._default_manager.get(pk=station.subject_pk)
    if not route.matches(subject):
        raise ValidationError("The source no longer belongs to this process.")
    return route, subject


def checked_observation(station, actor):
    with observation_scope():
        route, subject = subject_for(station)
        if station.projection_version == 1:
            result = route.observe(subject, actor)
        else:
            revision = route.revised_projection
            if not revision or revision.version != station.projection_version or not revision.enabled(subject):
                raise PermissionDenied("The selected source projection is no longer authorised.")
            result = revision.observe(subject, actor)
    if not isinstance(result.case, Case) or not isinstance(result.source, Evidence) or result.source.case_id != result.case.pk:
        raise ValidationError("The department source must belong to this project.")
    if not actor.is_active:
        raise PermissionDenied("An active reader is required.")
    require(actor, result.case, "case.read")
    if sha256(result.source.body.encode()).hexdigest() != result.source.sha256:
        raise ValidationError("The source no longer matches its evidence digest.")
    lines = result.lines
    if (
        not isinstance(lines, dict) or not 1 <= len(lines) <= 100
        or any(not isinstance(k, str) or not k.isascii() or not k.isdecimal() or len(k) > 4
               or not isinstance(v, str) or not v.strip() or len(v) > 1000 for k, v in lines.items())
        or sum(map(len, lines.values())) > 12000
    ):
        raise ValidationError("The department projection needs bounded numbered source lines.")
    if result.receipt is not None:
        if result.receipt.pk is None or result.receipt._state.adding or (
            result.receipt == subject or result.receipt == result.source or result.receipt == result.case
        ):
            raise ValidationError("An independent downstream record is required.")
    return result


def checked_work(work, actor):
    observation = checked_observation(work.native_station, actor)
    if observation.case.pk != work.case_id:
        raise PermissionDenied("The source belongs to a different project.")
    return observation


def readable(actor, work):
    from .native_station_access import read_work
    from django.http import Http404
    try:
        read_work(actor, work.pk)
    except Http404:
        return False
    return True


def enabled_for(case, process):
    from apps.policy.services import resolve
    from apps.agents.specialist_memory import COMPONENT as SOURCE_POLICY

    execution = resolve(COMPONENT, case)
    if execution.status != "ACTIVE" or not reference_values(execution.configuration)[0]["enabled"]:
        return False
    permission = resolve(SOURCE_POLICY, case)
    if permission.status != "ACTIVE":
        return case.synthetic
    value = permission.configuration.envelope["value"]
    return process in value["processes"] and PROJECTION in value["source_kinds"]


@transaction.atomic
def enroll(station_id):
    from .factory import access
    from .factory_progress import set_progress
    from .models import FactoryWork

    station = NativeStation.objects.select_for_update().get(pk=station_id)
    if station.work_id:
        return station.work
    route, subject = subject_for(station)
    actor = route.owner(subject)
    if actor is None:
        raise PermissionDenied("The native source needs an accountable owner.")
    revision = route.revised_projection
    if revision and revision.enabled(subject):
        station.projection_version = revision.version
    source = checked_observation(station, actor)
    access(actor, source.case, "factory.execute", DEFINITION)
    if not enabled_for(source.case, station.process):
        raise ValidationError("Specialist handoffs have not been enabled for this project.")
    identity = digest([station.process, station.subject_model, station.subject_pk])
    request = {"process": station.process, "station": station.pk}
    work = FactoryWork.objects.create(
        definition=DEFINITION, actor=actor, case=source.case, key="station-" + identity,
        business_key=identity, request=request, request_hash=digest(request), source_head=source.source,
    )
    station.work = work
    station.finding = ""
    station.save(update_fields=["work", "finding", "projection_version"])
    set_progress(actor, work.pk, work.revision, True, initial=True)
    return work


@transaction.atomic
def enroll_next():
    station = NativeStation.objects.select_for_update(skip_locked=True).filter(
        work__isnull=True, available_at__lte=timezone.now()
    ).order_by("available_at", "pk").first()
    if station is None:
        return False
    try:
        enroll(station.pk)
    except (ObjectDoesNotExist, PermissionDenied, ValidationError) as error:
        station.finding = "Source authority is unavailable." if isinstance(error, PermissionDenied) else "Waiting for current source evidence or project configuration."
        station.available_at = timezone.now() + timedelta(minutes=5)
        station.save(update_fields=["finding", "available_at"])
    return True


def projection_pin(observation):
    return digest([observation.source.pk, observation.source.sha256, observation.lines])


def receiver_identity(observation):
    receiver = observation.receipt
    return [receiver._meta.label_lower, str(receiver.pk)] if receiver is not None else None


def current_receipt(work, observation):
    receiver = receiver_identity(observation)
    if receiver is None:
        return None
    return NativeStationReceipt.objects.filter(
        handoff__station=work.native_station, handoff__projection_sha256=projection_pin(observation),
        handoff__packet__superseded_by__isnull=True, receiver_model=receiver[0], receiver_pk=receiver[1]
    ).order_by("-pk").first()


@transaction.atomic
def receive_advice(process, subject, actor, *, case=None):
    """Recheck an exact internal handoff in the transaction that consumes it."""
    from apps.agents import specialist_packets

    route = registry()[process]
    if subject._meta.label_lower != route.model.lower():
        raise ValidationError("The receiving command selected a different source type.")
    if not route.matches(subject):
        return None
    station = NativeStation.objects.select_related("work__case").filter(
        process=process, subject_model=route.model.lower(), subject_pk=str(subject.pk)
    ).first()
    if station is None or not station.work_id:
        # Source recording and downstream action may predate activation. Only
        # an explicitly authorised operational process can introduce a wait.
        case = case or getattr(subject, "case", None)
        if case is None:
            return None
        if not enabled_for(case, process):
            return None
        if case.synthetic:
            from apps.agents.specialist_memory import COMPONENT as SOURCE_POLICY
            from apps.policy.services import resolve
            if resolve(SOURCE_POLICY, case).status != "ACTIVE":
                # Synthetic demonstrations without an explicit disclosure
                # selection only enforce handoffs already enrolled by O01.
                return None
        if station is None:
            raise ValidationError("Reconcile the original department source before consuming its findings.")
        raise ValidationError("The department source is queued for specialist review.")
    work = station.work
    if work.cancel_requested or work.status == "cancelled":
        raise ValidationError("The original specialist handoff was stopped.")
    observation = checked_work(work, actor)
    handoff = station.handoffs.select_related("packet").filter(projection_sha256=projection_pin(observation),
        packet__consumed_at__isnull=False, packet__superseded_by=None).order_by("-pk").first()
    if not handoff:
        raise ValidationError("The specialist findings have not reached this department yet.")
    # The recipient's native read above must resolve to identical permitted
    # fields. Only the original execution principal needs model-use authority.
    result = specialist_packets.inspect(handoff.packet, work.execution_actor)
    if result["state"] != "ready" or result["digest"] != handoff.packet_sha256:
        raise ValidationError("The source findings changed. Review the current handoff.")
    NativeStationUse.objects.get_or_create(handoff=handoff, actor=actor)
    return handoff


def snapshot(work, profile, reader=None):
    from .factory import access
    from apps.agents import specialist_memory as memory
    from apps.agents.specialists import routes
    from apps.policy.services import resolve

    actor = reader or work.execution_actor
    access(actor, work.case, "factory.read" if reader else "factory.execute", DEFINITION)
    observation = checked_work(work, actor)
    reading_model = os.getenv("OPENROUTER_MODEL")
    if not work.case.synthetic:
        selection = resolve(memory.COMPONENT, work.case)
        reading_model = selection.configuration.envelope["value"]["model"] if selection.status == "ACTIVE" else None
    grant = None
    if reading_model:
        try:
            for member in routes()[work.native_station.process]["specialist_roles"]:
                grant = memory.permission(work, member["id"], work.native_station.process, PROJECTION, reading_model)
        except PermissionDenied:
            reading_model = None
    state = {
        "station": work.native_station.pk, "process": work.native_station.process,
        "sources": [[observation.source.pk, observation.source.sha256]],
        "projection": projection_pin(observation), "line_hash": digest(observation.lines), "receiver": receiver_identity(observation),
        "reading_model": reading_model, "reading_permission": grant,
        "profile": work.policy_id,
    }
    state["advice_received"] = NativeStationUse.objects.filter(
        handoff__station=work.native_station, handoff__projection_sha256=state["projection"],
        handoff__packet__superseded_by=None
    ).exists()
    stale = observation.source.created_at < timezone.now() - timedelta(seconds=profile["max_age_seconds"])
    state["stale"] = stale
    state["hash"] = digest(state)
    state["work_revision"] = work.revision
    return state, {PROJECTION: observation.source}, [], [PROJECTION] if stale else [], [], []


def latest_packet(work):
    from apps.agents.specialist_models import SpecialistPacket

    return SpecialistPacket.objects.filter(work=work, superseded_by=None).order_by("-pk").first()


def eligible(work, state):
    station = work.native_station
    if state["stale"]:
        return [], "The department needs current source evidence."
    if not state["reading_model"]:
        return [], "Waiting for project permission for this specialist team and source."
    packet = latest_packet(work)
    if not packet or not packet.members.filter(source_id=state["sources"][0][0], projection_sha256=state["line_hash"]).exists():
        return ["ACT04"], "Read the current department evidence."
    handoff = NativeStationAdvice.objects.filter(station=station, packet=packet, projection_sha256=state["projection"]).first()
    if not handoff:
        return ["ACT09"], "Bring the specialist findings to the department."
    if not state["receiver"]:
        return [], "Waiting for the department decision or downstream receipt."
    if station.process not in INCOMING_RECEIPTS and not state["advice_received"]:
        return [], "The receiving department has yet to use the current specialist findings."
    return ["ACT13"], "Verify the downstream receipt against the reviewed source."


def act(work, activity):
    from apps.agents import specialist_packets

    station = work.native_station
    actor = work.execution_actor
    native = checked_work(work, actor)
    pin = projection_pin(native)
    if activity == "ACT04":
        return {"station": station.pk, "source": native.source.pk, "projection": pin}
    packet = latest_packet(work)
    if not packet:
        raise ValidationError("The specialist team has no result for this source.")
    group = specialist_packets.inspect(packet, actor)
    if group["state"] != "ready" or any(row["source"] != native.source.pk for row in group["contributions"]):
        raise ValidationError("The complete specialist team must review the current source.")
    if activity == "ACT09":
        advice, _ = NativeStationAdvice.objects.get_or_create(
            station=station, packet=packet, projection_sha256=pin, packet_sha256=group["digest"],
        )
        return {"handoff": advice.pk, "process": station.process, "packet": packet.pk}
    if activity != "ACT13" or native.receipt is None:
        raise ValidationError("The downstream department receipt is outstanding.")
    advice = NativeStationAdvice.objects.get(station=station, packet=packet, projection_sha256=pin, packet_sha256=group["digest"])
    if station.process not in INCOMING_RECEIPTS and not NativeStationUse.objects.filter(handoff=advice).exists():
        raise ValidationError("The receiving command must consume the current specialist findings.")
    model, pk = receiver_identity(native)
    receipt, _ = NativeStationReceipt.objects.get_or_create(handoff=advice, receiver_model=model, receiver_pk=pk)
    work.status = "verified"
    return {"verification_scope": station.process, "station_receipt": receipt.pk, "receiver": [model, pk], "handoff": advice.pk}
