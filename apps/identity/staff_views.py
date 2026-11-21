from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.core.views import accessible_case
from apps.identity.models import Grant

from . import primary_roles, staff, teams
from .staff_models import StaffInvitation
from .team_models import StaffTeam


class InviteForm(forms.Form):
    name = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150,label='Sign-in name')
    email = forms.EmailField()
    revision = forms.IntegerField(min_value=1,widget=forms.HiddenInput)
    project_review = forms.CharField(widget=forms.HiddenInput,max_length=1024)

    def __init__(self,*args,case,lead,**kwargs):
        super().__init__(*args,**kwargs)
        if lead:
            return
        self.fields['base_role'] = forms.ChoiceField(label='Base role',choices=[
            ('','Choose a base role'),*((role['key'],role['name']) for role in primary_roles.built_ins())])
        self.fields['role_mode'] = forms.ChoiceField(label='Work scope',choices=[
            ('','Choose a work scope'),*((mode,teams.MODE_LABELS[mode]) for mode in ('lead','standalone'))])
        self.fields['team'] = forms.ModelChoiceField(label='Team',required=False,
            queryset=StaffTeam.objects.filter(case=case).order_by('name','pk'))
        self.fields['team'].label_from_instance = lambda team: team.name


class PasswordForm(forms.Form):
    token = forms.CharField(min_length=43, max_length=43, label='Invitation code', widget=forms.PasswordInput)
    password = forms.CharField(max_length=128, label='Choose a password', widget=forms.PasswordInput)
    confirm = forms.CharField(max_length=128, label='Confirm password', widget=forms.PasswordInput)
    review_alerts = forms.BooleanField(required=False, label='Review optional WhatsApp alerts after signing in',
                                      help_text='Alerts are sent only to a verified number.')

    def clean(self):
        values = super().clean()
        if values.get('password') != values.get('confirm'):
            self.add_error('confirm', 'The passwords differ.')
        return values


class InvitationPreviewForm(forms.Form):
    token = forms.CharField(min_length=43, max_length=43, widget=forms.PasswordInput)


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
def invites(request, case_id, invitation_id=None, team_id=None):
    lead = None
    if team_id is None:
        case = accessible_case(request.user,case_id)
        cfg,_ = teams.invitation_authority(request.user,case,'lead')
    else:
        lead = get_object_or_404(teams.memberships(request.user).select_related('case','team'),
                                 case_id=case_id,team_id=team_id,mode='lead')
        case = lead.case
        cfg,_ = teams.invitation_authority(request.user,case,'member',team_id=team_id,membership_id=lead.pk)
    rows = StaffInvitation.objects.filter(case=case)
    if lead:
        rows = rows.filter(role_scope__team_id=team_id,role_scope__mode='member')
    old = get_object_or_404(rows,pk=invitation_id) if invitation_id is not None else None
    review = {'actor':request.user.pk,'case':str(case.pk),'authority':cfg.pk,'lead':lead.pk if lead else None}
    initial = {'revision':case.revision,'project_review':signing.dumps(review,salt='staff.role-invitation')}
    if old:
        initial.update({key:getattr(old,key) for key in ('name','username','email')})
        if old.role_scope and not lead:
            initial.update(base_role=old.role_scope['role'],role_mode=old.role_scope['mode'],team=old.role_scope['team_id'])
    form = InviteForm(request.POST if request.method=='POST' else None,case=case,lead=lead,initial=initial)
    invitation_link = None
    if request.method=='POST' and form.is_valid():
        values = form.cleaned_data
        try:
            if set(request.POST)-set(form.fields)-{'csrfmiddlewaretoken'}:
                raise ValidationError('Review the current role invitation form before submitting.')
            if signing.loads(values['project_review'],salt='staff.role-invitation',max_age=900)!=review:
                raise ValidationError('Invitation authority changed. Review the current role and team.')
            if old and values['username'].strip().lower()!=old.username:
                raise ValidationError('Use the original sign-in name when renewing an invitation.')
            if lead:
                role, mode, target_team = lead.role, 'member', lead.team_id
            else:
                role, mode = values['base_role'], values['role_mode']
                target_team = values['team'].pk if values['team'] else None
            _,token = staff.invite_person(request.user,case.pk,values['username'],values['name'],values['email'],
                values['revision'],role=role,mode=mode,team_id=target_team,preceding=invitation_id)
        except signing.BadSignature:
            form.add_error(None,'Reload and review the invitation before submitting.')
        except (PermissionDenied,ValidationError) as error:
            form.add_error(None,error)
        else:
            invitation_link = request.build_absolute_uri(reverse('staff_accept_invite'))+'#'+token
    later = StaffInvitation.objects.filter(case=case,username=OuterRef('username'),number__gt=OuterRef('number'))
    rows = rows.annotate(superseded=Exists(later)).select_related('admission').order_by('-pk')[:40]
    response = render(request,'identity/staff_invites.html',{'case':case,'form':form,'rows':rows,'lead':lead,
        'renewing':old,'invitation_link':invitation_link,'as_of':timezone.now()})
    response['Referrer-Policy'] = 'same-origin'
    return response


@require_http_methods(['GET','HEAD','POST'])
@never_cache
@sensitive_post_parameters('token', 'password', 'confirm')
def accept(request):
    preview = None
    problem = None
    preview_request = request.method == 'POST' and request.POST.get('action') == 'preview'
    form = PasswordForm(request.POST if request.method == 'POST' and not preview_request else None)
    if preview_request:
        code_form = InvitationPreviewForm(request.POST)
        try:
            if not code_form.is_valid():
                raise ValidationError('This invitation is unavailable.')
            token = code_form.cleaned_data['token']
            row = staff.pending(token,role_required=True)
            from .teams import describe_pin

            label = describe_pin(row.role_scope) if row.role_scope else row.profile_label or 'Individual workspace access'
            preview = {'name': row.name, 'email': row.email, 'expires_at': row.expires_at,
                       'workspaces': [(row.case.title, label),
                                      *((case.title, profile['label']) for case, profile in staff.additional_access(row, row.authority))]}
            form = PasswordForm(initial={'token': token})
            form.fields['token'].widget = forms.HiddenInput()
        except (PermissionDenied, ValidationError):
            problem = 'This invitation is unavailable. Ask the inviter to review your current link.'
    elif request.method == 'POST' and form.is_valid():
        try:
            staff.accept(form.cleaned_data['token'],form.cleaned_data['password'],role_required=True)
        except PermissionDenied:
            form.add_error('token', 'This invitation is unavailable.')
        except ValidationError as exc:
            form.add_error('password', exc)
        else:
            messages.success(request, 'Your workspace account is ready. Sign in to continue.')
            if form.cleaned_data['review_alerts']:
                return redirect(reverse('login', query={'next': reverse('design_alert_preferences')}))
            return redirect('login')
    response = render(request, 'identity/staff_accept.html', {'form':form,'preview':preview,'problem':problem})
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
    handover = staff.handover_links(request.user, case, record.user)
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
    return render(request, 'identity/staff_departure.html', {'case':case,'person':record.user,'form':form,'blocked':blocked,
                  'handover':handover})
