from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.db.models import Count,Q
from django.shortcuts import redirect,render
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_safe

from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from . import staff_accounts as domain
from .intake_models import TenantAuthority


@login_required
@require_safe
@never_cache
def roster(request):
    cases=domain.manageable_cases(request.user)
    search=request.GET.get('q','').strip()[:120]
    status=request.GET.get('status','all')
    if status not in ['all','active','inactive']:status='all'
    people=get_user_model().objects.filter(grant__case__in=cases).distinct()
    if search:people=people.filter(Q(username__icontains=search)|Q(first_name__icontains=search)|
                                    Q(last_name__icontains=search)|Q(email__icontains=search))
    if status!='all':people=people.filter(is_active=status=='active')
    page=Paginator(people.only('id','username','first_name','last_name','email','is_active','is_staff',
                              'is_superuser','last_login','password').order_by('username','pk'),25).get_page(request.GET.get('page'))
    counts=dict(Grant.objects.filter(case__in=cases,user_id__in=[u.pk for u in page],active=True).values(
        'user_id').annotate(count=Count('case_id',distinct=True)).values_list('user_id','count'))
    for user in page:
        user.managed_workspace_count=counts.get(user.pk,0)
        user.departure_available=user.is_active and user.pk!=request.user.pk and not(user.is_staff or user.is_superuser)
    return render(request,'identity/staff_roster.html',{'people':page,'search':search,'status':status,
        'observed_at':timezone.now(),'available':cases.exists()})


class DepartureForm(forms.Form):
    fingerprint=forms.CharField(widget=forms.HiddenInput,min_length=64,max_length=64)
    operation=forms.UUIDField(widget=forms.HiddenInput)
    reason=forms.CharField(label='Reason',max_length=1000,widget=forms.Textarea(attrs={'rows':3}))
    confirmed=forms.BooleanField(label='I reviewed all listed workspaces and action handovers.')

    def __init__(self,prepared,data=None):
        super().__init__(data,initial={'fingerprint':prepared['fingerprint'],'operation':uuid4()})
        self.groups=[]
        from .staff_views import DepartureForm as WorkspaceDeparture
        for scope in prepared['scopes']:
            case=scope['case'];items=scope['items']
            prefix='scope_'+case.pk.hex
            proof_name=prefix+'_evidence'
            if items:
                self.fields[proof_name]=forms.ChoiceField(label='Handover evidence',choices=[(p.pk,str(p)) for p in
                    public_evidence(case.evidence.all()).defer('body').order_by('-pk')[:50]])
                try:workspace=WorkspaceDeparture(case,items,actor=prepared['actor'])
                except (ValidationError,PermissionDenied):workspace=None
            rows=[]
            unassigned=scope['authority'].value['staff_lifecycle'].get('allow_unassigned_departure') is True
            for item in items:
                name=f'action_{item.pk}'
                choices=list(workspace.fields[f'reassign_{item.pk}'].choices) if workspace else []
                self.fields[name]=forms.ChoiceField(label=item.current.description,required=not unassigned,
                    choices=[('', 'Owner needed — no successor' if unassigned else 'Choose a current successor')]+choices)
                rows.append({'item':item,'field':self[name]})
            self.groups.append({'case':case,'rows':rows,'evidence':self[proof_name] if items else None})

    def command(self):
        replacements={}
        evidence={}
        for group in self.groups:
            if group['rows']:evidence[str(group['case'].pk)]=int(self.cleaned_data[group['evidence'].name])
            for row in group['rows']:
                value=self.cleaned_data[row['field'].name]
                replacements[row['item'].pk]=int(value) if value else None
        return replacements,evidence


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def departure(request,person_id):
    person=domain.account(request.user,person_id)
    prepared=None;held=None;form=None
    try:prepared=domain.prepare(request.user,person_id)
    except PermissionDenied:held='This account needs its authorised administrator in every affected workspace.'
    except ValidationError as exc:held=exc.messages[0]
    if prepared:
        form=DepartureForm(prepared,request.POST if request.method=='POST' else None)
        if prepared['blocked']:held=' '.join(prepared['blocked'])
    if request.method=='POST' and not held and form and form.is_valid():
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:
                raise ValidationError('Use the displayed account review.')
            replacements,evidence=form.command()
            domain.deactivate(request.user,person_id,form.cleaned_data['fingerprint'],replacements,evidence,
                              form.cleaned_data['reason'],form.cleaned_data['operation'])
        except PermissionDenied:form.add_error(None,'Current account delegation changed. Review all workspaces again.')
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,'Account deactivated. Access was removed from every reviewed workspace; history is retained.')
            for scope in prepared['scopes']:
                messages.info(request,format_html('<a href="{}">Review {} action handover</a>',
                    reverse('design_project_tab',args=[scope['case'].pk,'actions']),scope['case'].title))
            return redirect('staff_roster')
    return render(request,'identity/staff_account_departure.html',{'person':person,'prepared':prepared,
                  'form':form,'held':held})


class ControlsForm(forms.Form):
    authority=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    allow_roster=forms.NullBooleanField(label='May view staff in managed workspaces')
    allow_account_deactivation=forms.NullBooleanField(label='May deactivate whole accounts across all managed workspaces')
    allow_unassigned_departure=forms.NullBooleanField(label='May leave departing staff actions marked Owner needed')
    reason=forms.CharField(max_length=1000,label='Reason and authority reference',widget=forms.Textarea(attrs={'rows':3}))


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def controls(request,authority_id):
    if not get_user_model().objects.filter(pk=request.user.pk,is_active=True,is_superuser=True).exists():
        raise PermissionDenied('Current technical bootstrap administrator required.')
    from django.shortcuts import get_object_or_404
    configuration=get_object_or_404(TenantAuthority.objects.select_related('user'),pk=authority_id)
    initial={'authority':configuration.pk,**{k:configuration.value.get('staff_lifecycle',{}).get(k) for k in domain.CONTROL_KEYS}}
    form=ControlsForm(request.POST if request.method=='POST' else None,initial=initial)
    if request.method=='POST' and form.is_valid():
        try:
            if form.cleaned_data['authority']!=configuration.pk or set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:
                raise ValidationError('Use this exact delegation version.')
            saved=domain.configure_controls(request.user,configuration.pk,
                {k:form.cleaned_data[k] for k in domain.CONTROL_KEYS},form.cleaned_data['reason'])
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,'Account controls saved as a new delegation version. Business decision roles are separate.')
            return redirect('staff_account_controls',saved.pk)
    history=TenantAuthority.objects.filter(user=configuration.user,tenant=configuration.tenant).only(
        'id','version','created_at','reason').order_by('-version')[:30]
    return render(request,'identity/staff_account_controls.html',{'configuration':configuration,'form':form,'history':history})
