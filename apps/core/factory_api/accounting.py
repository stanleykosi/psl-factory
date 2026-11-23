"""Controlled Finance intake, adjustment reviews and mapping readback."""

from datetime import datetime
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404

from apps.core.evidence_access import public_evidence
from apps.core.models import Audit, Case
from apps.core.read_budget import limit_queries
from apps.core.services import lock_case
from apps.finance import analysis
from apps.finance.models import FinanceAdjustment, FinanceRun
from apps.identity.services import require
from apps.workflows import factory_accounting_intake as intake
from apps.workflows.models import FactoryWork

from .delivery import PROOF, proof_rows
from .http import BOOLEAN, DATETIME, ID, REVISION, TEXT, array, choice, endpoint, nullable, obj
from .intake import progress_result


REFERENCE = {'type': 'string', 'pattern': r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$'}
KEY = {'type': 'string', 'pattern': r'^[A-Za-z0-9_.:-]{1,100}$'}
PERIOD = {'type': 'string', 'pattern': r'^\d{4}-(0[1-9]|1[0-2])$'}
CCY = {'type': 'string', 'pattern': '^[A-Z]{3}$'}
NOTE = {**TEXT, 'maxLength': 2000}
AMOUNT = {'type': 'string', 'maxLength': 128}
UNITS = choice(*dict(intake.UNIT_CHOICES))
VERDICT = choice('approve', 'return', 'reject')
PIN = obj({'work': ID, 'head': ID, 'decision': ID})
KIND = choice('additive', 'reclassification')
CONTEXT = obj({'entity': REFERENCE, 'period': PERIOD, 'currency': CCY,
               'accounting_basis': {**TEXT, 'maxLength': 100}, 'extracted_at': DATETIME,
               'completeness': choice('complete', 'partial', 'unknown'),
               'control_total': nullable(AMOUNT), 'source_evidence_id': ID})
FINDING = obj({'code': TEXT, 'message': TEXT, 'field': nullable(TEXT), 'line': nullable(ID)})
FINDING_CODES = {
    'Account is missing': 'account_missing',
    'Unknown amount; not zero': 'amount_missing',
    'Invalid exact decimal amount': 'amount_invalid',
    'Explicit three-letter currency required': 'currency_invalid',
    'Expected YYYY-MM period': 'period_invalid',
    'Does not match configured source convention': 'source_convention_mismatch',
    'Expected CSV columns: account,amount,currency,period': 'columns_invalid',
    'Import has no rows': 'rows_missing',
    'Malformed row or import row budget exceeded': 'rows_invalid',
    'Import budget exceeded (100,000 characters)': 'file_too_large',
    'Unknown or invalid exact source amount; not zero': 'amount_unavailable',
    'Currency/period does not match the selected source convention; no conversion': 'source_convention_mismatch',
    'Unmapped account': 'account_unmapped',
    'Multiply mapped account': 'account_mapping_ambiguous',
    'Duplicate source account requires explicit row handling': 'account_duplicate',
    'No effective mapping for this entity/period': 'mapping_missing',
}
RESULT = obj({'id': ID, 'case_revision': REVISION, 'status': TEXT, 'findings': array(TEXT),
              'finding_details': array(FINDING),
              'batch_id': nullable(ID), 'source_id': nullable(ID), 'work_id': nullable(ID),
              'can_confirm_units': BOOLEAN, 'successor_id': nullable(ID)})
VERSION = obj({'id': ID, 'case_revision': REVISION})


def finding_details(values, stage=None):
    details = []
    for value in values:
        if isinstance(value, dict):
            message, field, line = value['message'], value.get('field'), value.get('line')
            code = FINDING_CODES.get(message, 'unclassified')
        else:
            message, field, line = value, None, None
            declared = re.fullmatch(r'Line ([0-9]+): (period|currency) differs from declared .+', value)
            source_row = re.fullmatch(r'([0-9]+|adjustment:[0-9]+:[0-9]+): (.+)', value)
            if declared:
                line, field = int(declared[1]), declared[2]
                code = 'declared_context_mismatch'
            elif source_row:
                line = int(source_row[1]) if source_row[1].isdecimal() else None
                code = FINDING_CODES.get(source_row[2], 'unclassified')
            elif value.startswith('Missing source account: '):
                code = 'mapped_account_missing'
            else:
                code = FINDING_CODES.get(message, stage or 'unclassified')
        details.append({'code': code, 'message': message, 'field': field, 'line': line})
    return details


def receipt(actor, case, row, facts=None):
    facts = intake.latest(row) if facts is None else facts
    successor = Audit.objects.filter(case=case, actor=actor, action=intake.UNITS_CONFIRMED,
                                     data__previous=row.pk).values_list('data__successor', flat=True).first()
    details = finding_details(facts['findings'], facts['status'] if facts['status'] in (
        'source_units_needed', 'configuration_needed', 'followup_needed') else None)
    return {'id': row.pk, 'case_revision': case.revision, 'status': facts['status'],
            'findings': [item['message'] for item in details], 'finding_details': details,
            'batch_id': facts.get('batch'), 'source_id': facts.get('source'),
            'work_id': facts.get('work'), 'can_confirm_units': successor is None and intake.can_confirm_units(row, facts),
            'successor_id': successor}


def case_for(actor, case_id):
    case = get_object_or_404(Case, pk=case_id)
    for action in ('case.read', 'finance.read'):
        require(actor, case, action)
    return case


def intake_result(actor, case, result):
    if result.get('work'):
        work = FactoryWork.objects.filter(case=case, actor=actor, pk=result['work'],
                                          status='ready', background_progress__isnull=True).first()
        if work:
            progress_result(actor, work, True)
    case.refresh_from_db(fields=['revision'])
    return receipt(actor, case, get_object_or_404(Audit, case=case, actor=actor, pk=result['receipt']), result)


@endpoint(response=obj({'case_revision': REVISION, 'sources': array(PROOF, limit=40),
                        'extracts': array(PROOF, limit=40), 'submissions': array(RESULT, limit=30)}),
          summary='Read supplied trial balance and unit proof choices with the actor’s own intake receipts')
def intake_options(request, case_id):
    actor = request.user
    case = case_for(actor, case_id)
    intake.authority(actor, case)
    proofs = public_evidence(case.evidence.all()).only('id', 'kind', 'version').order_by('-pk')
    rows = Audit.objects.filter(case=case, actor=actor, action=intake.RECEIPT).order_by('-pk')[:30]
    return {'case_revision': case.revision, 'sources': proof_rows(proofs.filter(kind='finance_source')[:40]),
            'extracts': proof_rows(proofs.filter(kind='financial_input')[:40]),
            'submissions': [receipt(actor, case, row) for row in rows]}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'idempotency_key': KEY, 'reference': REFERENCE,
    'evidence_id': ID, 'context': CONTEXT, 'correction': nullable(PIN)}, optional=('correction',)),
    response=RESULT, status=201, summary='Submit an exact supplied trial balance with its extraction context')
