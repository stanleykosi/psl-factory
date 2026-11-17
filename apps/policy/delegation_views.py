"""Workspace delegation setup backed by the versioned decision-rule service."""
from urllib.parse import urlencode
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.core.evidence_access import public_evidence
from apps.core.services import bump, event, lock_case
from apps.core.workbench import granted
from apps.identity.models import Grant
from apps.pmo.forms import OffsetTimestamp

from .impact import configuration
from .models import Configuration, PolicyState
from .role_assignments import COMPONENT, assert_assigned, authorize_header, draft_delegations, instant, invoice_delegation_source
from .services import reference_values, resolve

SUBMISSION_ACTION = 'delegation.draft_submitted'


def assignments(actor, case):
    authorize_header(actor, case, COMPONENT)
    resolved = resolve(COMPONENT, case)
    if resolved.status != 'ACTIVE':
        return []
    return reference_values(configuration(actor, case.pk, resolved.configuration.pk))


class DelegationDraftForm(forms.Form):
    principal = forms.ModelChoiceField(queryset=None, label='From')
    delegate = forms.ModelChoiceField(queryset=None, label='To')
    role = forms.ChoiceField(label='Decision role')
    starts = OffsetTimestamp(label='Starts (include timezone)')
    ends = OffsetTimestamp(label='Ends (include timezone)')
    evidence = forms.ModelChoiceField(queryset=None, label='Recorded owner decision')
    effective = OffsetTimestamp(label='Draft effective from (include timezone)')
    source_configuration = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    submission_key = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def __init__(self, case, source, members, role, data=None):
        super().__init__(data, initial={'role': role, 'source_configuration': source.pk if source else None,
                                       'revision': case.revision, 'submission_key': uuid4()})
        self.fields['role'].widget = forms.HiddenInput()
        self.fields['role'].choices = [(role, role)]
        people = get_user_model().objects.filter(is_active=True, grant__case=case, grant__active=True,
            grant__action='case.read', pk__in=[item['user_id'] for item in members if item['role'] == role]).order_by('username', 'pk')
        for key in ('principal', 'delegate'):
            self.fields[key].queryset = people
            self.fields[key].label_from_instance = lambda user: user.get_full_name() or user.get_username()
        self.fields['evidence'].queryset = public_evidence(case.evidence.filter(kind='policy_decision')).order_by('-pk')

    def clean(self):
        data = super().clean()
        if data.get('principal') and data.get('principal') == data.get('delegate'):
            self.add_error('delegate', 'Choose a different person.')
        if data.get('starts') and data.get('ends') and data['ends'] <= data['starts']:
            self.add_error('ends', 'Enter a time after the start.')
        return data


@transaction.atomic
def save(actor, case_id, data):
    case = lock_case(actor, case_id, 'policy.configure')
    source, records = invoice_delegation_source(actor, case)
    entry = {'role': data['role'], 'principal_id': data['principal'].pk, 'delegate_id': data['delegate'].pk,
             'valid_from': data['starts'].isoformat(), 'valid_until': data['ends'].isoformat()}
    key = data.get('submission_key')
    intent = dict(entry, evidence=data['evidence'].pk, effective=data['effective'].isoformat(),
                  source=data['source_configuration'])
    if key:
        previous = case.audit.filter(action=SUBMISSION_ACTION, actor=actor, data__key=str(key)).first()
        if previous:
            if previous.data['intent'] != intent:
                raise ValidationError('This submission already saved a different draft. Open a new form to make another draft.')
            return configuration(actor, case.pk, previous.data['configuration'])
    if case.revision != data['revision']:
        raise ValidationError('The workspace changed. Refresh before saving a new draft.')
    if data['source_configuration'] != (source.pk if source else None):
        raise ValidationError('Delegations changed. Review the current table before saving.')
    ids = {data['principal'].pk, data['delegate'].pk}
    if len(ids) != 2 or Grant.objects.filter(case=case, user_id__in=ids, user__is_active=True,
                                            action='case.read', active=True).count() != 2:
        raise ValidationError('Choose two distinct active people with access to this project.')
    members = assignments(actor, case)
    assert_assigned(data['principal'], case, members, data['role'])
    assert_assigned(data['delegate'], case, members, data['role'])
    if entry in records:
        raise ValidationError('That exact delegation is already recorded.')
    draft = draft_delegations(actor, case.pk, [*records, entry], data['evidence'].pk, data['effective'])
    if key:
        event(actor, case, SUBMISSION_ACTION, key=str(key), intent=intent, configuration=draft.pk)
    bump(case)
    return draft


