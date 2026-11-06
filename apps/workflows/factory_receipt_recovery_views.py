"""Human-only configuration and original receipt destination review."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from apps.core.models import Evidence
from apps.core.services import lock_case
from apps.identity.services import require,visible_cases
from apps.policy.document_validators import ROLES
from apps.policy.factory_receipt_recovery_validators import COMPONENT,METHOD
from apps.policy.models import Configuration
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import reference_values,transition
from . import factory_receipt_recovery as service
from .readiness_models import IntegrationContract


class SettingsForm(forms.Form):
    revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    base=forms.IntegerField(widget=forms.HiddenInput,min_value=0)
    method=forms.ChoiceField(required=False,choices=[('','Not decided'),(METHOD,'Look up the original response from the same provider')])
    reviewer_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Receipt recovery reviewer')
    review_role=forms.ChoiceField(required=False,choices=[('','Not decided'),*[(r,r) for r in ROLES]],label='Required responsibility')
    independent_of_requester=forms.ChoiceField(required=False,choices=[('','Not decided'),('yes','Yes'),('no','No')],label='Reviewer must differ from the original requester')
    valid_from=forms.DateTimeField(required=False,label='Authority starts')
    valid_until=forms.DateTimeField(required=False,label='Authority ends')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Human authority evidence')
    def __init__(self,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['reviewer_id'].queryset=get_user_model().objects.filter(is_active=True,grant__case=case,grant__active=True,grant__action='integration.review').distinct().order_by('pk')
        self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='policy_decision').order_by('-pk')
    def value(self):
        d=self.cleaned_data
        return {'method':d['method'] or None,'reviewer_id':d['reviewer_id'].pk if d['reviewer_id'] else None,
            'review_role':d['review_role'] or None,'independent_of_requester':{'yes':True,'no':False}.get(d['independent_of_requester']),
            'valid_from':d['valid_from'].isoformat() if d['valid_from'] else None,
            'valid_until':d['valid_until'].isoformat() if d['valid_until'] else None}


def response(request,template,context):
    result=render(request,template,context);result['Cache-Control']='no-store';return result


@login_required
def configuration(request,case_id):
    case=get_object_or_404(visible_cases(request.user),pk=case_id);require(request.user,case,'policy.read')
    versions=Configuration.objects.filter(case=case,component=COMPONENT).order_by('-revision');latest=versions.first()
    initial={'revision':case.revision,'base':latest.pk if latest else 0}
    if latest:
        value=reference_values(latest)[0];initial.update(value)
        initial['independent_of_requester']='yes' if value['independent_of_requester'] is True else 'no' if value['independent_of_requester'] is False else ''
    form=SettingsForm(case,request.POST if request.method=='POST' and request.POST.get('action')=='draft' else None,initial=initial)
    if request.method=='POST':
        try:
            if request.POST.get('action')=='draft' and form.is_valid():
                with transaction.atomic():
                    locked=lock_case(request.user,case.pk,'policy.configure',form.cleaned_data['revision'])
                    head=Configuration.objects.filter(case=case,component=COMPONENT).order_by('-revision').first()
                    if form.cleaned_data['base']!=(head.pk if head else 0):raise ValidationError('STALE_VERSION: refresh current recovery settings')
                    draft_operator_policy(request.user,locked.pk,COMPONENT,form.value(),form.cleaned_data['evidence'].pk,timezone.now())
                return redirect(request.path)
            elif request.POST.get('action') in ['validated','active','revoked']:
                try:configuration_id=int(request.POST.get('configuration',''))
                except (ValueError,TypeError):raise ValidationError('Choose an exact settings revision') from None
                config=get_object_or_404(versions,pk=configuration_id)
                transition(request.user,config.pk,request.POST['action']);return redirect(request.path)
        except ValidationError as exc:
            if form.is_bound:form.add_error(None,exc)
            else:messages.error(request,'; '.join(exc.messages))
    return response(request,'factory/receipt_recovery_settings.html',{'case':case,'form':form,'versions':versions})


class ReviewForm(forms.Form):
    revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    case_revision=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    attempt=forms.IntegerField(widget=forms.HiddenInput,min_value=1)
    contract=forms.ModelChoiceField(queryset=IntegrationContract.objects.none(),label='Reviewed successor provider contract')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Human authority evidence')
    reason=forms.CharField(max_length=2000,widget=forms.Textarea,label='Why these credentials can read the original response')


@login_required
def review(request,work_id):
    from .factory_views import visible
    from .factory import access
    from . import readiness
    from apps.agents.factory_coordinator import pending
    work=get_object_or_404(visible(request.user),pk=work_id);access(request.user,work.case,'factory.manage',work.definition)
    readiness.readable(request.user,work.case,True)
    attempt=pending(work)
    form=ReviewForm(request.POST if request.method=='POST' else None,initial={'revision':work.revision,'case_revision':work.case.revision,'attempt':attempt.pk if attempt else None})
    contracts=readiness.visible_contracts(request.user,work.case)
    form.fields['contract'].queryset=contracts.filter(payload__kind='provider').order_by('reference','version')
    form.fields['evidence'].queryset=Evidence.objects.filter(case=work.case,kind='policy_decision').order_by('-pk')
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data
        try:service.review(request.user,work.pk,d['revision'],d['case_revision'],d['attempt'],d['contract'].pk,d['evidence'].pk,d['reason'])
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,'Receipt recovery reviewed. A separate lookup can check the original response; no new request was sent.')
            return redirect(reverse('factory_detail',args=[work.pk]))
    return response(request,'factory/receipt_recovery_review.html',{'case':work.case,'work':work,'attempt':attempt,'form':form})
