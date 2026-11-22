"""Department receipts and source reviews for authenticated clients."""
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.agents import specialist_packets
from apps.agents.specialists import routes
from apps.workflows.native_station_access import acknowledge_finance, finance_acknowledgement, listed, project_scope, read_work
from .http import DATETIME, ID, REVISION, TEXT, UUID, Problem, array, endpoint, nullable, obj


ITEM = obj({"work_id": ID, "project_id": UUID, "process": TEXT, "title": TEXT, "status": TEXT, "django_url": TEXT})
REVIEW = obj({"packet_id": ID, "digest": TEXT, "readings": array(obj({"specialist": TEXT, "assessment": TEXT,
                                                                    "report_url": TEXT}))})
SOURCE_DECISION = obj({"packet_id": ID, "digest": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                       "reason": {"type": "string", "minLength": 1, "maxLength": 2000}})


def item(work):
    process = work.native_station.process
    return {"work_id": work.pk, "project_id": work.case_id, "process": process,
            "title": routes()[process]["original_title"], "status": work.status,
            "django_url": reverse("factory_detail", args=[work.pk])}


@endpoint(response=obj({"items": array(ITEM, limit=20), "next_before": nullable(ID)}),
          query={"before": ID}, summary="Read current department handoffs for this project")
def project(request, case_id):
    case = get_object_or_404(project_scope(request.user), pk=case_id)
    raw = request.GET.get("before")
    if raw is not None and not (raw.isascii() and raw.isdecimal() and len(raw) <= 18 and int(raw) > 0):
        raise Problem(422, "invalid_filter", "Choose a valid handoff cursor.")
    works, cursor = listed(request.user, case, int(raw) if raw is not None else None)
    return {"items": [item(work) for work in works], "next_before": cursor}


@endpoint(response=obj({**ITEM["properties"], "evidence": array(TEXT, limit=100),
                        "receipt": nullable(obj({"verified_at": DATETIME})), "source_review": nullable(REVIEW),
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
        ]}
    snapshot = finance_acknowledgement(request.user, work)
    return {**item(work), "evidence": list(current.lines.values()), "source_review": review,
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