@login_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@never_cache
def workspace(request, case_id):
    case = get_object_or_404(granted(request.user, ['policy.read']), pk=case_id)
    source, records = None, []
    problem = ''
    try:
        source, records = invoice_delegation_source(request.user, case)
    except ValidationError as exc:
        problem = exc.messages[0]
    latest_state = PolicyState.objects.filter(configuration=OuterRef('pk')).order_by('-pk').values('state')[:1]
    pending = Configuration.objects.filter(case=case, component='D05.delegation_rules', created_by=request.user).annotate(
        lifecycle=Subquery(latest_state)).filter(lifecycle__in=['draft', 'validated']).order_by('-revision')[:5]
    drafts = []
    for draft in pending:
        try:
            configuration(request.user, case.pk, draft.pk)
        except (PermissionDenied, ValidationError):
            continue
        drafts.append(draft)
    saved = None
    saved_id = request.GET.get('saved', '')
    if saved_id.isascii() and saved_id.isdigit() and len(saved_id) <= 18:
        candidate = Configuration.objects.filter(case=case, component='D05.delegation_rules', created_by=request.user,
                                                 pk=saved_id).first()
        if candidate:
            saved = configuration(request.user, case.pk, candidate.pk)
    ids = {entry[key] for entry in records for key in ('principal_id', 'delegate_id')}
    people = get_user_model().objects.filter(pk__in=ids, grant__case=case, grant__active=True,
                                             grant__action='case.read').in_bulk()

    def label(pk):
        user = people.get(pk)
        return (user.get_full_name() or user.get_username()) if user else 'Unavailable person'

    now = timezone.now()
    rows = [{'principal': label(entry['principal_id']), 'delegate': label(entry['delegate_id']),
             'role': entry['role'], 'starts': instant(entry['valid_from']), 'ends': instant(entry['valid_until']),
             'scope': 'Invoice review' if entry.get('decision_scope') else 'Role delegation'} for entry in records]
    can_edit = not problem and Grant.objects.filter(case=case, user=request.user, active=True, action='policy.configure').exists()
    if request.method == 'POST' and not can_edit:
        raise PermissionDenied
    members = assignments(request.user, case) if can_edit else []
    roles = sorted({item['role'] for item in members})
    role = request.POST.get('role') if request.method == 'POST' else request.GET.get('role', roles[0] if roles else '')
    if request.method == 'POST' and role not in roles:
        raise PermissionDenied('Select a currently assigned role.')
    form = DelegationDraftForm(case, source, members, role, request.POST if request.method == 'POST' else None) if role in roles else None
    if request.method == 'POST' and form.is_valid():
        try:
            draft = save(request.user, case.pk, form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Delegation draft saved for review.')
            if form.cleaned_data['submission_key']:
                return redirect(reverse('design_delegation', args=[case.pk]) + '?' + urlencode({'saved': draft.pk}))
            return redirect('design_delegation', case_id=case.pk)
    return render(request, 'design/delegation.html', {'case': case, 'rows': rows, 'drafts': drafts, 'form': form, 'problem': problem,
                                                       'can_edit': can_edit, 'roles': roles, 'role': role,
                                                       'source': source, 'as_of': now, 'saved': saved})
