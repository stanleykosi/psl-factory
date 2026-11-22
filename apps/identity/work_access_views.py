from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import WorkAccessRequest


MAX_REFERENCE = (1 << 63) - 1


def unavailable(request, work_id):
    response = render(request, '404.html', {'access_reference': work_id if 0 < work_id <= MAX_REFERENCE else None}, status=404)
    response['Cache-Control'] = 'no-store'
    return response


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def request_access(request, work_id):
    if not 0 < work_id <= MAX_REFERENCE:
        raise Http404
    user_model = get_user_model()
    if request.method == 'POST':
        with transaction.atomic():
            if not user_model.objects.select_for_update().filter(pk=request.user.pk, is_active=True).first():
                raise PermissionDenied
            requests = WorkAccessRequest.objects.filter(requester=request.user)
            if not requests.filter(work_reference=work_id).exists():
                # Bound writes from guessed links without querying their targets.
                cutoff = timezone.now() - timedelta(hours=1)
                if requests.filter(created_at__gte=cutoff).count() >= 10:
                    return render(request, 'identity/work_access_request.html', {'limited': True}, status=429)
                requests.create(requester=request.user, work_reference=work_id)
        return redirect('work_access_request', work_id=work_id)
    if not user_model.objects.filter(pk=request.user.pk, is_active=True).exists():
        raise PermissionDenied
    saved = WorkAccessRequest.objects.filter(requester=request.user, work_reference=work_id).exists()
    return render(request, 'identity/work_access_request.html', {'saved': saved})
