"""Typed intake over exact records owned by each factory line."""
from datetime import date
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.core.workbench import granted
from apps.core.presentation import workspace_name
from apps.workflows.process_directory import entries
from apps.finance.schedules import DETAIL
from apps.workflows import (
    factory, factory_accounting, factory_archive, factory_bu, factory_change, factory_closure, factory_commercial,
    factory_delivery, factory_emergency, factory_engagement, factory_escalation, factory_forecast,
    factory_forecast_sources, factory_go_live, factory_handover, factory_hypercare, factory_invoice_intake,
    factory_issues, factory_leadership, factory_ledger, factory_minutes, factory_payroll, factory_planning,
    factory_ppe, factory_progress, factory_reporting, factory_rfp, factory_schedules, factory_views,
)

from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, UUID, Problem, array, choice, endpoint, nullable, obj
from .work import PAGE, WORK_RESULT, page_number, result


REF = {**TEXT, 'maxLength': 160}
KEY = {**TEXT, 'maxLength': 100, 'pattern': '^[ -~]+$'}
NID = nullable(ID)
IDS = {**array(ID, limit=100), 'uniqueItems': True}


def ids(names):
    return obj(dict.fromkeys(names, NID))


def invoice_start(actor, *, mode, **values):
    if mode == 'preparation':
        if values['due_date'] is not None:
            values['due_date'] = date.fromisoformat(values['due_date'])
        return factory_invoice_intake.start(actor, **values)
    return factory.start(actor, **values)


RFP_PAYLOAD = obj({
    'response_evidence': NID, 'public_terms': NID, 'lessons': NID,
    'sources': ids(('requirements', 'plan', 'costing')),
    'matrix': array(obj({'key': {**TEXT, 'maxLength': 100}, 'evidence_id': ID,
                         'response': {**TEXT, 'maxLength': 4000},
                         'disposition': choice('addressed', 'clarification', 'out_of_scope')}), limit=100),
})


def engagement_start(actor, *, case_id, key, reference, expected, **source):
    if 'capture_id' in source:
        return factory_engagement.start(actor, case_id, key, source['capture_id'], reference, expected)
    return factory_engagement.receive(actor, case_id, key, source['route'], source['evidence_id'],
                                      reference, expected, source.get('rfp_disposition'))

STARTS = {
    'pmo-issues/v1': (factory_issues.start, obj({'issue_id': ID})),
    'pmo-leadership-report/v1': (factory_leadership.start, obj({'inputs': factory_leadership.INPUT})),
    'finance-ledger/v1': (factory_ledger.start, obj({'evidence_id': ID, 'predecessor_id': NID})),
    'finance-bu/v1': (factory_bu.start, obj({'inputs': factory_bu.INPUT})),
    'engagement/v1': (engagement_start, {'oneOf': [obj({'capture_id': ID}),
        obj({'route': choice('A', 'B', 'C'), 'evidence_id': ID, 'rfp_disposition': NID}, optional=('rfp_disposition',))]}),
    'pmo-minutes/v1': (factory_minutes.start, obj({'data': factory_minutes.SELECTION})),
    'pmo-escalation/v1': (factory_escalation.start, obj({'request_id': ID, 'template_id': NID})),
    'pmo-weekly-report/v1': (factory_reporting.start, obj({'inputs': factory_reporting.INPUT})),
    'finance-schedules/v1': (factory_schedules.start, obj({
        'kind': choice('income', 'inventory'), 'parent_id': NID, 'evidence_id': ID, 'payload': nullable(DETAIL),
    })),
    'finance-ppe/v1': (factory_ppe.start, obj({'register_id': ID, 'prior_id': NID, 'ledger_id': NID})),
    'finance-forecast/v1': (factory_forecast.start, obj({'value': obj({
        'protocol': {'const': factory_forecast_sources.PROTOCOL}, 'scenario_id': ID, 'as_of': TEXT,
        'months': array(TEXT, limit=120), 'source_ids': {**array(ID, limit=4000), 'uniqueItems': True},
        'template_id': NID, 'audience': choice('internal', 'management', 'group'),
    })})),
    'finance-payroll/v1': (factory_payroll.start, obj({'request_id': ID, 'inputs': factory_payroll.INPUT})),
    'pmo-emergency/v1': (factory_emergency.start, obj({'profile_id': ID, 'inputs': factory_emergency.INPUT})),
    'pmo-change/v1': (factory_change.start, obj({'version_id': ID, 'inputs': factory_change.INPUT})),
    'rfp-response/v1': (factory_rfp.start, obj({'payload': RFP_PAYLOAD})),
    'finance-accounts/v1': (factory_accounting.start, obj({'source_id': ID, 'adjustment_ids': IDS})),
    'pmo-finance/v1': (invoice_start, {'oneOf': [
        obj({'mode': {'const': 'completion'}, 'coverage_id': ID, 'handoff_id': ID}),
        obj({'mode': {'const': 'preparation'}, 'preparation_id': ID,
             'due_date': nullable({'type': 'string', 'format': 'date'}), 'invoice_id': NID}),
    ]}),
    'planning/v1': (factory_planning.start, obj({'packet_id': ID})),
    'commercial/v1': (factory_commercial.start, obj({'head_id': ID})),
    'delivery-release/v1': (factory_delivery.start, obj({'dossier_id': ID})),
    'delivery-hypercare/v1': (factory_hypercare.start, obj({'dossier_id': ID})),
    'delivery-archive/v1': (factory_archive.start, obj({'dossier_id': ID, 'inventory': factory_archive.INVENTORY})),
    'delivery-handover/v1': (factory_handover.start, obj({'dossier_id': ID, 'inputs': ids(factory_handover.FIELDS)})),
    'delivery-closure/v1': (factory_closure.start, obj({'dossier_id': ID, 'inputs': ids(factory_closure.FIELDS)})),
    'delivery-go-live/v1': (factory_go_live.start, obj({'dossier_id': ID, 'inputs': ids(factory_go_live.FIELDS)})),
}
INTAKE_GRANTS = {key: grants for key, _, _, grants in factory_views.INTAKES}
DERIVED_REFERENCES = {'pmo-issues/v1', 'finance-ledger/v1'}

