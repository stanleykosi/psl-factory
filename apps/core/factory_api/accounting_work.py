"""Current management-account review stations, source rework and publication receipt."""

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.core.evidence_access import public_evidence
from apps.core.read_budget import limit_queries
from apps.core.services import lock_case
from apps.documents.models import PublicationJob
from apps.finance.models import FinanceDocumentBinding, FinanceRun, FinanceSource
from apps.workflows import factory_accounting as native, factory_accounting_corrections as corrections
from apps.workflows import factory_accounting_intake as intake, factory_accounting_views as native_views
from apps.workflows.factory_progress import wake_waiting
from apps.workflows.models import FactoryWork

from .accounting import AMOUNT, CCY, KEY, NOTE, PERIOD, REFERENCE, RESULT, intake_result
from .commands import require_line
from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .reviews import VERSIONS
from .work import WORK_RESULT, result


RETURN = obj({'work': ID, 'head': ID, 'decision': ID, 'source': ID, 'batch': ID, 'status_reason': TEXT,
              'entity': TEXT, 'period': PERIOD, 'currency': CCY, 'accounting_basis': TEXT})
TASK = obj({'id': ID, 'revision': REVISION, 'label': TEXT, 'can_claim': BOOLEAN, 'can_decide': BOOLEAN,
            'verdicts': array(choice('approve', 'return', 'reject'))})
PUBLICATION = obj({'id': ID, 'run_id': ID, 'version_id': ID, 'receipt_ids': array(ID), 'ledger_posted': {'const': False},
                   'published_at': DATETIME, 'verified_at': DATETIME})
STATION = obj({'label': TEXT, 'subjects': array(obj({'id': ID, 'status': TEXT,
                'review_id': nullable(ID), 'evidence_id': nullable(ID), 'reviewed_at': nullable(DATETIME)}))})


@endpoint(response=obj({**VERSIONS, 'state': TEXT, 'next_action': TEXT, 'finding': {'type': 'string'},
    'source_id': nullable(ID), 'mapping_id': nullable(ID), 'allocation_id': nullable(ID), 'formula_id': nullable(ID),
    'report_version_id': nullable(ID), 'publication': nullable(PUBLICATION), 'tasks': array(TASK, limit=50),
    'calculated_at': nullable(DATETIME), 'review_stations': array(STATION), 'delivery_jobs': array(
        obj({'id': ID, 'status': TEXT}), limit=30),
    'can_reassess': BOOLEAN, 'can_recheck_reviewers': BOOLEAN, 'can_reconcile': BOOLEAN, 'sources': array(ID, limit=30),
    'setup_missing': array(TEXT), 'correction': nullable(RETURN), 'predecessor_id': nullable(ID),
    'successor_id': nullable(ID), 'review_evidence': array(PROOF, limit=35)}),
    summary='Read the exact Finance review stations and source recovery with the current verified report receipt')
