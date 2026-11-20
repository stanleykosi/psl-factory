from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.identity.services import active_case_grants
from apps.pmo import rfp_estimate_requests as estimate

from . import factory_rfp


class ReviewForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    draft = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    channel = forms.ChoiceField(label='Send by')
    due_on = forms.DateField(label='Estimate needed by', widget=forms.DateInput(attrs={'type': 'date'}))
    body = forms.CharField(max_length=4000, label='Message', widget=forms.Textarea(attrs={'rows': 6}))
    evidence = forms.ModelChoiceField(queryset=None, label='Review evidence')
    attachment = forms.ModelChoiceField(queryset=None, required=False, label='Your private attachment')


class ReceiptForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    dispatch = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    evidence = forms.ModelChoiceField(queryset=None, label='Original channel receipt evidence')
    reference = forms.CharField(max_length=160, label='Original receipt reference')
    result = forms.ChoiceField(choices=[('delivered', 'Delivered'), ('failed', 'Confirmed failed')], label='Actual result')


@login_required
@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def detail(request, work_id):
    from .factory_views import visible

    actor = request.user
    work = get_object_or_404(visible(actor, work_id=work_id), pk=work_id, definition=factory_rfp.DEFINITION)
    estimate.access(actor, work)
    case = work.case
    configuration, destinations = estimate.routes(case)
    try:
        _, scope = estimate.scope(actor, work)
    except PermissionDenied:
        scope = None
    except ValidationError:
        scope = None
    draft = estimate.current_draft(actor, work, scope) if scope else None
    reviewed = (work.estimate_requests.filter(actor=actor).select_related('dispatch__receipt', 'attachment')
                .order_by('-pk').first())
    dispatch = getattr(reviewed, 'dispatch', None)
    receipt = getattr(dispatch, 'receipt', None)
    decision = request.POST.get('action', '')
    review = None
    if draft and destinations:
        review = ReviewForm(request.POST if decision == 'review' else None, initial={
            'revision': case.revision, 'draft': draft.pk, 'body': draft.evidence.body})
        channels = {'email': 'Email', 'whatsapp': 'WhatsApp'}
        review.fields['channel'].choices = [(key, f'{channels[key]} · {route["contact"]}') for key, route in destinations.items()]
        review.fields['evidence'].queryset = case.evidence.filter(kind='policy_decision').order_by('-version')
        review.fields['attachment'].queryset = estimate.attachments(actor, work)
    receipt_form = None
    if dispatch and not receipt and reviewed.payload['route']['method'] == 'manual_receipt':
        receipt_form = ReceiptForm(request.POST if decision == 'receipt' else None, initial={
            'revision': case.revision, 'dispatch': dispatch.pk})
        receipt_form.fields['evidence'].queryset = case.evidence.filter(kind='rfp_estimate_receipt').order_by('-version')
    grants = active_case_grants(actor, [case.pk], actions=['rfp.estimate.send', 'policy.configure', 'ops.read', 'agent.rfp'])
    can_send = (case.pk, 'rfp.estimate.send') in grants
    if request.method == 'POST':
        try:
            if decision == 'prepare':
                estimate.prepare(actor, work.pk, int(request.POST.get('revision', '')))
            elif decision == 'review' and review and review.is_valid():
                value = review.cleaned_data
                attachment = value['attachment']
                estimate.review(actor, work.pk, value['revision'], value['draft'], value['channel'], value['due_on'],
                                value['body'], value['evidence'].pk, attachment.pk if attachment else None)
            elif decision == 'release':
                estimate.release(actor, work.pk, int(request.POST.get('revision', '')), int(request.POST.get('request', '')))
            elif decision == 'receipt' and receipt_form and receipt_form.is_valid():
                value = receipt_form.cleaned_data
                estimate.record_receipt(actor, work.pk, value['revision'], value['dispatch'], value['reference'],
                                        value['result'] == 'delivered', value['evidence'].pk)
            else:
                raise ValidationError('Select the current request and complete the required fields.')
        except (ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, 'Security request updated. The estimate is recorded separately when it arrives.')
            return redirect('factory_rfp_security_estimate', work_id=work.pk)
    return render(request, 'factory/rfp_security_estimate.html', {
        'work': work, 'case': case, 'draft': draft, 'destinations': destinations, 'review_form': review,
        'can_prepare': scope and (case.pk, 'agent.rfp') in grants, 'reviewed': reviewed, 'dispatch': dispatch,
        'receipt': receipt, 'receipt_form': receipt_form if can_send else None,
        'can_release': bool(scope and configuration and reviewed and not dispatch and can_send
                            and reviewed.configuration_id == configuration.pk and reviewed.payload['scope'] == scope),
        'can_configure': all((case.pk, action) in grants for action in ('ops.read', 'policy.configure')),
    })
