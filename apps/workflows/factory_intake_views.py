"""Explicit human source instruction, separate from worker replacement or business approval."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.shortcuts import get_object_or_404,render,redirect
from django.urls import reverse
from apps.core.models import Evidence
from apps.core.evidence_access import public_evidence
from . import factory_delivery as service


class InstructionForm(forms.Form):
    revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    case_revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    packet=forms.CharField(widget=forms.HiddenInput,min_length=64,max_length=64)
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Project evidence supporting this instruction')
    reason=forms.CharField(max_length=2000,widget=forms.Textarea,label='Why you are taking responsibility for the current instruction')


@login_required
def review(request,work_id):
    from .factory_views import visible
    from .factory import access
    work=get_object_or_404(visible(request.user).filter(definition__in=[service.DEFINITION,'delivery-hypercare/v1']),pk=work_id)
    access(request.user,work.case,'factory.manage',work.definition)
    finding='';packet=None
    try:_,packet=service.reaffirmation(request.user,work)
    except ValidationError as exc:finding='; '.join(exc.messages)
    form=InstructionForm(request.POST if request.method=='POST' else None,initial={
        'revision':work.revision,'case_revision':work.case.revision,'packet':packet})
    form.fields['evidence'].queryset=public_evidence(Evidence.objects.filter(case=work.case)).order_by('-pk')
    form.fields['evidence'].label_from_instance=lambda e:e.kind.replace('_',' ')+' · version '+str(e.version)
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        try:service.reaffirm(request.user,work.pk,d['revision'],d['case_revision'],d['evidence'].pk,d['reason'],d['packet'])
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,'Fresh project instruction recorded. Review the current worker and permitted next action.')
            return redirect(reverse('factory_detail',args=[work.pk]))
    response=render(request,'factory/intake_instruction.html',{'case':work.case,'work':work,'form':form,'packet':packet,'finding':finding})
    response['Cache-Control']='no-store';return response
