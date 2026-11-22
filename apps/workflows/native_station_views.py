from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe
from apps.agents.specialists import routes
from .native_station_access import acknowledge_finance, finance_acknowledgement, listed, project_scope, read_work


@login_required
@require_safe
def project(request, case_id):
    case = get_object_or_404(project_scope(request.user), pk=case_id)
    cursor = request.GET.get("before", "")
    before = int(cursor) if cursor.isascii() and cursor.isdecimal() and len(cursor) <= 18 else None
    items, continuation = listed(request.user, case, before)
    rows = [(work, routes()[work.native_station.process]["original_title"]) for work in items]
    response = render(request, "factory/project_handoffs.html", {
        "case": case, "rows": rows, "cursor": continuation,
    })
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET", "HEAD", "POST"])
def detail(request, work):
    work, current, receipt = read_work(request.user, work.pk)
    if request.method == "POST":
        if request.POST.get("action") != "acknowledge_finance":
            raise Http404
        try:
            acknowledge_finance(request.user, work.pk, int(request.POST["snapshot_id"]), int(request.POST["revision"]))
        except (KeyError, ValueError):
            raise Http404 from None
        except ValidationError:
            messages.error(request, "The handoff changed. Check its current evidence before acknowledging it.")
        return redirect("factory_detail", work_id=work.pk)
    response = render(request, "factory/department_handoff.html", {
        "work": work,
        "title": routes()[work.native_station.process]["original_title"],
        "lines": current.lines.values(),
        "received": receipt is not None,
        "recorded_at": receipt.created_at if receipt else None,
        "finance_snapshot": finance_acknowledgement(request.user, work),
    })
    response["Cache-Control"] = "private, no-store"
    return response
