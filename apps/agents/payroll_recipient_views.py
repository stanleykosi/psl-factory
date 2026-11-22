from uuid import UUID

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_safe

from apps.finance import payroll
from apps.finance.payroll_models import PayrollReportReceipt
from . import assistant
from .assistant_views import open_conversation


@login_required
@never_cache
@require_safe
def reports(request):
    receipts = PayrollReportReceipt.objects.filter(actor=request.user, publication__request__case__in=
        payroll.recipient_workspaces(request.user)).select_related('publication__request__case').defer(
            'publication__payload').order_by('-created_at')
    page = Paginator(receipts, 20).get_page(request.GET.get('page'))
    reports = []
    for receipt in page:
        try:
            report = payroll.observe_publication(request.user, receipt.publication_id)
        except (PermissionDenied, ValidationError):
            continue
        reports.append({'case': receipt.publication.request.case, 'pk': receipt.publication_id,
                        'entity': report['entity'], 'period': report['period'], 'version': report['report_version']})
    return render(request, 'finance/payroll_received.html', {'reports': reports, 'page': page})


@login_required
@never_cache
@require_POST
def report_action(request, case_id, pk):
    case = get_object_or_404(payroll.recipient_workspaces(request.user), pk=case_id)
    try:
        with transaction.atomic():
            if request.POST.get('action') == 'acknowledge':
                payroll.receive_report(request.user, case.pk, pk, int(request.POST.get('revision', '')))
                messages.success(request, 'You acknowledged this report.')
            elif request.POST.get('action') == 'ask':
                key = UUID(request.POST.get('operation', ''))
                get_object_or_404(PayrollReportReceipt, actor=request.user, publication_id=pk,
                                  publication__request__case=case)
                chat = open_conversation(request.user, 'zainab', case, key)
                assistant.reserve(request.user, chat.pk, key, assistant.TOTALS_QUESTION, publication_id=pk)
                return redirect('assistant_thread', chat.pk)
            else:
                raise ValidationError('Choose an action on the report.')
    except (ValueError, ValidationError) as exc:
        messages.error(request, ' '.join(exc.messages) if isinstance(exc, ValidationError) else
                       'Reload the report before trying again.')
    return redirect('payroll_inspect', case.pk, 'report', pk)
