from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from adapters import case_uploads
from . import document_review as service
from .document_models import FinanceDocument
from .rules import decimal

from .document_forms import AccountsForm, FigureForm, Figures, ReviewForm


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def inbox(request, case_id=None):
    cases = service.workspaces(request.user).order_by('title', 'pk')
    case = get_object_or_404(cases, pk=case_id) if case_id else None
    if request.method == 'POST' and case:
        try:
            doc = service.submit(request.user, case, request.FILES.get('file'))
            return redirect('finance_document_review', case.pk, doc.pk)
        except (ValidationError, OSError) as exc:
            messages.error(request, ' '.join(exc.messages) if isinstance(exc, ValidationError) else 'Private file storage is unavailable.')
    docs = FinanceDocument.objects.filter(case__in=cases).order_by('-pk')
    if case:
        docs = docs.filter(case=case)
    from django.core.paginator import Paginator
    return render(request, 'finance/document_inbox.html', {'case': case, 'cases': cases,
                  'page': Paginator(docs, 25).get_page(request.GET.get('page'))})


def scoped(request, case_id, pk):
    return get_object_or_404(FinanceDocument.objects.select_related('case', 'reviewer', 'receipt'),
                             case__in=service.workspaces(request.user), case_id=case_id, pk=pk)


@login_required
@never_cache
@require_safe
def original(request, case_id, pk):
    doc = scoped(request, case_id, pk)
    return FileResponse(BytesIO(case_uploads.read(doc)), as_attachment=True, filename=doc.name)


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def review(request, case_id, pk):
    doc = scoped(request, case_id, pk)
    action = request.POST.get('action') if request.method == 'POST' else None
    data = request.POST if action == 'approve' else None
    form = ReviewForm(data, initial=doc.draft)
    rows = Figures(data, initial=doc.draft.get('rows', []), prefix='rows')
    accounts = AccountsForm(request.POST if action == 'accounts' else None, initial={'entity': doc.approved.get('entity')})
    try:
        if action == 'approve' and form.is_valid() and rows.is_valid():
            items = [{k: r[k] for k in FigureForm.base_fields} for r in rows.cleaned_data if r and not r.get('DELETE')]
            service.approve(request.user, doc.case, pk, request.POST.get('attempt'), form.cleaned_data, items)
            return redirect(request.path)
        if action == 'retry':
            service.retry(request.user, doc.case, pk, request.POST.get('attempt'))
            return redirect(request.path)
        if action == 'return':
            service.return_file(request.user, doc.case, pk, request.POST.get('attempt'), request.POST.get('reason'))
            return redirect(request.path)
        if action == 'accounts' and accounts.is_valid():
            service.handoff(request.user, doc.case, pk, **accounts.cleaned_data)
            return redirect(request.path)
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    from apps.workflows.factory_accounting_intake import latest
    display_rows = [{**row, 'display_amount': format(decimal(row['full_amount']), ',f')}
                    for row in doc.approved.get('rows', [])]
    total = doc.approved.get('full_control_total')
    return render(request, 'finance/document_review.html', {'doc': doc, 'form': form, 'rows': rows,
                  'display_rows': display_rows, 'display_total': format(decimal(total), ',f') if total is not None else None,
                  'accounts': accounts, 'receipt': latest(doc.receipt) if doc.receipt_id else None})
