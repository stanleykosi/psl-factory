"""Asset register intake, source evidence and exact depreciation review."""

from io import BytesIO

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from adapters import case_uploads
from apps.core.evidence_access import public_evidence
from apps.core.models import Case
from apps.core.read_budget import limit_queries
from apps.core.read_observation import observation_scope
from apps.finance import ppe, ppe_dates
from apps.finance.models import ScheduleWork
from apps.identity.services import active_case_grants, require
from apps.workflows import factory_ppe as native, factory_ppe_date_proof as date_proof, factory_ppe_opening as opening

from .commands import require_line
from .delivery import PROOF, proof_rows, recorded
from .http import BOOLEAN, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT


REFERENCE = {'type': 'string', 'pattern': r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}
BASIS = choice(ppe_dates.SUPPLIED, ppe_dates.DERIVED)
PURPOSE = choice('register', 'basis', 'schedule')
VERDICT = choice('approve', 'return', 'reject', 'revoke')
ATTACHMENT = {'type': 'string', 'format': 'binary'}
AMOUNT = nullable({'type': 'string', 'maxLength': 256})
ROW = obj({'asset_id': TEXT, 'category': TEXT, 'closing_cost': AMOUNT, 'charge': AMOUNT,
           'closing_accumulated': AMOUNT, 'book_value': AMOUNT, 'event_refs': array(TEXT), 'findings': array(TEXT),
           'fraction_basis': BASIS, 'used_fraction': AMOUNT}, optional=('fraction_basis', 'used_fraction'))
SCHEDULE = obj({'status': choice('ready', 'held'), 'findings': array(TEXT), 'rows': array(ROW, limit=100),
                'totals': obj({key: AMOUNT for key in ('cost', 'accumulated', 'book_value', 'charge')}),
                'scope': obj({'entity': TEXT, 'currency': TEXT, 'unit': TEXT, 'period_start': ppe.DATE,
                              'period_end': ppe.DATE, 'label_as_of': ppe.DATE}),
                'coverage': {'const': 'selected_supplied_population'}, 'native_source_verified': {'const': False},
                'ledger_posted': {'const': False}})
REGISTER_ROW = obj({'id': ID, 'reference': REFERENCE, 'version': ID})
RECORD = obj({**REGISTER_ROW['properties'], 'case_revision': REVISION})


def project(actor, case_id):
    case = get_object_or_404(Case, pk=case_id)
    ppe.readable(actor, case)
    return case


@endpoint(response=obj({'case_revision': REVISION, 'can_capture': BOOLEAN, 'registers': array(REGISTER_ROW, limit=40),
                        'register_sources': array(PROOF, limit=40), 'date_sources': array(PROOF, limit=40)}),
          summary='Read the native asset register choices and supporting evidence in this project')
def registers(request, case_id):
    actor = request.user
    case = project(actor, case_id)
    grants = {action for _, action in active_case_grants(actor, [case.pk])}
    evidence = public_evidence(case.evidence.all()).only('id', 'kind', 'version').order_by('-pk')
    queryset = ScheduleWork.objects.filter(case=case, kind='ppe_register')
    heads = queryset.order_by('reference', '-version').distinct('reference').values('pk')
    return {'case_revision': case.revision, 'can_capture': 'ppe.capture' in grants,
            'registers': list(queryset.filter(pk__in=heads).order_by('-pk').values('id', 'reference', 'version')[:40]),
            'register_sources': proof_rows(evidence.filter(kind='ppe_register')[:40]),
            'date_sources': proof_rows(evidence.filter(kind__in=ppe_dates.SUPPORT_KINDS)[:40])}


def version(row):
    return {'id': row.pk, 'reference': row.reference, 'version': row.version, 'case_revision': row.case.revision}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'reference': REFERENCE, 'evidence_id': ID}),
          response=RECORD, status=201, summary='Capture a versioned register from exact supplied asset evidence')
def capture(request, case_id, *, body):
    return version(ppe.capture(request.user, case_id, body['reference'], body['evidence_id'], body['case_revision']))


class DateForm(forms.Form):
    case_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    evidence_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    asset_id = forms.CharField(max_length=100)
    delivery_date = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    in_service_date = forms.DateField(required=False, input_formats=['%Y-%m-%d'])
    fraction_basis = forms.ChoiceField(choices=[(value, value) for value in BASIS['enum']])
    file = forms.FileField(required=False)


@endpoint(method='POST', multipart=True, request=obj({'case_revision': REVISION, 'evidence_id': ID,
    'asset_id': TEXT, 'delivery_date': ppe.DATE, 'in_service_date': ppe.DATE, 'fraction_basis': BASIS, 'file': ATTACHMENT},
    optional=('delivery_date', 'in_service_date', 'file')), response=RECORD, status=201,
    summary='Record a new register version for one asset date with an optional private PDF explanation')
def record_dates(request, case_id, register_id):
    form = DateForm(request.POST, request.FILES)
    if not form.is_valid():
        raise ValidationError('Check the asset reference, dates, selected basis and PDF evidence.')
    data = form.cleaned_data
    dates = [data[key].isoformat() if data[key] else None for key in ('delivery_date', 'in_service_date')]
    row = date_proof.record(request.user, case_id, register_id, data['asset_id'], *dates, data['fraction_basis'],
                            data['evidence_id'], data['case_revision'], data['file'])
    return version(row)


