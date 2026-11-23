from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.pmo import rfp_fresh_intake, rfp_intake_context


class ReceivedBidForm(forms.Form):
    start_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid4)
    authority = forms.TypedChoiceField(label='Organization', coerce=int)
    reference = forms.CharField(max_length=160, label='Bid reference')
    prospect_name = forms.CharField(required=False, max_length=160, label='Client or prospect')
    document = forms.FileField(label='Attach the bid document',
        help_text='Upload a Word or PDF file up to 5 MiB. The original is private.',
        widget=forms.ClearableFileInput(attrs={'accept': '.docx,.pdf'}))
    received_at = forms.DateTimeField(widget=forms.DateTimeInput(
        format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}))
    deadline_status = forms.ChoiceField(label='Deadline in the document', choices=[
        ('unknown', 'Unknown'), ('stated', 'Stated'), ('not_stated', 'Not stated')])
    deadline_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(
        format='%Y-%m-%dT%H:%M:%S', attrs={'type': 'datetime-local', 'step': '1'}),
        help_text='Enter the time only if the attached document states it.')
    submission_method = forms.ChoiceField(required=False, label='Submit by',
        choices=[('', 'Unknown'), *rfp_intake_context.METHODS])
    submission_target = forms.CharField(required=False, max_length=320, label='Submit to',
        help_text='Record only the destination stated in the document.')
    context_attested = forms.BooleanField(required=False,
        label='I confirm the name and submission instructions I entered appear in this source.')

    def __init__(self, authorities, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['authority'].choices = [(scope.pk, scope.tenant) for scope in authorities]
        self.fields['received_at'].label = f'Received at ({timezone.get_current_timezone_name()})'
        self.fields['deadline_at'].label = f'Deadline ({timezone.get_current_timezone_name()})'

    def clean(self):
        data = super().clean()
        if self.files and (set(self.files) != {'document'} or len(self.files.getlist('document')) != 1):
            self.add_error('document', 'Attach one bid document.')
        return data

    def record(self, actor):
        value = self.cleaned_data
        context = rfp_intake_context.SourceContext(value['prospect_name'], value['submission_method'], value['submission_target'])
        return rfp_fresh_intake.record(actor, value['authority'], value['start_key'], value['reference'],
            value['received_at'], value['deadline_status'], value['deadline_at'], value['document'],
            source_context=context, context_attested=value['context_attested'])


@require_http_methods(['GET', 'HEAD', 'POST'])
def create(request):
    from .factory_views import QUEUES

    authorities = list(rfp_fresh_intake.available(request.user).only('pk', 'tenant'))
    if not authorities:
        raise PermissionDenied('Current authority to record a bid in a new workspace is required.')
    bound = request.method == 'POST'
    form = ReceivedBidForm(authorities, request.POST if bound else None, request.FILES if bound else None)
    if bound and form.is_valid():
        try:
            receipt = form.record(request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Bid recorded. Review the original document in the bid workspace.')
            return redirect(f"{reverse('rfp', args=[receipt.rfp.case_id])}?received={receipt.pk}")
    queue = request.GET.get('queue', 'needs_me')
    if queue not in QUEUES:
        queue = 'needs_me'
    result = render(request, 'factory/fresh_bid_intake.html', {
        'form': form, 'definition': rfp_fresh_intake.LINE, 'queue': queue, 'q': request.GET.get('q', '').strip()[:120],
    })
    result['Cache-Control'] = 'no-store'
    return result