def submit(request, case_id, *, body):
    actor = request.user
    case = case_for(actor, case_id)
    context = dict(body['context'], extracted_at=datetime.fromisoformat(body['context']['extracted_at']))
    result = intake.submit(actor, case.pk, body['idempotency_key'], body['evidence_id'], context,
                           body['reference'], body['case_revision'], correction=body.get('correction'))
    return intake_result(actor, case, result)


@endpoint(method='POST', request={'oneOf': [
    obj({'action': {'const': 'resume'}, 'case_revision': REVISION}),
    obj({'action': {'const': 'confirm_units'}, 'case_revision': REVISION, 'unit': UNITS, 'evidence_id': ID, 'note': NOTE}),
]}, response=RESULT, summary='Resume a held import or create the exact source unit confirmation successor')
def resume(request, case_id, receipt_id, *, body):
    actor = request.user
    case = case_for(actor, case_id)
    if body['action'] == 'confirm_units':
        result = intake.confirm_units(actor, case.pk, receipt_id, body['unit'], body['evidence_id'],
                                      body['note'], body['case_revision'])
    else:
        result = intake.resume(actor, case.pk, receipt_id, body['case_revision'])
    return intake_result(actor, case, result)


LINE = obj({'account': TEXT, 'amount': AMOUNT})
ADJUSTMENT = obj({'id': ID, 'source_id': ID, 'reference': REFERENCE, 'version': ID, 'kind': KIND,
                  'lines': array(LINE, limit=100), 'evidence_id': ID, 'review_id': nullable(ID),
                  'review_verdict': nullable(VERDICT), 'case_revision': REVISION})


