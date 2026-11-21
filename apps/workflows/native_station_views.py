from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe
from apps.agents.specialists import routes
from apps.identity.factory_access import project_cases
from apps.identity.services import require
from .native_stations import DEFINITION, checked_work, current_receipt, readable
from .models import FactoryWork


@login_required
@require_safe
def project(request, case_id):
    case = get_object_or_404(project_cases(request.user), pk=case_id)
    require(request.user, case, "factory.read")
    require(request.user, case, "agent.extract")
    query = FactoryWork.objects.filter(definition=DEFINITION, case=case)
    cursor = request.GET.get("before", "")
    if cursor.isascii() and cursor.isdecimal() and len(cursor) <= 18:
        query = query.filter(pk__lt=int(cursor))
    candidates = list(query.select_related("native_station", "actor", "case").order_by("-pk")[:21])
    rows = [(work, routes()[work.native_station.process]["original_title"]) for work in candidates[:20] if readable(request.user, work)]
    response = render(request, "factory/project_handoffs.html", {
        "case": case, "rows": rows, "cursor": candidates[19].pk if len(candidates) > 20 else None,
    })
    response["Cache-Control"] = "private, no-store"
    return response


def detail(request, work):
    current = checked_work(work, request.user)
    receipt = current_receipt(work, current)
    response = render(request, "factory/department_handoff.html", {
        "work": work,
        "title": routes()[work.native_station.process]["original_title"],
        "lines": current.lines.values(),
        "received": receipt is not None,
        "recorded_at": receipt.created_at if receipt else None,
    })
    response["Cache-Control"] = "private, no-store"
    return response
