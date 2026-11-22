from io import BytesIO
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads
from apps.agents.assistant_access import WINNING, permission
from . import bid_sharing as sharing


@login_required
@never_cache
@require_safe
def library(request, case_id):
    workspace = get_object_or_404(sharing.workspaces(request.user), pk=case_id)
    bids = sharing.available(request.user, workspace)
    query = request.GET.get('q', '').strip()[:160]
    if query:
        bids = bids.filter(reference__icontains=query)
    page = Paginator(bids.order_by('reference', 'pk'), 25).get_page(request.GET.get('page'))
    return render(request, 'pmo/bid_library.html', {'case': workspace, 'page': page, 'query': query})


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def record(request, case_id, bid_id):
    workspace = get_object_or_404(sharing.workspaces(request.user), pk=case_id)
    bid = get_object_or_404(sharing.available(request.user, workspace), pk=bid_id)
    owner = workspace.pk == bid.case_id and sharing.owns(request.user, bid)
    error = None
    if request.method == 'POST':
        if not owner:
            raise PermissionDenied
        try:
            if request.POST.get('action') == 'sharing':
                sharing.set_visibility(request.user, workspace, bid.pk, request.POST.get('visibility'),
                                       int(request.POST.get('version', '')))
                messages.success(request, 'Bid sharing saved.')
            elif request.POST.get('action') == 'note':
                sharing.record_note(request.user, workspace, bid.pk, request.POST.get('body', ''),
                                    request.POST.get('operation'))
                messages.success(request, 'Client conversation recorded.')
            else:
                raise ValidationError('Choose an action on this bid.')
            return redirect('bid_record', workspace.pk, bid.pk)
        except (ValueError, ValidationError) as exc:
            error = ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Reload the sharing form.'
    attachment = sharing.visible_attachment(request.user, bid)
    earlier_rule = owner and bid.sharing_version is None and permission(bid.case, WINNING)
    return render(request, 'pmo/bid_record.html', {'case': workspace, 'bid': bid, 'owner': owner,
        'entries': sharing.record_entries(bid), 'attachment': attachment, 'operation': uuid4(), 'error': error,
        'earlier_rule': bool(earlier_rule)})


@login_required
@never_cache
@require_safe
def original_file(request, case_id, bid_id):
    workspace = get_object_or_404(sharing.workspaces(request.user), pk=case_id)
    bid = get_object_or_404(sharing.available(request.user, workspace), pk=bid_id)
    attachment = sharing.visible_attachment(request.user, bid)
    if not attachment:
        raise Http404
    try:
        data = case_uploads.read(attachment)
    except (OSError, ValidationError):
        raise Http404('The original file is unavailable.') from None
    return FileResponse(BytesIO(data), as_attachment=True, filename=attachment.name,
                        content_type='application/octet-stream')
