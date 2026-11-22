from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from adapters import case_uploads
from .specialist_memory import current
from .specialist_models import SpecialistReading
from . import specialist_packets


@login_required
@require_POST
def resolve_findings(request, work_id, pk):
    try:
        specialist_packets.acknowledge(
            request.user, work_id, pk, request.POST.get("digest"), request.POST.get("reason")
        )
    except (
        PermissionDenied,
        specialist_packets.SpecialistPacket.DoesNotExist,
        specialist_packets.FactoryWork.DoesNotExist,
    ):
        raise Http404 from None
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    return redirect("factory_detail", work_id=work_id)


@login_required
@require_safe
@never_cache
def report(request, work_id, pk):
    reading = get_object_or_404(
        SpecialistReading.objects.select_related("work__case", "work__actor", "source", "actor"),
        pk=pk,
        work_id=work_id,
        status="ready",
    )
    try:
        check_report_reader(reading, request.user)
        data = case_uploads.read(reading)
        reading.work.refresh_from_db()
        check_report_reader(reading, request.user)
    except (PermissionDenied, ValidationError):
        raise Http404 from None
    except OSError:
        return HttpResponse("The private file store is temporarily unavailable.", status=503)
    response = HttpResponse(data, content_type="text/plain; charset=utf-8")
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Disposition"] = f'inline; filename="work-{work_id}-source-reading-{pk}.txt"'
    return response


def check_report_reader(reading, actor):
    from apps.workflows.native_station_access import DEFINITION, review_scope

    if reading.work.definition == DEFINITION:
        review = specialist_packets.review_for(reading.work, actor)
        if review and any(row["task"] == reading.pk for row in review["contributions"]):
            with review_scope(reading.work, actor):
                return current(reading, actor)
    return current(reading, actor)
