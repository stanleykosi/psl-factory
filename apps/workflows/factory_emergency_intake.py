"""Start a native Emergency request from an exact project incident."""
from urllib.parse import urlencode
from uuid import UUID, uuid4

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.functions import Left
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.core.evidence_access import public_evidence
from apps.core.models import Case
from apps.core.presentation import workspace_name
from apps.core.services import add_evidence, event, lock_case
from apps.core.workbench import granted
from apps.documents.contracts import digest
from apps.identity.services import require
from apps.pmo import changes, emergencies
from apps.pmo.models import ChangeRequest, DeliveryCandidate, EmergencyProfile
from apps.policy.services import role_policy

from . import factory_emergency
from .factory_progress_views import StartWithBackground, started
from .models import FactoryWork


REQUESTED = 'factory.emergency_incident_requested'
PROFILE_INPUTS = {'template_id': None, 'authorization_id': None, 'outcome_id': None, 'audience': None}
REQUEST_GRANTS = ('emergency.read', 'change.manage', 'evidence.add', 'factory.start', 'factory.read')


def _url(case=None, version=None):
    values = {'definition': factory_emergency.DEFINITION, 'mode': 'classify' if version else 'incident'}
    if case:
        values['case'] = case.pk
    if version:
        values['version'] = version.pk
    return reverse('factory_create') + '?' + urlencode(values)


def _sources(case, kind):
    return public_evidence(case.evidence.filter(kind=kind)).annotate(summary=Left('body', 100)).defer('body').order_by('-pk')


def _evidence_label(source):
    return f'{source.summary} · Version {source.version}'


def _request_authority(actor, case):
    for action in ('case.read', *REQUEST_GRANTS):
        require(actor, case, action)
    role_policy(actor, case, 'PM')


def _request_scope(actor, case, version_id):
    _request_authority(actor, case)
    if not case.audit.filter(action=REQUESTED, actor=actor, data__version=version_id).exists():
        raise Http404('Choose your recorded Emergency request.')
    version = changes.current_change(case, version_id)
    if (version.actor_id != actor.pk or version.category != 'Emergency'
            or not _sources(case, 'incident').filter(pk=version.incident_id).exists()):
        raise ValidationError('Review the current linked incident before continuing.')
    return version


@transaction.atomic
def request_change(actor, case_id, expected, key, incident_id, module, plan):
    case = lock_case(actor, case_id, 'change.manage')
    _request_authority(actor, case)
    if (case.kind != 'project' or type(expected) is not int or expected < 1 or not isinstance(key, UUID)
            or type(incident_id) is not int or not isinstance(module, str) or not 0 < len(module.strip()) <= 160
            or not isinstance(plan, str) or not 0 < len(plan.strip()) <= 4000):
        raise ValidationError('Provide a project, exact incident, affected service and plan.')
    incident = _sources(case, 'incident').filter(pk=incident_id).first()
    if incident is None:
        raise ValidationError('Choose available incident evidence for this project.')
    reference = f'EMG-{key.hex}'
    intent = {'incident': incident.pk, 'incident_hash': incident.sha256, 'module': module.strip(), 'plan': plan.strip()}
    saved = case.audit.filter(actor=actor, action=REQUESTED, data__key=str(key)).first()
    if saved:
        if saved.data['intent'] != digest(intent):
            raise ValidationError('This request already recorded another plan. Start a new request to change it.')
        return _request_scope(actor, case, saved.data['version'])
    if case.revision != expected:
        raise ValidationError('The project changed. Reopen this form before submitting your request.')
    if ChangeRequest.objects.filter(case=case, reference=reference).exists():
        raise ValidationError('This request reference is already in use. Reopen the form to start a new request.')
    evidence = add_evidence(actor, case.pk, 'change_request', intent['plan'], f'psl:emergency-incident/{key.hex}', expected)
    case.refresh_from_db(fields=['revision'])
    request = changes.log_change(actor, case.pk, reference, 'Emergency', intent['module'], intent['plan'],
                                 'Request for preauthorisation of this incident plan.', evidence.pk,
                                 case.revision, incident.pk)
    event(actor, case, REQUESTED, key=str(key), version=request.pk, incident=incident.pk,
          evidence=evidence.pk, intent=digest(intent))
    return request


def _work_for(case, version):
    key = digest([str(case.pk), factory_emergency.DEFINITION, version.change_id])
    return FactoryWork.objects.filter(case=case, definition=factory_emergency.DEFINITION, business_key=key).first()


@transaction.atomic
def classify_request(actor, case_id, version_id, expected, values):
    case = lock_case(actor, case_id, 'emergency.manage')
    version = _request_scope(actor, case, version_id)
    profile = EmergencyProfile.objects.filter(version=version).order_by('-pk').first()
    selected = values['profile']
    if selected:
        if not profile or profile.pk != selected:
            raise ValidationError('The classification changed. Review its current source before continuing.')
    elif profile and (profile.candidate_id, profile.evidence_id, profile.critical_production, profile.p1, profile.note) != (
            values['candidate'].pk, values['evidence'].pk, values['critical_production'], values['p1'], values['note']):
        raise ValidationError('An exact classification is already recorded. Review it before continuing.')
    existing = _work_for(case, version)
    if existing:
        factory_emergency.source(existing, actor)
        return existing
    if case.revision != expected:
        raise ValidationError('The project changed. Reopen the classification before saving.')
    if not profile:
        candidate, classification = values['candidate'], values['evidence']
        if not _sources(case, 'incident_classification').filter(pk=classification.pk).exists():
            raise ValidationError('Choose available classification evidence for this project.')
        profile = emergencies.capture_profile(actor, case.pk, version.pk, candidate.pk, values['critical_production'],
                                              values['p1'], classification.pk, values['note'], expected)
        case.refresh_from_db(fields=['revision'])
    return factory_emergency.start(actor, case.pk, f'EMERGENCY-INCIDENT-{version.pk}', profile.pk,
                                   PROFILE_INPUTS, f'Emergency change · {version.module}'[:160], case.revision)


