"""Department receipts and source reviews for authenticated clients."""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.agents import specialist_coordination, specialist_packets
from apps.agents.specialists import routes
from apps.workflows.native_station_access import acknowledge_finance, finance_acknowledgement, listed, project_scope, read_work
from apps.workflows.factory_execution import can_control
from apps.workflows.native_station_contracts import PROCESSES
from .http import DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj


ITEM = obj({"work_id": ID, "project_id": UUID, "process": TEXT, "title": TEXT, "status": TEXT, "django_url": TEXT})
REVIEW = obj({"packet_id": ID, "digest": TEXT, "readings": array(obj({"specialist": TEXT, "assessment": TEXT,
                                                                    "report_url": TEXT})),
              "findings": array(obj({"report_url": TEXT, "line": TEXT, "issue": TEXT}), limit=5)})
SOURCE_DECISION = obj({"packet_id": ID, "digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                       "reason": {"type": "string", "minLength": 1, "maxLength": 2000}})


def item(work):
    process = work.native_station.process
    return {"work_id": work.pk, "project_id": work.case_id, "process": process,
            "title": routes()[process]["original_title"], "status": work.status,
            "django_url": reverse("factory_detail", args=[work.pk])}


@endpoint(response=obj({"items": array(ITEM, limit=20), "next_before": nullable(ID)}),
          query={"before": ID, "process": choice(*sorted(PROCESSES))}, summary="Read current department handoffs for this project")
def project(request, case_id):
    process = request.GET.get("process")
    if process is not None and process not in PROCESSES:
        raise Problem(422, "invalid_filter", "Choose a listed automatic process.")
    case = get_object_or_404(project_scope(request.user, process=process), pk=case_id)
    raw = request.GET.get("before")
    if raw is not None and not (raw.isascii() and raw.isdecimal() and len(raw) <= 18 and int(raw) > 0):
        raise Problem(422, "invalid_filter", "Choose a valid handoff cursor.")
    works, cursor = listed(request.user, case, int(raw) if raw is not None else None, process=process)
    return {"items": [item(work) for work in works], "next_before": cursor}


@endpoint(response=obj({**ITEM["properties"], "evidence": array(TEXT, limit=100),
                        "receipt": nullable(obj({"verified_at": DATETIME})), "source_review": nullable(REVIEW),
                        "coordinator_retry": nullable(obj({"check_id": ID, "revision": REVISION})),
                        "finance_acknowledgement": nullable(obj({"snapshot_id": ID, "revision": REVISION}))}),
          summary="Read the exact department evidence, verified receipt and available source review")
def detail(request, work_id):
    work, current, receipt = read_work(request.user, work_id)
    result = specialist_packets.review_for(work, request.user)
    review = None
    if result:
        review = {"packet_id": result["packet"], "digest": result["digest"], "readings": [
            {"specialist": row["role"], "assessment": row["assessment"],
             "report_url": reverse("specialist_report", args=[work.pk,row["task"]])}
            for row in result["contributions"] if row["status"] == "ready"
        ], "findings": [{"report_url": reverse("specialist_report", args=[work.pk, row["report"]]),
                         "line": row["line"], "issue": row["issue"]} for row in result["coordinator_findings"]]}
    snapshot = finance_acknowledgement(request.user, work)
    retry = specialist_coordination.retry_candidate(work) if can_control(request.user, work) else None
    return {**item(work), "evidence": list(current.lines.values()), "source_review": review,
            "coordinator_retry": {"check_id": retry.pk, "revision": work.revision} if retry else None,
            "finance_acknowledgement": {"snapshot_id": snapshot.pk, "revision": work.case.revision} if snapshot else None,
            "receipt": {"verified_at": receipt.created_at} if receipt else None}


@endpoint(method="POST", request=SOURCE_DECISION, response=obj({"work_id": ID, "packet_id": ID}),
          summary="Record the appointed reviewer's resolution of these exact source findings")
def review(request, work_id, *, body):
    work, _, _ = read_work(request.user, work_id)
    result = specialist_packets.review_for(work, request.user)
    if not result or result["packet"] != body["packet_id"]:
        raise Http404
    specialist_packets.acknowledge(request.user, work.pk, result["packet"], body["digest"], body["reason"])
    return {"work_id": work.pk, "packet_id": result["packet"]}


@endpoint(method="POST", request=obj({"snapshot_id": ID, "revision": REVISION}), response=obj({"receipt_id": ID}),
          summary="Acknowledge the HR-approved snapshot as its named Finance recipient")
def acknowledge(request, work_id, *, body):
    receipt = acknowledge_finance(request.user, work_id, body["snapshot_id"], body["revision"])
    return {"receipt_id": receipt.pk}


@endpoint(method="POST", request=obj({"revision": REVISION, "reason": SOURCE_DECISION["properties"]["reason"]}),
          response=obj({"check_id": ID}), status=202, summary="Retry an exact coordinator check within the work allowance")
def retry(request, work_id, check_id, *, body):
    from apps.workflows.models import FactoryWork

    try:
        specialist_coordination.retry(request.user, work_id, check_id, body["revision"], body["reason"])
    except FactoryWork.DoesNotExist:
        raise Http404 from None
    return {"check_id": check_id}