START_INPUT = {'oneOf': [
    obj({'line': {'type': 'string', 'const': line}, 'case_id': UUID, 'case_revision': REVISION,
         'idempotency_key': KEY, 'background': BOOLEAN, 'intake': schema,
         **({} if line in DERIVED_REFERENCES else {'reference': REF})},
        optional=('background',)) for line, (_, schema) in STARTS.items()
]}
LINE = obj({'key': choice(*STARTS, factory_views.rfp_fresh_intake.LINE), 'title': TEXT, 'description': TEXT,
            'can_submit_via_api': BOOLEAN, 'django_url': TEXT, 'project_options_url': nullable(TEXT), 'submit_url': TEXT})
TRIGGER_GUIDE = obj({'action': TEXT, 'screen': TEXT, 'source_url': TEXT, 'tracking_url': TEXT})
LINE_PROJECT = obj({'case_id': UUID, 'title': TEXT, 'case_revision': REVISION, 'sample': BOOLEAN, 'django_url': TEXT,
                    'source_options_url': TEXT, 'workflow_intake_url': nullable(TEXT)})
START_RESULT = obj({**WORK_RESULT['properties'], 'background': choice('queued', 'existing', 'held', 'not_requested')})
WORKFLOW_INTAKE = {'pmo-emergency/v1': 'emergency-intake', 'pmo-weekly-report/v1': 'weekly-report-intake',
                   'pmo-leadership-report/v1': 'leadership-report-intake', 'pmo-escalation/v1': 'escalation-register',
                   'engagement/v1': 'engagement-intake', 'finance-payroll/v1': 'payroll/requests',
                   'finance-accounts/v1': 'accounting-intake', 'finance-ppe/v1': 'asset-registers',
                   'pmo-change/v1': 'ordinary-changes', 'pmo-issues/v1': 'issues'}


def start_projects(actor, line):
    return granted(actor, INTAKE_GRANTS[line]).filter(kind='project')


@endpoint(response=obj({'items': array(obj({'process': TEXT, 'title': TEXT, 'department': choice('PMO', 'Finance'),
    'line': nullable(TEXT), 'project_handoff': BOOLEAN, 'intake_available': BOOLEAN, 'intake_url': nullable(TEXT),
    'guide': nullable(TRIGGER_GUIDE)}))}),
    summary='Browse release processes and see which intakes are available in your workspaces')
def processes(request):
    available = {item['definition'] for item in factory_views.intake_options(request.user)}
    return {'items': entries(available)}


@endpoint(response=obj({'items': array(LINE), 'as_of': DATETIME}), summary='List available factory intake choices')
def lines(request):
    return {'items': [
        {'key': item['definition'], 'title': item['title'], 'description': item['description'],
         'can_submit_via_api': item['definition'] in STARTS or item['definition'] == factory_views.rfp_fresh_intake.LINE,
         'django_url': reverse('factory_create') + '?definition=' + item['definition'],
         'project_options_url': '/api/v1/lines/projects?line=' + item['definition'] if item['definition'] in STARTS else None,
         'submit_url': '/api/v1/work' if item['definition'] in STARTS else '/api/v1/received-bids'}
        for item in factory_views.intake_options(request.user)
    ], 'as_of': timezone.now()}


