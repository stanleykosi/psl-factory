"""HR reviews a correction reference and a successor it is authorized to supply."""
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.models import Evidence
from apps.core.views import accessible_case
from apps.identity.services import require

from . import hrfinance as hr
from .hrfinance_models import HRReadSnapshot
from .payroll_models import PayrollHRFollowup


def reviewer(actor, case):
    for action in ('hrfinance.read', 'hrfinance.respond'):
        require(actor, case, action)
    try:
        hr.authority(actor, case, 'respond')
    except ValidationError as exc:
        raise PermissionDenied('A configured HR correction reviewer is required') from exc


class CorrectionDecision(forms.Form):
    verdict = forms.ChoiceField(choices=[('approve', 'Approve with a corrected HR export'), ('return', 'Return for clarification'),
                                        ('reject', 'Reject')])
    successor = forms.ModelChoiceField(queryset=HRReadSnapshot.objects.none(), required=False, label='Corrected HR export')
    evidence = forms.ModelChoiceField(queryset=Evidence.objects.none(), label='HR decision evidence')
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    operation_key = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, case, job, data=None):
        super().__init__(data, initial={'revision': case.revision, 'operation_key': uuid4()})
        evidence = case.evidence.filter(kind='hr_correction_response').order_by('-pk').values('pk')[:30]
        self.fields['evidence'].queryset = case.evidence.filter(pk__in=evidence).defer('body').order_by('-pk')
        snapshots = HRReadSnapshot.objects.filter(contract_id=job.contract_id, pk__gt=job.snapshot_id, status='accepted')
        self.fields['successor'].queryset = snapshots.defer('payload').order_by('-pk')


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def desk(request, case_id, followup_id=None):
    case = accessible_case(request.user, case_id)
    reviewer(request.user, case)
    links = PayrollHRFollowup.objects.filter(run__request__case=case, record__contract__need__case=case).select_related('record')
    rows = list(links.order_by('-pk')[:30])
    job = get_object_or_404(links, pk=followup_id).record if followup_id is not None else None
    decision = hr.correction_disposition(job).order_by('-pk').first() if job is not None else None
    form = CorrectionDecision(case, job, request.POST if request.method == 'POST' else None) if job else None
    if request.method == 'POST':
        if form is None:
            raise PermissionDenied('Choose the exact payroll correction')
        if form.is_valid():
            values = form.cleaned_data
            successor = values['successor']
            try:
                hr.decide_correction(request.user, case.pk, job.pk, values['verdict'], successor.pk if successor else None,
                                     str(values['operation_key']), values['evidence'].pk, values['revision'])
            except ValidationError:
                form.add_error(None, 'The decision is held. Check the current request, evidence and corrected export.')
            else:
                messages.success(request, 'HR decision recorded.')
                return redirect('design_hr_payroll_correction', case_id, followup_id)
    return render(request, 'finance/payroll_hr_corrections.html',
                  {'case': case, 'rows': rows, 'job': job, 'decision': decision, 'form': form})
