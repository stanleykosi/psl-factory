from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.identity.actions import ACTIONS
from apps.identity.models import Grant

from . import staff
from .staff_models import StaffInvitation


class InviteForm(forms.Form):
    name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150, label='Sign-in name')
    email = forms.EmailField()
    profile = forms.ChoiceField(label='Account access profile',required=False,choices=[])
    actions = forms.MultipleChoiceField(label='Individual workspace functions',required=False, widget=forms.CheckboxSelectMultiple)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self,configuration,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from .staff_profiles import choices
        self.profiles={p['key']:p for p in choices(configuration)}
        self.fields['profile'].choices=[('', 'Choose a configured profile')]+[(k,p['label']) for k,p in self.profiles.items()]
        self.fields['actions'].choices=[(a,a.replace('.', ' · ').replace('_',' ').capitalize())
            for a in sorted(set(configuration.value['allowed_actions'])&set(ACTIONS))]

    def clean(self):
        values=super().clean();key=values.get('profile');actions=values.get('actions',[])
        if key:
            supplied=self.profiles[key]['actions']
            if actions and set(actions)!=set(supplied):self.add_error('actions','Use the selected profile or choose individual functions, not both.')
            values['actions']=list(supplied)
        elif not actions:self.add_error('profile','Choose a configured profile, or review explicit individual workspace functions.')
        return values


class PasswordForm(forms.Form):
    token = forms.CharField(min_length=43, max_length=43, label='Invitation code', widget=forms.PasswordInput)
    password = forms.CharField(max_length=128, label='Choose a password', widget=forms.PasswordInput)
    confirm = forms.CharField(max_length=128, label='Confirm password', widget=forms.PasswordInput)

    def clean(self):
        values = super().clean()
        if values.get('password') != values.get('confirm'):
            self.add_error('confirm', 'The passwords differ.')
        return values


class DepartureForm(forms.Form):
    reason = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={'rows': 4}))
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    def __init__(self, case, items, data=None, *, actor):
        super().__init__(data, initial={'revision': case.revision})
        if items:
            self.fields['evidence'] = forms.ChoiceField(label='Reassignment evidence',
                choices=[(record.pk, str(record)) for record in public_evidence(case.evidence.all()).defer('body').order_by('-pk')[:30]])
            from django.contrib.auth import get_user_model
            from apps.policy.role_assignments import eligibility
            from apps.policy.services import active_component, reference_values

            _, values = staff.role_context(actor, case)
            original = eligibility(case, values, items[0].current.owner_id)
            owners = Grant.objects.filter(case=case, action='action.own', active=True).values('user_id')
            visible = Grant.objects.filter(case=case, action='case.read', active=True).values('user_id')
            accounts = get_user_model().objects.filter(is_active=True, pk__in=owners).filter(pk__in=visible).exclude(
                pk=items[0].current.owner_id)
            allowed = []
            for user in accounts.order_by('username')[:100]:
                current = eligibility(case, values, user.pk)
                if current['eligible_role_bundle'] and set(current['roles']).intersection(original['roles']):
                    allowed.append((user.pk, user.get_full_name() or user.username))
            for item in items:
                self.fields[f'reassign_{item.pk}'] = forms.ChoiceField(choices=allowed, label=item.current.description)


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def invites(request, case_id, invitation_id=None):
    case = accessible_case(request.user, case_id)
    cfg, _ = staff.authority(request.user, case, 'allow_invite')
    old = get_object_or_404(StaffInvitation, case=case, pk=invitation_id) if invitation_id is not None else None
    initial = {'revision': case.revision}
    if old:
        initial.update({key: getattr(old, key) for key in ('name','username','email','actions')})
        from .staff_profiles import choices
        current={p['key']:p for p in choices(cfg)}
        if old.profile_key in current:
            initial.update(profile=old.profile_key,actions=[])
    form = InviteForm(cfg,request.POST if request.method == 'POST' else None, initial=initial)
    invitation_link = None
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        if old and values['username'].strip().lower() != old.username:
            form.add_error('username', 'Use the original sign-in name when renewing this invitation.')
        else:
            try:
                _, token = staff.invite(request.user, case.pk, values['username'], values['name'], values['email'],
                                        values['actions'], values['revision'], preceding=invitation_id,
                                        profile_key=values.get('profile',''))
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                invitation_link = request.build_absolute_uri(reverse('staff_accept_invite'))+'#'+token
    later = StaffInvitation.objects.filter(case=case, username=OuterRef('username'), number__gt=OuterRef('number'))
    rows = StaffInvitation.objects.filter(case=case).annotate(superseded=Exists(later)).select_related('admission').order_by('-pk')[:40]
    response = render(request, 'identity/staff_invites.html', {'case':case,'form':form,'rows':rows,
                      'renewing':old,'invitation_link':invitation_link,'as_of':timezone.now()})
    response['Referrer-Policy'] = 'same-origin'
    return response


@require_http_methods(['GET','HEAD','POST'])
@never_cache
def accept(request):
    form = PasswordForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            staff.accept(form.cleaned_data['token'], form.cleaned_data['password'])
        except PermissionDenied:
            form.add_error('token', 'This invitation is unavailable.')
        except ValidationError as exc:
            form.add_error('password', exc)
        else:
            messages.success(request, 'Your workspace account is ready. Sign in to continue.')
            return redirect('login')
    response = render(request, 'identity/staff_accept.html', {'form':form})
    response['Referrer-Policy'] = 'same-origin'
    return response


@login_required
@require_http_methods(['GET','HEAD','POST'])
@never_cache
def departure(request, case_id, person_id):
    case = accessible_case(request.user, case_id)
    cfg, _ = staff.authority(request.user, case, 'allow_deactivation')
    record = Grant.objects.filter(case=case,user_id=person_id,active=True,
                                  action__in=cfg.value['allowed_actions']).select_related('user').order_by('pk').first()
    if record is None:
        raise Http404
    items = list(staff.open_actions(case, person_id)[:101])
    blocked = None
    try:
        form = DepartureForm(case, items, request.POST if request.method == 'POST' else None, actor=request.user)
    except (ValidationError,PermissionDenied):
        form = None
        blocked = 'Current role assignments are needed to reassign these actions.'
    if form and request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        successors = {item.pk:int(data[f'reassign_{item.pk}']) for item in items}
        try:
            staff.deactivate(request.user, case.pk, person_id, successors, int(data['evidence']) if items else None,
                             data['reason'], data['revision'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Workspace access removed and reassignment history recorded.')
            return redirect('case_access', case.pk)
    return render(request, 'identity/staff_departure.html', {'case':case,'person':record.user,'form':form,'blocked':blocked})