@endpoint(response=obj({'items': array(LINE_PROJECT, limit=25), 'page': PAGE, 'next_page': nullable(PAGE)}),
          query={'line': choice(*STARTS), 'q': {'type': 'string', 'maxLength': 120}, 'page': PAGE},
          required_query=('line',), summary='List projects and current revisions for a specific Start work type')
def projects(request):
    line = request.GET.get('line')
    search = request.GET.get('q', '')
    if line not in STARTS or len(search) > 120:
        raise Problem(422, 'invalid_filter', 'Choose a Start work type and a shorter project search.')
    cases = start_projects(request.user, line).order_by('title', 'pk')
    if search.strip():
        cases = cases.filter(title__icontains=search.strip())
    page = Paginator(cases, 25).get_page(page_number(request))
    resource = WORKFLOW_INTAKE.get(line)
    return {'items': [{
        'case_id': case.pk, 'title': workspace_name(case), 'case_revision': case.revision, 'sample': case.synthetic,
        'django_url': reverse('factory_create', query={'case': case.pk, 'definition': line}),
        'source_options_url': f'/api/v1/projects/{case.pk}/intake-sources?line={line}',
        'workflow_intake_url': f'/api/v1/projects/{case.pk}/{resource}' if resource else None,
    } for case in page], 'page': page.number,
        'next_page': page.next_page_number() if page.has_next() and page.number < PAGE['maximum'] else None}


def progress_result(actor, work, enable):
    background = 'not_requested'
    if enable:
        existed = getattr(work, 'background_progress', None) is not None
        try:
            factory_progress.set_progress(actor, work.pk, work.revision, True, initial=True)
            background = 'existing' if existed else 'queued'
        except (PermissionDenied, ValidationError):
            background = 'held'
    return {**result(work), 'background': background}


@endpoint(method='POST', request=START_INPUT, response=START_RESULT,
          summary='Start the selected factory line using the current exact native sources')
def start(request, *, body):
    case = get_object_or_404(start_projects(request.user, body['line']), pk=body['case_id'])
    starter, _ = STARTS[body['line']]
    inputs = dict(body['intake'])
    if body['line'] not in DERIVED_REFERENCES:
        inputs['reference'] = body['reference']
    with transaction.atomic():
        work = starter(request.user, case_id=case.pk, key=body['idempotency_key'], expected=body['case_revision'], **inputs)
        return progress_result(request.user, work, body.get('background', True))


MINUTES_UPLOAD_FIELDS = obj({
    'case_revision': REVISION, 'idempotency_key': KEY, 'reference': REF, 'template_id': ID, 'meeting_version_id': ID,
    'audience': choice('internal', 'client'), 'background': choice('true', 'false'),
    'notes_file': {'type': 'string', 'format': 'binary'},
}, optional=('meeting_version_id', 'background'))


class MinutesUploadForm(forms.Form):
    case_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    idempotency_key = forms.RegexField(r'\A[A-Za-z0-9_.:-]{1,100}\Z', strip=False)
    reference = forms.CharField(max_length=160)
    template_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    meeting_version_id = forms.IntegerField(min_value=1, max_value=ID['maximum'], required=False)
    audience = forms.ChoiceField(choices=(('internal', 'Internal'), ('client', 'Client')))
    background = forms.ChoiceField(choices=(('true', 'true'), ('false', 'false')), required=False)
    notes_file = forms.FileField()


@endpoint(method='POST', request=MINUTES_UPLOAD_FIELDS, response=START_RESULT, multipart=True,
          summary='Start formal minutes from an exact private notes file and the selected project template')
@transaction.atomic
def upload_minutes(request, case_id):
    actor = request.user
    case = get_object_or_404(start_projects(actor, factory_minutes.DEFINITION), pk=case_id)
    form = MinutesUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        raise Problem(422, 'invalid_input', 'Check the meeting notes and intake fields.',
                      fields=[{'name': name, 'message': messages[0]} for name, messages in form.errors.items()])
    values = form.cleaned_data
    data = {'protocol': factory_minutes.PROTOCOL, 'evidence_id': None, 'meeting_version_id': values['meeting_version_id'],
            'template_id': values['template_id'], 'audience': values['audience'], 'publish': values['audience'] == 'client'}
    work = factory_minutes.start_uploaded(actor, case.pk, values['idempotency_key'], values['reference'], data,
                                          values['case_revision'], values['notes_file'])
    return progress_result(actor, work, values['background'] != 'false')