@endpoint(response=ADJUSTMENT, summary='Read exact pending or reviewed Finance reporting adjustment and source context')
def adjustment(request, case_id, adjustment_id):
    case = case_for(request.user, case_id)
    row = get_object_or_404(FinanceAdjustment, pk=adjustment_id, source__case=case)
    analysis.source_for(case, row.source_id)
    review = row.financereview_set.order_by('-pk').first()
    return {'id': row.pk, 'source_id': row.source_id, 'reference': row.reference, 'version': row.number,
            'kind': row.kind, 'lines': row.lines, 'evidence_id': row.evidence_id,
            'review_id': review.pk if review else None, 'review_verdict': review.verdict if review else None,
            'case_revision': case.revision}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'role': {**TEXT, 'maxLength': 50},
    'verdict': VERDICT, 'evidence_id': ID, 'note': NOTE}), response=VERSION, status=201,
    summary='Review the current reporting adjustment independently of its source schedule')
def review_adjustment(request, case_id, adjustment_id, *, body):
    case = case_for(request.user, case_id)
    row = analysis.review(request.user, case.pk, 'adjustment', adjustment_id, body['role'], body['verdict'],
                          body['evidence_id'], body['note'], body['case_revision'])
    return {'id': row.pk, 'case_revision': row.case.revision}


@endpoint(method='POST', request=obj({'case_revision': REVISION, 'adjustment_ids': array(ID, limit=100)}),
    response=VERSION, status=201, summary='Prepare a current accounting note from exact reviewed source and adjustments')
def map_source(request, case_id, source_id, *, body):
    case = case_for(request.user, case_id)
    row = analysis.map_source(request.user, case.pk, source_id, body['adjustment_ids'], body['case_revision'])
    return {'id': row.pk, 'case_revision': row.case.revision}


MAPPED_ROW = obj({'account': TEXT, 'amount': nullable(AMOUNT), 'source_line': {'anyOf': [ID, TEXT, {'type': 'null'}]},
                  'source_evidence_id': ID, 'report_line': nullable(TEXT), 'origin': TEXT})


@endpoint(response=obj({'id': ID, 'source_id': ID, 'entity': TEXT, 'period': PERIOD, 'currency': CCY,
    'unit': {'const': 'major_currency'}, 'status': TEXT, 'findings': array(TEXT), 'finding_details': array(FINDING),
    'rows': array(MAPPED_ROW, limit=100),
    'has_more_rows': BOOLEAN, 'ledger_posted': {'const': False}}), query={'after_row': {'type': 'integer', 'minimum': 0}},
    summary='Read exact current accounting note rows and source evidence without ledger effects')
def mapping(request, case_id, mapping_id):
    with transaction.atomic(), limit_queries(800):
        actor = request.user
        case_for(actor, case_id)
        case = lock_case(actor, case_id, 'finance.read')
        row = get_object_or_404(FinanceRun.objects.select_related('source__batch', 'source__case'), pk=mapping_id,
                                case=case, kind='mapping')
        analysis.ensure_current(row)
        raw = request.GET.get('after_row', '0')
        if not raw.isascii() or not raw.isdecimal() or len(raw) > 9:
            raise ValidationError('Choose a valid accounting note page.')
        offset = int(raw)
        result = row.result
        selected = result['rows'][offset:offset + 101]
        rows = [{'account': item['account'], 'amount': item['amount'], 'source_line': item['source_line'],
                 'source_evidence_id': item['source_evidence'], 'report_line': item['report_line'], 'origin': item['origin']}
                for item in selected[:100]]
        return {'id': row.pk, 'source_id': row.source_id,
                **{key: result[key] for key in ('entity', 'period', 'currency', 'unit', 'status', 'findings')},
                'finding_details': finding_details(result['findings']),
                'rows': rows, 'has_more_rows': len(selected) > 100, 'ledger_posted': False}