class ProjectForm(forms.Form):
    case = forms.ModelChoiceField(queryset=Case.objects.none(), label='Project')

    def __init__(self, cases, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['case'].queryset = cases
        self.fields['case'].label_from_instance = workspace_name


class RequestForm(forms.Form):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    key = forms.UUIDField(widget=forms.HiddenInput)
    incident = forms.ModelChoiceField(queryset=None, label='Incident')
    module = forms.CharField(max_length=160, label='Affected service or module')
    plan = forms.CharField(max_length=4000, label='Plan', widget=forms.Textarea(attrs={'rows': 4}))

    def __init__(self, case, data=None):
        super().__init__(data, initial={'revision': case.revision, 'key': uuid4()})
        self.fields['incident'].queryset = _sources(case, 'incident')
        self.fields['incident'].label_from_instance = _evidence_label


class ClassifyForm(StartWithBackground):
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    profile = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)
    candidate = forms.ModelChoiceField(queryset=None, required=False, label='Release candidate')
    evidence = forms.ModelChoiceField(queryset=None, required=False, label='Classification evidence')
    critical_production = forms.NullBooleanField(required=False, label='Critical production incident')
    p1 = forms.NullBooleanField(required=False, label='Confirmed priority one incident')
    note = forms.CharField(max_length=4000, required=False, label='Classification note', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, case, data=None, profile=None):
        super().__init__(data, initial={'revision': case.revision, 'profile': profile.pk if profile else None})
        self.fields['candidate'].queryset = DeliveryCandidate.objects.filter(case=case).order_by('-pk')
        self.fields['evidence'].queryset = _sources(case, 'incident_classification')
        self.fields['evidence'].label_from_instance = _evidence_label

    def clean(self):
        data = super().clean()
        if not data.get('profile'):
            for field in ('candidate', 'evidence', 'note'):
                if field not in self.errors and not data.get(field):
                    self.add_error(field, 'Provide this information to record the classification.')
        return data


def create(request):
    data = request.POST if request.method == 'POST' else request.GET
    cases = granted(request.user, REQUEST_GRANTS).filter(kind='project')
    projects = ProjectForm(cases, data if data.get('case') else None)
    case = projects.cleaned_data['case'] if projects.is_bound and projects.is_valid() else None
    form, problem = None, ''
    if case:
        try:
            _request_authority(request.user, case)
        except (PermissionDenied, ValidationError):
            problem = 'The current project manager must submit this incident plan.'
            if request.method == 'POST':
                raise PermissionDenied(problem)
        else:
            form = RequestForm(case, request.POST if request.method == 'POST' else None)
            if request.method == 'POST' and form.is_valid():
                values = form.cleaned_data
                try:
                    version = request_change(request.user, case.pk, values['revision'], values['key'],
                                             values['incident'].pk, values['module'], values['plan'])
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    return redirect(_url(case, version))
    return render(request, 'factory/emergency_incident_start.html', {'projects': projects, 'case': case,
                                                                   'form': form, 'problem': problem})


def classification(request):
    data = request.POST if request.method == 'POST' else request.GET
    try:
        case_id = UUID(data.get('case', ''))
        version_id = int(data.get('version', ''))
    except (ValueError, TypeError):
        raise Http404('Choose the recorded Emergency request.') from None
    case = get_object_or_404(granted(request.user, REQUEST_GRANTS).filter(kind='project'), pk=case_id)
    try:
        version = _request_scope(request.user, case, version_id)
    except ValidationError as exc:
        return render(request, 'factory/emergency_incident_classification.html',
                      {'case': case, 'problem': ' '.join(exc.messages)}, status=409)
    work = _work_for(case, version)
    profile = EmergencyProfile.objects.filter(version=version).order_by('-pk').first()
    form, problem = None, ''
    try:
        require(request.user, case, 'emergency.manage')
    except PermissionDenied:
        if request.method == 'POST':
            raise
        problem = 'A project manager with Emergency classification access must check this request.'
    else:
        if not work or request.method == 'POST':
            form = ClassifyForm(case, request.POST if request.method == 'POST' else None, profile)
        if form and form.is_bound and form.is_valid():
            try:
                work = classify_request(request.user, case.pk, version.pk, form.cleaned_data['revision'], form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                return started(request, work, form.cleaned_data['background'])
    return render(request, 'factory/emergency_incident_classification.html', {
        'case': case, 'version': version, 'profile': profile, 'work': work, 'form': form, 'problem': problem,
        'incident': _sources(case, 'incident').filter(pk=version.incident_id).first(),
    })