def detail(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    with limit_queries(1400):
        observed = native_views.presentation(actor, work)
        status = observed['accounting']['state'] or {}
        binding = FinanceDocumentBinding.objects.filter(pk=status.get('document')).only('version_id').first()
        publication = None
        accepted = observed['accounting']['verified_report']
        if accepted:
            publication = {'id': accepted['publication'], 'run_id': accepted['run'],
                           'version_id': accepted['document_version'], 'receipt_ids': accepted['receipt_ids'],
                           'ledger_posted': False, 'verified_at': work.updated_at,
                           'published_at': PublicationJob.objects.filter(publication_id=accepted['publication'])
                           .values_list('publication__created_at', flat=True).get()}
        calculated_at = FinanceRun.objects.filter(pk=status.get('formula')).values_list('created_at', flat=True).first()
        stations = native_views.review_stations(work, status, observed['tasks'])
        reviews = [{'label': station['label'], 'subjects': [
            {'id': item['subject'], 'status': item['status'],
             'review_id': item['decision'].pk if item['decision'] else None,
             'evidence_id': item['decision'].evidence_id if item['decision'] else None,
             'reviewed_at': item['decision'].created_at if item['decision'] else None}
            for item in station['subjects']]} for station in stations]
        earlier, later = corrections.predecessor(work), corrections.successor(work)
        correction = None
        if not later and observed['can_reassess'] and actor.pk == work.actor_id and work.status == 'followup_needed':
            try:
                pin = corrections.selection(actor, work)
            except (PermissionDenied, ValidationError):
                pass
            else:
                keys = ('work', 'head', 'decision', 'source', 'batch', 'entity', 'period', 'currency', 'accounting_basis')
                correction = {**{key: pin[key] for key in keys}, 'status_reason': pin['reason']}
        sources = FinanceSource.objects.filter(case=work.case, batch_id=work.request['batch'], entity=work.request['entity'])
        evidence = public_evidence(work.case.evidence.filter(kind='finance_review')).only('id', 'kind', 'version')
        return {'expected_revision': work.revision, 'case_revision': work.case.revision, 'state': observed['state'],
                'next_action': observed['next_action'], 'finding': observed['blocker'], 'source_id': status.get('source'),
                'mapping_id': status.get('mapping'), 'allocation_id': status.get('allocation'),
                'formula_id': status.get('formula'), 'report_version_id': binding.version_id if binding else None,
                'publication': publication, 'calculated_at': calculated_at, 'review_stations': reviews,
                'delivery_jobs': [{'id': pk, 'status': job_status} for pk, job_status, _ in status.get('jobs', [])[:30]],
                'can_reassess': not later and observed['can_reassess'],
                'can_reconcile': observed['can_reconcile'],
                'can_recheck_reviewers': observed['can_cancel'] and bool(native.review_routing_hold(work)),
                'tasks': [{'id': task.pk, 'revision': task.revision, 'label': task.label, 'can_claim': task.can_claim,
                           'can_decide': task.can_decide, 'verdicts': task.verdicts} for task in observed['tasks'][:50]],
                'sources': list(sources.order_by('-pk').values_list('pk', flat=True)[:30]),
                'setup_missing': (observed['accounting']['setup'] or {}).get('missing', []),
                'correction': correction, 'predecessor_id': earlier.data['previous_work'] if earlier else None,
                'successor_id': later.data['work'] if later else None, 'review_evidence': proof_rows(evidence.order_by('-pk')[:35])}


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'recheck_reviewers'}, 'expected_revision': REVISION}),
    obj({'action': {'const': 'reassess'}, **VERSIONS, 'source_id': ID, 'adjustment_ids': array(ID, limit=100), 'reason': NOTE}),
]}, response=WORK_RESULT, summary='Refresh exact reviewer routing or reassess the existing source and adjustments')
@transaction.atomic
def command(request, work_id, *, body):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    if body['action'] == 'recheck_reviewers':
        work = native.recheck_reviewers(actor, work.pk, body['expected_revision'])
    else:
        work = FactoryWork.objects.select_for_update(of=('self',)).get(pk=work.pk)
        lock_case(actor, work.case_id, 'finance.source', body['case_revision'])
        work = native.recheck(actor, work.pk, body['expected_revision'], body['source_id'],
                             body['adjustment_ids'], body['reason'])
    wake_waiting(work.pk)
    return result(work)


class CorrectedFile(forms.Form):
    case_revision = forms.IntegerField(min_value=1, max_value=REVISION['maximum'])
    head_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    decision_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    source_evidence_id = forms.IntegerField(min_value=1, max_value=ID['maximum'])
    idempotency_key = forms.RegexField(r'\A[A-Za-z0-9_.:-]{1,100}\Z', strip=False)
    reference = forms.RegexField(REFERENCE['pattern'])
    extracted_at = forms.DateTimeField()
    completeness = forms.ChoiceField(choices=[(value, value) for value in ('complete', 'partial', 'unknown')])
    control_total = forms.CharField(required=False, max_length=64)
    file = forms.FileField()


@endpoint(method='POST', multipart=True, status=201, response=RESULT,
    request=obj({'case_revision': REVISION, 'head_id': ID, 'decision_id': ID, 'source_evidence_id': ID,
                 'idempotency_key': KEY, 'reference': REFERENCE, 'extracted_at': DATETIME,
                 'completeness': choice('complete', 'partial', 'unknown'), 'control_total': AMOUNT,
                 'file': {'type': 'string', 'format': 'binary'}}, optional=('control_total',)),
    summary='Upload a corrected trial balance against its exact returned source and original extraction scope')
def upload_correction(request, work_id):
    actor = request.user
    work = require_line(actor, work_id, native.DEFINITION)
    form = CorrectedFile(request.POST, request.FILES)
    if not form.is_valid():
        raise ValidationError('Check the selected exact return, extraction context and corrected trial balance file.')
    data = form.cleaned_data
    earlier = native.source_for(work)
    dataset = earlier.batch.rows
    dimension = {(row['period'], row['currency']) for row in dataset}
    if len(dimension) != 1:
        raise ValidationError('Select an original source with one exact currency and period.')
    period, currency = dimension.pop()
    context = {key: data[key] for key in ('extracted_at', 'completeness', 'source_evidence_id')}
    context.update(entity=earlier.entity, period=period, currency=currency, accounting_basis=earlier.accounting_basis,
                   control_total=data['control_total'] or None)
    pin = {'work': work.pk, 'head': data['head_id'], 'decision': data['decision_id']}
    facts = intake.submit_corrected_file(actor, work.case_id, data['idempotency_key'], data['file'], context,
                                         data['reference'], data['case_revision'], pin)
    return intake_result(actor, work.case, facts)
