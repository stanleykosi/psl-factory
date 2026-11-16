from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError,PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError,transaction
from django.db.models import Count, Q
from django.shortcuts import render,redirect
from django.http import JsonResponse
from apps.core.views import accessible_case
from . import intake as d
from .intake_models import AccessChange
from .intake_models import TenantAuthority
from .models import Grant

class NewCase(forms.Form):
    tenant=forms.ChoiceField(label='Organization')
    reference=forms.SlugField(max_length=100, label='Reference')
    title=forms.CharField(max_length=240, label='Workspace name')
    kind=forms.ChoiceField(label='Workspace type', choices=[('project','Project'),('support','Customer support')])

@login_required
def create(request):
    opts=d.options(request.user)
    form=NewCase(request.POST if request.method=='POST' else None)
    form.fields['tenant'].choices=[(v.tenant,v.tenant) for v in opts]
    if request.method=='POST' and form.is_valid():
        try:
            c=d.create_case(request.user,**form.cleaned_data)
            return redirect('case',case_id=c.pk)
        except (ValidationError,IntegrityError) as exc:form.add_error(None,'The intake is invalid or its reference is already used.' if isinstance(exc,IntegrityError) else str(exc))
    return render(request,'identity/intake.html',{'form':form,'available':bool(opts)})

@login_required
@transaction.atomic
def access(request,case_id):
    c=accessible_case(request.user,case_id);cfg=d.current(request.user,c.tenant,'manage_access')
    if c.synthetic != (cfg.value['classification']=='synthetic'):
        raise PermissionDenied('Exact technical classification required')
    class Change(forms.Form):
        subject=forms.IntegerField(min_value=1,label='Existing account ID (active required when granting)')
        action=forms.ChoiceField(choices=[(a,a) for a in cfg.value['allowed_actions']])
        enabled=forms.ChoiceField(choices=[('grant','Grant'),('revoke','Revoke')])
        reason=forms.CharField(max_length=1000,widget=forms.Textarea)
    form=Change(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            d.change_access(request.user,c.pk,v['subject'],v['action'],v['enabled']=='grant',v['reason'])
            messages.success(request,'Record action access change recorded. Business decision roles require their own configured authority.')
            return redirect('case_access',case_id=c.pk)
        except (ValidationError,get_user_model().DoesNotExist) as exc:form.add_error(None,'Select an existing account; granting requires it to be active.' if isinstance(exc,get_user_model().DoesNotExist) else str(exc))
    search=request.GET.get('person','').strip()[:100]
    grants=Grant.objects.filter(case=c,action__in=cfg.value['allowed_actions'])
    if search:
        grants=grants.filter(Q(user__username__icontains=search)|Q(user__first_name__icontains=search)|
                             Q(user__last_name__icontains=search)|Q(user__email__icontains=search))
    accounts=grants.values('user_id','user__username','user__first_name','user__last_name','user__email','user__is_active')
    accounts=accounts.annotate(active_actions=Count('pk',filter=Q(active=True))).order_by('user__username','user_id')
    page=Paginator(accounts,25).get_page(request.GET.get('page'))
    access_by_account={row['user_id']:[] for row in page.object_list}
    for user_id,action in grants.filter(active=True,user_id__in=access_by_account).order_by('action').values_list('user_id','action'):
        access_by_account[user_id].append(action)
    for row in page.object_list:
        row['record_actions']=access_by_account[row['user_id']]
    response=render(request,'identity/access.html',{
        'case':c,'form':form,'search':search,'people':page,
        'staff_access':cfg.value.get('staff_lifecycle',{}),
        'history':AccessChange.objects.filter(case=c,action__in=cfg.value['allowed_actions']).order_by('-pk')[:100],
    })
    response['Cache-Control']='no-store'
    return response

@login_required
def provision(request):
    if not get_user_model().objects.filter(pk=request.user.pk,is_active=True,is_superuser=True).exists():raise PermissionDenied('Technical bootstrap administrator required')
    class Configuration(forms.Form):
        subject=forms.IntegerField(min_value=1,label='Existing account ID (active required when enabling)')
        tenant=forms.CharField(max_length=100)
        value=forms.JSONField(widget=forms.Textarea)
        expires_at=forms.DateTimeField()
        enabled=forms.BooleanField(required=False,initial=True)
        reason=forms.CharField(max_length=1000)
    form=Configuration(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        v=form.cleaned_data
        try:
            subject=get_user_model().objects.get(pk=v.pop('subject'),is_active=True)
            d.provision(request.user,subject,**v)
            messages.success(request,'Technical delegation version recorded. Business authority remains separate.')
            return redirect('tenant_access')
        except (ValidationError,get_user_model().DoesNotExist) as exc:form.add_error(None,str(exc))
    import json
    return render(request,'identity/tenant.html',{'form':form,'schema':json.dumps(d.SCHEMA,indent=2),'history':TenantAuthority.objects.order_by('-pk')[:100]})

@login_required
def investigate(request,case_id):
    from apps.agents.intake import investigate
    accessible_case(request.user,case_id)
    return JsonResponse(investigate(request.user,case_id),headers={'Cache-Control':'no-store'})