def review_options(actor, work, register, schedule, stage):
    if work.cancel_requested or work.status in ('cancelled', 'followup_needed'):
        return []
    candidates = [(register, 'register')]
    if ppe_dates.needs_review(register):
        candidates.append((register, 'basis'))
    if schedule:
        candidates.append((schedule, 'schedule'))
    expected_stage = {'register': 'source_review', 'basis': 'basis_review', 'schedule': 'output_review'}
    options = []
    for target, purpose in candidates:
        try:
            ppe.authority(actor, target, purpose)
            last = ppe.latest(target, purpose)
            if stage != expected_stage[purpose] and (not last or last.verdict != 'approve'):
                continue
            ppe.current(target)
        except (PermissionDenied, ValidationError):
            continue
        verdicts = ['revoke'] if last and last.verdict == 'approve' else ['approve', 'return', 'reject']
        options.append({'target_id': target.pk, 'purpose': purpose, 'verdicts': verdicts})
    return options


@endpoint(response=obj({**VERSIONS, 'register_id': ID, 'schedule_id': nullable(ID), 'accounting_note_id': nullable(ID),
    'stage': TEXT, 'finding': {'type': 'string'}, 'register': nullable(ppe.REGISTER), 'schedule': nullable(SCHEDULE),
    'accounting_note_url': nullable(TEXT),
    'review_options': array(obj({'target_id': ID, 'purpose': PURPOSE, 'verdicts': array(VERDICT)}), limit=3),
    'schedule_review_id': nullable(ID), 'review_evidence': array(PROOF, limit=35),
    'opening_return': nullable(obj({'target_id': ID, 'review_id': ID})), 'has_opening_attachment': BOOLEAN,
    'date_attachment_ids': array(ID, limit=100)}),
    summary='Read the exact current asset register, basis and depreciation review with protected proof references')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with transaction.atomic(), limit_queries(950):
        grants = {action for _, action in active_case_grants(actor, [work.case_id])}
        permitted = 'ppe.report' in grants
        if permitted:
            work.case = ppe.locked(actor, work.case_id, 'ppe.report')
        with observation_scope():
            return projection(actor, work, permitted)


def projection(actor, work, permitted):
    register, selection = native.source(work, actor)
    facts = native.report(work, actor)
    schedule = native.schedule(work)
    last = ppe.latest(schedule, 'schedule') if schedule else None
    opening_return = None
    if facts['stage'] == 'returned' and permitted and actor.pk == work.actor_id:
        subject = opening.returned_subject(work, register)
        if subject:
            opening_return = {'target_id': subject[0].pk, 'review_id': subject[1].pk}
    evidence = public_evidence(work.case.evidence.filter(kind__in=('finance_review', 'ppe_basis_explanation')))
    mapping_url = None
    if permitted and selection['ledger_id']:
        try:
            require(actor, work.case, 'finance.read')
        except PermissionDenied:
            pass
        else:
            mapping_url = f"/api/v1/projects/{work.case_id}/accounting-mappings/{selection['ledger_id']}"
    return {'expected_revision': work.revision, 'case_revision': work.case.revision,
            'register_id': register.pk, 'schedule_id': facts['schedule'], 'accounting_note_id': selection['ledger_id'],
            'accounting_note_url': mapping_url,
            'stage': facts['stage'], 'finding': facts['finding'], 'register': register.payload if permitted else None,
            'schedule': schedule.result if permitted and facts['stage'] in ('output_review', 'complete') else None,
            'review_options': review_options(actor, work, register, schedule, facts['stage']),
            'schedule_review_id': last.pk if last else None, 'opening_return': opening_return,
            'review_evidence': proof_rows(evidence.only('id', 'kind', 'version').order_by('-pk')[:35]),
            'has_opening_attachment': permitted and opening.attachment_for(actor, work, register) is not None,
            'date_attachment_ids': sorted(date_proof.attachments_for(actor, work, register)) if permitted else []}


class OpeningForm(forms.Form):
    expected_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    case_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    target_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    review_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    reason = forms.CharField(max_length=2000)
    file = forms.FileField()


@endpoint(method='POST', multipart=True, request=obj({**VERSIONS, 'target_id': ID, 'review_id': ID,
    'reason': {**TEXT, 'maxLength': 2000}, 'file': ATTACHMENT}), response=obj({**WORK_RESULT['properties'], 'record_id': ID}),
    status=201, summary='Attach private opening proof to the exact returned asset subject and resume with a successor')
def attach_opening(request, work_id):
    work = require_line(request.user, work_id, native.DEFINITION)
    form = OpeningForm(request.POST, request.FILES)
    if not form.is_valid():
        raise ValidationError('Choose one PDF and identify the exact return and reason.')
    data = form.cleaned_data
    row = opening.attach(request.user, work.pk, data['expected_revision'], data['case_revision'], data['target_id'],
                         data['review_id'], data['reason'], data['file'])
    return recorded(work, row)


def download_attachment(attachment):
    if attachment is None:
        raise Http404
    try:
        body = case_uploads.read(attachment)
    except (OSError, ValidationError) as exc:
        raise Http404 from exc
    return FileResponse(BytesIO(body), as_attachment=True, filename=attachment.name, content_type='application/pdf')


@endpoint(media_type='application/pdf', response=ATTACHMENT, summary='Download the currently selected private opening proof PDF')
def opening_file(request, work_id):
    work = require_line(request.user, work_id, native.DEFINITION)
    with transaction.atomic():
        work.case = ppe.locked(request.user, work.case_id, 'ppe.report')
        register, _ = native.source(work, request.user)
        return download_attachment(opening.attachment_for(request.user, work, register))


@endpoint(media_type='application/pdf', response=ATTACHMENT, summary='Download the private PDF for the selected exact asset date')
def date_file(request, work_id, fact_id):
    work = require_line(request.user, work_id, native.DEFINITION)
    with transaction.atomic():
        work.case = ppe.locked(request.user, work.case_id, 'ppe.report')
        register, _ = native.source(work, request.user)
        return download_attachment(date_proof.attachments_for(request.user, work, register).get(fact_id))
