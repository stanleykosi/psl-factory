"""Staff visibility of department handoffs. Source and decision authority stay native."""
from contextlib import contextmanager
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404

from apps.agents.specialists import routes
from apps.core.models import Case
from apps.identity.factory_access import department_cases
from apps.identity.models import Grant
from apps.identity.services import visible_cases
from .models import FactoryWork
from .native_station_contracts import DEFINITION, PROCESSES


def legacy_cases(actor):
    projects = visible_cases(actor)
    for action in ("agent.extract", "factory.read"):
        projects = projects.filter(pk__in=Grant.objects.filter(user=actor, active=True, action=action).values("case_id"))
    return projects


def project_scope(actor):
    available = Q(pk__in=legacy_cases(actor))
    for role in ("pmo-lead", "finance-lead"):
        available |= Q(pk__in=department_cases(actor, role))
    return Case.objects.filter(available, kind="project")


def candidates(actor):
    eligible = Q(case_id__in=legacy_cases(actor))
    for department, role in (("PMO", "pmo-lead"), ("Finance", "finance-lead")):
        processes = [pid for pid in PROCESSES if routes()[pid]["department"] == department]
        eligible |= Q(case_id__in=department_cases(actor, role), native_station__process__in=processes)
    return FactoryWork.objects.filter(eligible, definition=DEFINITION).select_related("case", "native_station")


def observe(actor, work):
    from .native_stations import checked_work, current_receipt

    current = checked_work(work, actor)
    receipt = current_receipt(work, current)
    if work.status == "verified" and receipt is None:
        raise PermissionDenied("The original receiving record is no longer available.")
    return current, receipt


def read_work(actor, work_id):
    work = candidates(actor).filter(pk=work_id).first()
    if work is None:
        raise Http404
    try:
        current, receipt = observe(actor, work)
    except (ObjectDoesNotExist, PermissionDenied, ValidationError):
        raise Http404 from None
    return work, current, receipt


@contextmanager
def review_scope(work, actor):
    """The appointed person can inspect a pending packet for an already readable source."""
    from apps.identity.factory_access import role_managed
    from apps.identity.services import subject_actions
    from . import factory

    if work.definition != DEFINITION or not role_managed(actor):
        yield
        return
    _, profile = factory.profile(work)
    if (profile["information_resolver_id"] != actor.pk or work.cancel_requested
            or work.status in factory.TERMINAL):
        yield
        return
    if not candidates(actor).filter(pk=work.pk).exists():
        raise PermissionDenied("The reviewer no longer has this project and department.")
    observe(actor, work)
    with subject_actions(actor, work.case, ("agent.extract", "factory.information")):
        yield


def listed(actor, case, before=None):
    query = candidates(actor).filter(case=case)
    if before is not None:
        query = query.filter(pk__lt=before)
    selection = list(query.order_by("-pk")[:21])
    items = []
    for work in selection[:20]:
        try:
            observe(actor, work)
        except (ObjectDoesNotExist, PermissionDenied, ValidationError):
            continue
        items.append(work)
    return items, selection[19].pk if len(selection) > 20 else None


def finance_acknowledgement(actor, work):
    """Offer only the accepted current snapshot and its original HR decision."""
    if work.native_station.process != "F35":
        return None
    from apps.finance import hrfinance
    from .native_stations import subject_for

    _, contract = subject_for(work.native_station)
    snapshot = contract.snapshots.defer("payload").filter(status="accepted").order_by("-pk").first()
    if not snapshot or contract.records.filter(kind="receipt", actor=actor, snapshot=snapshot).exists():
        return None
    from apps.finance.hrfinance_recipient import recipient_scope
    with recipient_scope(actor, work.case, contract.payload["recipient_ids"]):
        hrfinance.snapshot_access(actor, snapshot)
    return snapshot


def acknowledge_finance(actor, work_id, snapshot_id, revision):
    from django.db import transaction
    from apps.finance import hrfinance

    with transaction.atomic():
        work, _, _ = read_work(actor, work_id)
        project = Case.objects.select_for_update().get(pk=work.case_id)
        if work.native_station.process != "F35":
            raise Http404
        from .native_stations import subject_for
        _, contract = subject_for(work.native_station)
        key = f"station-{work.pk}-{snapshot_id}-{actor.pk}"
        prior = contract.records.filter(actor=actor, snapshot_id=snapshot_id, kind="receipt", operation_key=key).first()
        if prior:
            from apps.finance.hrfinance_recipient import recipient_scope
            with recipient_scope(actor, project, contract.payload["recipient_ids"]):
                hrfinance.snapshot_access(actor, prior.snapshot)
            return prior
        snapshot = finance_acknowledgement(actor, work)
        if snapshot is None or snapshot.pk != snapshot_id:
            raise Http404
        original = hrfinance.authorized(snapshot.contract)
        return hrfinance.receive(actor, project.pk, snapshot.pk, key,
                                 original.evidence_id, revision)
