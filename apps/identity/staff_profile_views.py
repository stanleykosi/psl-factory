from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.paginator import Paginator
from django.forms import formset_factory
from django.shortcuts import get_object_or_404,redirect,render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods,require_safe

from apps.core.views import accessible_case
from . import intake,staff_accounts,staff_profiles
from .intake_models import TenantAuthority
from .models import Grant
from .staff_models import StaffPrimaryRoleChange


@login_required
@require_safe
@never_cache
def person(request,person_id):
    from .teams import memberships, scope_label

    user=staff_accounts.account(request.user,person_id)
    cases=staff_accounts.manageable_cases(request.user).filter(pk__in=Grant.objects.filter(
        user=user).values('case_id')).order_by('title','pk')
    page=Paginator(cases,20).get_page(request.GET.get('page'))
    labels=staff_profiles.labels([c.pk for c in page],user.pk)
    cfgs={c.tenant:c for c in intake.options(request.user,'manage_access')}
    current_reads = set(Grant.objects.filter(user=user, case__in=page.object_list, active=True, action='case.read')
                        .values_list('case_id', flat=True))
    primary = dict(StaffPrimaryRoleChange.objects.filter(user=user, case__in=page.object_list)
                   .order_by('case_id', '-pk').distinct('case_id').values_list('case_id', 'role_name'))
    scoped = {row.case_id:row for row in memberships(user).filter(case__in=page.object_list).select_related('team')}
    delegated = {cfg.tenant: cfg.value for cfg in intake.options(user, 'manage_access')} if user.is_active else {}
    protected = user.is_staff or user.is_superuser or staff_accounts._technical_authority(user)
    for case in page:
        case.account_access_label=labels[case.pk]
        case.can_edit_profile=(user.is_active and user.pk!=request.user.pk and not(user.is_staff or user.is_superuser)
                               and cfgs[case.tenant].value.get('staff_lifecycle',{}).get('allow_profile_edit') is True)
        target_delegation = delegated.get(case.tenant, {})
        is_admin = (case.kind == 'project' and case.pk in current_reads
                    and target_delegation.get('staff_lifecycle', {}).get('allow_profile_edit') is True
                    and case.kind in target_delegation.get('kinds', [])
                    and case.synthetic == (target_delegation.get('classification') == 'synthetic'))
        case.primary_role = ('Admin' if is_admin else primary.get(case.pk)) if user.is_active and case.pk in current_reads else None
        case.can_assign_primary_role = (case.can_edit_profile and not protected and case.pk in current_reads and case.kind == 'project')
        if case.pk in scoped:
            member = scoped[case.pk]
            case.primary_role = scope_label(member.role, member.mode)
            case.account_access_label = member.team.name if member.team else 'Standalone role scope'
            case.can_edit_profile = False
    return render(request,'identity/staff_person.html',{'person':user,'workspaces':page})


class AccessForm(forms.Form):
    profile=forms.ChoiceField(label='Account access profile')
    fingerprint=forms.CharField(widget=forms.HiddenInput,min_length=64,max_length=64)
    operation=forms.UUIDField(widget=forms.HiddenInput)
    reason=forms.CharField(max_length=1000,label='Reason for this change',widget=forms.Textarea(attrs={'rows':3}))
    confirmed=forms.BooleanField(label='I reviewed the new access and any work that must be handed over.')

    def __init__(self,prepared,data=None):
        super().__init__(data,initial={'fingerprint':prepared['fingerprint'],'operation':uuid4()})
        self.fields['profile'].choices=[('', 'Choose a current profile')]+[(p['key'],p['label']) for p in prepared['profiles']]


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def access(request,case_id,person_id):
    case=accessible_case(request.user,case_id)
    prepared=staff_profiles.review(request.user,case,person_id)
    form=AccessForm(prepared,request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:raise ValidationError('Use the displayed access review.')
            staff_profiles.apply(request.user,case.pk,person_id,form.cleaned_data['profile'],form.cleaned_data['fingerprint'],
                                 form.cleaned_data['reason'],form.cleaned_data['operation'])
        except (ValidationError,PermissionDenied) as exc:
            form.add_error(None,exc if isinstance(exc,ValidationError) else 'Current access delegation changed. Review again.')
        else:
            messages.success(request,'Account access updated. Project decision roles are reviewed separately.')
            return redirect('staff_person',person_id)
    current=staff_profiles.labels([case.pk],person_id)[case.pk]
    return render(request,'identity/staff_profile_access.html',{'case':case,'person':prepared['person'],
        'form':form,'profiles':prepared['profiles'],'current_access':current})


class ProfileForm(forms.Form):
    key=forms.SlugField(max_length=50,label='Stable profile reference')
    label=forms.CharField(max_length=80,label='Profile name')
    actions=forms.MultipleChoiceField(label='Allowed workspace functions',widget=forms.SelectMultiple(attrs={'size':8}))

    def __init__(self,*args,allowed,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['actions'].choices=[(a,a.replace('.', ' · ').replace('_',' ').capitalize()) for a in sorted(allowed)]

class ConfigurationForm(forms.Form):
    authority=forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    undecided=forms.BooleanField(required=False,label='Profile definitions are still undecided')
    reason=forms.CharField(max_length=1000,label='Reason and authority reference',widget=forms.Textarea(attrs={'rows':3}))


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def configure(request,authority_id):
    if not get_user_model().objects.filter(pk=request.user.pk,is_active=True,is_superuser=True).exists():
        raise PermissionDenied('Current technical bootstrap administrator required.')
    cfg=get_object_or_404(TenantAuthority.objects.select_related('user'),pk=authority_id)
    profiles=cfg.value.get('staff_lifecycle',{}).get('profiles')
    data=request.POST if request.method=='POST' else None
    form=ConfigurationForm(data,initial={'authority':cfg.pk,'undecided':profiles is None})
    forms_type=formset_factory(ProfileForm,extra=1,max_num=30,validate_max=True,absolute_max=31,can_delete=True)
    rows=forms_type(data,initial=profiles or [],form_kwargs={'allowed':cfg.value['allowed_actions']})
    if request.method=='POST' and form.is_valid() and rows.is_valid():
        values=[{k:r.cleaned_data[k] for k in ['key','label','actions']} for r in rows
                if r.cleaned_data and not r.cleaned_data.get('DELETE')]
        try:
            if form.cleaned_data['authority']!=cfg.pk:raise ValidationError('Use this exact delegation version.')
            if rows.initial_form_count()!=len(profiles or []) or rows.total_form_count()<len(profiles or []):
                raise ValidationError('Review every existing profile and explicitly mark any removal.')
            if form.cleaned_data['undecided'] and values:raise ValidationError('Remove the profile definitions before marking them undecided.')
            saved=staff_profiles.configure(request.user,cfg.pk,None if form.cleaned_data['undecided'] else values,
                                           form.cleaned_data['reason'])
        except ValidationError as exc:form.add_error(None,exc)
        else:
            messages.success(request,'Named access profiles saved as a new delegation version. Existing access was retained.')
            return redirect('staff_profile_configuration',saved.pk)
    return render(request,'identity/staff_profile_configuration.html',{'configuration':cfg,'form':form,'profiles':rows})
