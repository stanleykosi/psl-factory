"""Human-owned coordinator configuration; no implicit appointment or external activation."""
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.shortcuts import get_object_or_404,render,redirect
from django.utils import timezone
from apps.core.models import Evidence
from apps.identity.services import require,visible_cases
from apps.policy.models import Configuration,ScopeApplication
from apps.policy.operator_drafts import draft_operator_policy
from apps.policy.services import reference_values,transition
from apps.policy.factory_coordinator_validators import COMPONENT,SCOPE
from django.views.decorators.http import require_POST

@login_required
@require_POST
def reconcile(request,work_id):
    from .factory_views import visible
    from apps.agents.factory_coordinator import reconcile as lookup
    from django.urls import reverse
    work=get_object_or_404(visible(request.user, candidates=[work_id]),pk=work_id)
    try:lookup(request.user,work.pk,int(request.POST.get('revision','0')))
    except (ValidationError,ValueError) as exc:
        messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Use the current work revision.')
    else:messages.success(request,'Original planning response checked. Inspect the current work and receipt state.')
    return redirect(reverse('factory_detail',args=[work.pk]))

class CoordinatorForm(forms.Form):
    planner_id=forms.ModelChoiceField(queryset=get_user_model().objects.none(),required=False,label='Accountable person')
    evidence=forms.ModelChoiceField(queryset=Evidence.objects.none(),label='Recorded configuration decision')
    def __init__(self,actor,case,*args,**kwargs):
        super().__init__(*args,**kwargs)
        people=get_user_model().objects.filter(is_active=True)
        for action in ['case.read','factory.read','factory.execute']:people=people.filter(grant__case=case,grant__active=True,grant__action=action)
        self.fields['planner_id'].queryset=people.distinct().order_by('username')
        self.fields['evidence'].queryset=Evidence.objects.filter(case=case,kind='policy_decision').order_by('-pk')

def origin_access(actor,config):
    source=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=config).first()
    if source:
        from apps.policy.scopes import authorized
        authorized(actor,source.source.configuration.case,'policy.read')

@login_required
def configuration(request,case_id):
    case=get_object_or_404(visible_cases(request.user),pk=case_id)
    for action in ['case.read','factory.read','policy.configure']:require(request.user,case,action)
    form=CoordinatorForm(request.user,case,request.POST if request.method=='POST' and request.POST.get('action')=='draft' else None)
    if request.method=='POST':
        if request.POST.get('action')=='draft' and form.is_valid():
            value=dict(form.cleaned_data);proof=value.pop('evidence')
            person = value['planner_id']
            value.update(planner_id=person.pk if person else None, contract_id=None,
                         mode='openrouter_coordination_v1', data_scope=SCOPE, max_output_chars=2048)
            try:draft_operator_policy(request.user,case.pk,COMPONENT,value,proof.pk,timezone.now())
            except ValidationError as exc:form.add_error(None,exc)
            else:messages.success(request,'Coordination draft saved. Review and activate it separately.');return redirect(request.path)
        elif request.POST.get('action')=='transition':
            try:pk=int(request.POST.get('configuration','0'))
            except ValueError:pk=0
            config=get_object_or_404(Configuration,case=case,component=COMPONENT,pk=pk);origin_access(request.user,config)
            try:transition(request.user,config.pk,request.POST.get('state'))
            except ValidationError as exc:messages.error(request,'; '.join(exc.messages))
            return redirect(request.path)
    versions=list(Configuration.objects.filter(case=case,component=COMPONENT).prefetch_related('states').order_by('-revision'))
    for config in versions:
        origin_access(request.user,config);config.settings_value=reference_values(config)[0]
        state=config.states.order_by('-pk').first().state
        config.can_validate=state=='draft'
        try:require(request.user,case,'policy.activate');can_activate=True
        except PermissionDenied:can_activate=False
        config.can_activate=can_activate and state=='validated';config.can_revoke=can_activate and state=='active'
    response=render(request,'factory/coordinator_configuration.html',{'case':case,'form':form,'versions':versions})
    response['Cache-Control']='no-store';return response
