from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.db.models import Count,Exists,OuterRef,Q,Subquery
from django.shortcuts import redirect,render
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_safe

from apps.core.evidence_access import public_evidence
from apps.identity.models import Grant
from . import staff
from . import staff_accounts as domain
from .intake_models import TenantAuthority
from .staff_models import StaffInvitation
from .team_models import StaffMembership


@login_required
@require_safe
@never_cache
def roster(request):
    search=request.GET.get('q','').strip()[:120]
    status=request.GET.get('status','all')
    if status not in ['all','active','inactive']:status='all'
    data=roster_projection(request.user,search,status,request.GET.get('page'),request.GET.get('invitations_page'))
    return render(request,'identity/staff_roster.html',data)


def roster_projection(actor,search,status,people_page,invitations_page):
    cases=domain.manageable_cases(actor)
    people=get_user_model().objects.filter(Q(grant__case__in=cases)|Q(staffmembership__case__in=cases)).distinct()
    if search:people=people.filter(Q(username__icontains=search)|Q(first_name__icontains=search)|
                                    Q(last_name__icontains=search)|Q(email__icontains=search))
    if status!='all':people=people.filter(is_active=status=='active')
    first_scope=Grant.objects.filter(case__in=cases,user_id=OuterRef('pk'),active=True).order_by('case__title','case_id')
    people=people.annotate(first_profile_case=Subquery(first_scope.values('case_id')[:1]))
    page=Paginator(people.only('id','username','first_name','last_name','email','is_active','is_staff',
                              'is_superuser','last_login','password').order_by('username','pk'),25).get_page(people_page)
    counts=dict(Grant.objects.filter(case__in=cases,user_id__in=[u.pk for u in page],active=True).values(
        'user_id').annotate(count=Count('case_id',distinct=True)).values_list('user_id','count'))
    from .staff_profiles import binding_labels
    from .teams import scope_label

    labels=binding_labels([(u.first_profile_case,u.pk) for u in page if u.first_profile_case])
    roles = {}
    for membership in StaffMembership.objects.filter(case__in=cases,user_id__in=[u.pk for u in page],active=True).select_related(
            'team').order_by('case__title','pk'):
        roles.setdefault(membership.user_id,[]).append(membership)
    for user in page:
        scoped = roles.get(user.pk,[])
        user.managed_workspace_count=counts.get(user.pk,0)+len(scoped)
        user.first_profile_label=(scope_label(scoped[0].role,scoped[0].mode) if scoped
                                  else labels.get((user.first_profile_case,user.pk),'No current access'))
        user.departure_available=(user.is_active and not scoped and user.pk!=actor.pk
                                  and not(user.is_staff or user.is_superuser))
        user.reactivation_available=not user.is_active and not(user.is_staff or user.is_superuser)
    later=StaffInvitation.objects.filter(case_id=OuterRef('case_id'),username=OuterRef('username'),number__gt=OuterRef('number'))
    pending=StaffInvitation.objects.filter(case__in=cases,admission__isnull=True).annotate(
        superseded=Exists(later)).filter(superseded=False)
    if search:pending=pending.filter(Q(name__icontains=search)|Q(username__icontains=search)|Q(email__icontains=search))
    invitations=Paginator(pending.select_related('case').only('id','case_id','case__title','name','username','email',
        'profile_label','role_scope','created_at','expires_at','number').order_by('-pk'),25).get_page(invitations_page)
    return {'people':page,'search':search,'status':status,
            'invitations':invitations,'observed_at':timezone.now(),'available':cases.exists()}


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
            handover = staff.handover_links(prepared['actor'], case, prepared['person']) if scope['handover_pending'] else None
            self.groups.append({'case':case,'rows':rows,'evidence':self[proof_name] if items else None,'handover':handover})

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
    allow_profile_edit=forms.NullBooleanField(label='May change named workspace access profiles')
    allow_reactivation=forms.NullBooleanField(label='May reactivate accounts after fresh access review')
    reason=forms.CharField(max_length=1000,label='Reason and authority reference',widget=forms.Textarea(attrs={'rows':3}))


class ReactivationForm(forms.Form):
    fingerprint=forms.CharField(widget=forms.HiddenInput,min_length=64,max_length=64)
    operation=forms.UUIDField(widget=forms.HiddenInput)
    reason=forms.CharField(max_length=1000,label='Reason for restoring sign-in',widget=forms.Textarea(attrs={'rows':3}))
    confirmed=forms.BooleanField(label='I reviewed every listed workspace. Previous access and project roles will not be restored.')


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def reactivate(request,person_id):
    from . import staff_reactivation
    from apps.agents.staff_accounts import investigate_restoration
    person=domain.account(request.user,person_id)
    prepared=None;held=None;form=None
    try:prepared=investigate_restoration(request.user,person_id)
    except PermissionDenied:held='Restoring this account needs current delegation and role-source access in every affected workspace.'
    except ValidationError as exc:held=exc.messages[0]
    if prepared:
        form=ReactivationForm(request.POST if request.method=='POST' else None,
            initial={'fingerprint':prepared['fingerprint'],'operation':uuid4()})
        if prepared['blocked']:held=' '.join(prepared['blocked'])
    if request.method=='POST' and not held and form and form.is_valid():
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Use the displayed restoration review.')
            staff_reactivation.restore(request.user,person_id,form.cleaned_data['fingerprint'],form.cleaned_data['reason'],
                                        form.cleaned_data['operation'])
        except PermissionDenied:form.add_error(None,'Current delegation or role-source access changed. Review again.')
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,'Sign-in restored. Allocate fresh workspace access before this person resumes work.')
            return redirect('staff_person',person_id)
    return render(request,'identity/staff_reactivation.html',{'person':person,'prepared':prepared,'held':held,'form':form})


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
