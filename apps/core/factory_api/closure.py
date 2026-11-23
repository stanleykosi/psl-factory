"""Capture an exact successor report on an existing controlled closure journey."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.read_observation import read_observation
from apps.core.services import add_evidence, lock_case
from apps.identity.services import require, visible_cases
from apps.pmo import delivery, delivery_closure
from apps.pmo.models import DeliveryDossier, MeetingVersion
from apps.workflows import factory, factory_closure
from apps.workflows.factory_progress import wake_waiting
from apps.workflows.models import FactoryWork

from .commands import require_line
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .intake_sources import positive_id
from .reviews import VERSIONS
from .work import WORK_RESULT, result


def finance_scope(actor, case_id, dossier_id):
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    require(actor, case, 'delivery.finance_confirm')
    return case, get_object_or_404(DeliveryDossier.objects.filter(case=case), pk=dossier_id)


@endpoint(response=obj({'revision': REVISION, 'confirmation_id': nullable(ID), 'finding': nullable(TEXT),
    'milestones': array(obj({'milestone_id': ID, 'receipt_id': ID}), limit=200)}),
          summary='Read the exact milestone notifications Finance must confirm before closure')
def finance_options(request, case_id, dossier_id):
    case, dossier = finance_scope(request.user, case_id, dossier_id)
    known, finding, confirmation_id = [], None, None
    with limit_queries(500):
        try:
            known = delivery_closure.finance_inputs(dossier)['milestones']
        except ValidationError as exc:
            finding = exc.messages[0]
        if finding is None:
            try:
                confirmation_id = delivery_closure.current_finance_confirmation(dossier).pk
            except ValidationError:
                pass
    return {'revision': case.revision, 'confirmation_id': confirmation_id, 'finding': finding,
            'milestones': [{'milestone_id': row[0], 'receipt_id': row[1]} for row in known]}


@endpoint(method='POST', request=obj({'revision': REVISION, 'milestone_ids': array(ID, limit=200),
    'inventory_complete': {'const': True}, 'evidence_id': ID, 'note': {**TEXT, 'maxLength': 4000}}),
    response=obj({'confirmation_id': ID, 'revision': REVISION}), status=201,
    summary='Confirm the complete milestone notification inventory with Finance proof')
def finance_confirmation(request, case_id, dossier_id, *, body):
    actor = request.user
    case, dossier = finance_scope(actor, case_id, dossier_id)
    get_object_or_404(public_evidence(case.evidence.all()), pk=body['evidence_id'])
    row = delivery_closure.confirm_finance(actor, case.pk, dossier.pk, body['milestone_ids'],
                                          body['inventory_complete'], body['evidence_id'], body['note'], body['revision'])
    case.refresh_from_db(fields=['revision'])
    return {'confirmation_id': row.pk, 'revision': case.revision}


@endpoint(response=obj({'revision': REVISION, 'as_of': DATETIME, 'ready_to_prepare': BOOLEAN,
    'recorded_closure_id': nullable(ID), 'checks': array(obj({'key': TEXT, 'title': TEXT,
        'status': choice('current', 'held', 'unknown', 'closed', 'recorded', 'unavailable'),
        'summary': TEXT, 'references': array(ID), 'finding': nullable(TEXT)})),
}), query={'retrospective_id': ID, 'report_evidence_id': ID},
          summary='Read exact closure evidence and independent prerequisite holds before preparing closure')
@read_observation
def checklist(request, case_id, dossier_id):
    actor = request.user
    case = get_object_or_404(visible_cases(actor), pk=case_id, kind='project')
    require(actor, case, 'delivery.read')
    get_object_or_404(DeliveryDossier.objects.filter(case=case).only('pk'), pk=dossier_id)
    with limit_queries(1000):
        dossier = delivery.dossier_for(case, dossier_id, current=False)
        closed = delivery.latest(dossier, 'closure', False)
        if closed:
            checked = delivery_closure.recorded_closure_requirements(actor, dossier, closed)
        else:
            selection = {name: positive_id(request, name) for name in ('retrospective_id', 'report_evidence_id')}
            public = public_evidence(case.evidence.all())
            if selection['retrospective_id'] is not None:
                get_object_or_404(MeetingVersion.objects.filter(meeting__case=case, kind='retrospective',
                    evidence_id__in=public.values('pk')).only('pk'), pk=selection['retrospective_id'])
            if selection['report_evidence_id'] is not None:
                get_object_or_404(public.filter(kind='closure_report').only('pk'), pk=selection['report_evidence_id'])
            checked = delivery_closure.closure_requirements(dossier, selection)
    return {'revision': case.revision, 'as_of': checked['as_of'], 'ready_to_prepare': checked['ready_to_prepare'],
        'recorded_closure_id': checked['recorded_closure_id'],
        'checks': [{**row, 'finding': row.get('finding') or None} for row in checked['checks']]}


@endpoint(method='POST', request=obj({**VERSIONS, 'previous_evidence_id': nullable(ID),
    'report_text': {**TEXT, 'maxLength': 16000}, 'source_reference': {**TEXT, 'maxLength': 160},
    'reason': {**TEXT, 'maxLength': 2000},
}), response=obj({**WORK_RESULT['properties'], 'report_evidence_id': ID}), status=201,
          summary='Capture and bind a replacement closure report for fresh review against its exact predecessor')
@transaction.atomic
def replace_report(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, factory_closure.DEFINITION)
    work = FactoryWork.objects.select_for_update(of=('self',)).select_related('case', 'source_head').get(pk=work.pk)
    if work.revision != body['expected_revision']:
        raise ValidationError('STALE_VERSION: Open the current closure work before recording a replacement.')
    factory.access(actor, work.case, 'factory.manage', work.definition)
    case = lock_case(actor, work.case_id, 'evidence.add', body['case_revision'])
    work.case = case
    _, data, inputs = factory_closure.source(work, actor, current=False)
    if data['inputs']['report_evidence_id'] != body['previous_evidence_id']:
        raise ValidationError('STALE_VERSION: Review the current selected closure report.')
    report = body['report_text'].strip()
    reference = body['source_reference'].strip()
    if not report or not reference:
        raise ValidationError('Provide the observed report text and its source reference.')
    previous = inputs.get(body['previous_evidence_id'])
    if previous and previous.body == report:
        raise ValidationError('Submit the corrected report content or select an existing source.')
    evidence = add_evidence(actor, case.pk, 'closure_report', report, 'psl:closure-report:' + reference, case.revision)
    case.refresh_from_db(fields=['revision'])
    revised = factory_closure.correct(actor, work.pk, work.revision, case.revision,
        {**data['inputs'], 'report_evidence_id': evidence.pk}, body['reason'])
    wake_waiting(revised.pk)
    return {**result(revised), 'report_evidence_id': evidence.pk}
