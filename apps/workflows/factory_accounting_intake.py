"""Controlled F02 intake receipts over native Finance services.

Append-only Audit receipts are serialized by the native case lock. Submission
identity is distinct from content identity: a repeat submission gets a receipt,
not a second import. These are local intake receipts, not QuickBooks receipts.
"""
import hashlib
import json
import re
from datetime import datetime
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.evidence_access import restricted
from apps.core.models import Audit
from apps.core.services import add_evidence, lock_case, event, bump
from apps.identity.services import require
from apps.pmo.services import subject
from apps.policy.services import require_operation, reference_values, PolicyHold
from apps.finance import analysis, services
from apps.finance.models import FinancialImport, FinanceSource, ImportValidation
from apps.finance.rules import decimal, number
from . import factory_accounting as accounting

RECEIPT = 'factory.accounting_intake_received'
RESULT = 'factory.accounting_intake_result'
UNITS_CONFIRMED = 'factory.accounting_intake_units_confirmed'
UNIT_CHOICES = [
    ('major_currency', 'Currency units as shown'),
    ('thousands_currency', 'Thousands'),
    ('millions_currency', 'Millions'),
]


def authority(actor, case):
    from .factory import access
    access(actor, case, 'factory.start', accounting.DEFINITION)
    for action in ['finance.import', 'finance.validate', 'finance.source', 'evidence.add']:
        require(actor, case, action)


def latest(receipt):
    result = Audit.objects.filter(case=receipt.case, action=RESULT, data__receipt=receipt.pk).order_by('-pk').first()
    return result.data if result else {'receipt': receipt.pk, 'status': 'received', 'findings': []}


def record(actor, case, receipt, status, findings, **extra):
    data = {'receipt': receipt.pk, 'status': status, 'findings': findings, **extra}
    if latest(receipt) != data:
        event(actor, case, RESULT, **data)
        bump(case)
    return data


@transaction.atomic
def submit_corrected_file(actor, case_id, key, file, context, reference, expected, correction):
    from . import factory_accounting_corrections as corrections

    case = lock_case(actor, case_id, 'factory.start', expected)
    authority(actor, case)
    if (not file or not file.name.lower().endswith('.csv') or file.size > 400000
            or not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', key)):
        raise ValidationError('Choose the corrected CSV export within the accounting import size limit.')
    try:
        body = file.read(400001).decode('utf-8-sig')
    except UnicodeError:
        raise ValidationError('Upload the corrected CSV as UTF-8 text.') from None
    if not body.strip() or len(body) > 100000:
        raise ValidationError('Use a nonempty CSV with at most 100,000 characters.')
    location = f'psl:accounting-correction/{actor.pk}/{key}'
    sha = hashlib.sha256(body.encode()).hexdigest()
    evidence = case.evidence.filter(kind='financial_input', source=location, sha256=sha,
                                    created_by=actor).defer('body').first()
    previous = Audit.objects.filter(case=case, action=RECEIPT, data__key=key).first()
    if previous is None:
        pin = corrections.locked_selection(actor, case, correction)
        corrections.check_file(pin, context, sha)
    if evidence is None:
        evidence = add_evidence(actor, case.pk, 'financial_input', body, location, case.revision)
        case.refresh_from_db(fields=['revision'])
    return submit(actor, case.pk, key, evidence.pk, context, reference, case.revision, correction=correction)


@transaction.atomic
def submit(actor, case_id, key, evidence_id, context, reference, expected, *, correction=None):
    case = lock_case(actor, case_id, 'factory.start', expected)
    authority(actor, case)
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', key):
        raise ValidationError('Supply a bounded intake submission identity')
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 100:
        raise ValidationError('Supply a reporting work reference')
    fields = {'entity', 'period', 'currency', 'accounting_basis', 'extracted_at', 'completeness', 'control_total', 'source_evidence_id'}
    if not isinstance(context, dict) or set(context) not in [fields, fields | {'unit_declaration'}]:
        raise ValidationError('Exact extraction and reporting context required')
    if not isinstance(context['entity'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}', context['entity']):
        raise ValidationError('Explicit entity identifier required')
    if not isinstance(context['accounting_basis'], str) or not context['accounting_basis'].strip() or len(context['accounting_basis']) > 100:
        raise ValidationError('Explicit accounting basis required')
    if not isinstance(context['period'], str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', context['period']):
        raise ValidationError('Explicit YYYY-MM reporting period required')
    if not isinstance(context['currency'], str) or not re.fullmatch(r'[A-Z]{3}', context['currency']):
        raise ValidationError('Explicit three-letter source currency required')
    extracted = context['extracted_at']
    if not isinstance(extracted, datetime) or timezone.is_naive(extracted) or extracted > timezone.now():
        raise ValidationError('Actual aware extraction time must not be in the future')
    if context['completeness'] not in ['complete', 'partial', 'unknown']:
        raise ValidationError('Declare source completeness')
    source_evidence = subject(case, context['source_evidence_id'], 'finance_source')
    evidence = subject(case, evidence_id, 'financial_input')
    payload = {**context, 'extracted_at': extracted.isoformat(), 'source_evidence_id': source_evidence.pk,
               'control_total': None if context['control_total'] is None else number(decimal(context['control_total'])),
               'evidence_id': evidence.pk, 'sha256': evidence.sha256, 'reference': reference}
    old = Audit.objects.filter(case=case, action=RECEIPT, data__key=key).first()
    if old:
        if old.actor_id != actor.pk or old.data['request'] != payload or old.data.get('correction') != correction:
            raise ValidationError('IDEMPOTENCY_CONFLICT: intake identity already has different inputs or initiator')
        return resume(actor, case.pk, old.pk, case.revision)
    if correction is not None:
        from . import factory_accounting_corrections as corrections

        if restricted(evidence) or restricted(source_evidence):
            raise PermissionDenied('Use available Finance intake evidence for the correction.')
        pin = corrections.locked_selection(actor, case, correction)
        corrections.check_file(pin, payload, evidence.sha256)
    batch = FinancialImport.objects.filter(case=case, source_sha256=evidence.sha256).first()
    findings = []
    if not batch:
        try:
            batch = services.capture_import(actor, case.pk, evidence.pk, case.revision)
        except ValidationError as exc:
            findings = exc.messages
        case.refresh_from_db()
    receipt = event(actor, case, RECEIPT, schema='factory-accounting-intake-receipt/v1', key=key,
                    request=payload, batch=batch.pk if batch else None, parser_findings=findings,
                    **({'correction': correction} if correction is not None else {}))
    bump(case)
    return resume(actor, case.pk, receipt.pk, case.revision)


@transaction.atomic
def resume(actor, case_id, receipt_id, expected):
    case = lock_case(actor, case_id, 'factory.start', expected)
    authority(actor, case)
    receipt = Audit.objects.filter(case=case, pk=receipt_id, action=RECEIPT).first()
    if not receipt or receipt.actor_id != actor.pk:
        raise PermissionDenied('Resume only your exact intake receipt in this workspace')
    payload = receipt.data['request']
    evidence = subject(case, payload['evidence_id'], 'financial_input')
    source_evidence = subject(case, payload['source_evidence_id'], 'finance_source')
    if evidence.sha256 != payload['sha256']:
        raise ValidationError('Intake source hash changed')
    prior = latest(receipt)
    if prior['status'] in ['started', 'source_units_needed']:
        # Observation only. Never promote a held receipt or reset completed work on retry.
        return prior
    pin = None
    correction = receipt.data.get('correction')
    if correction is not None:
        from . import factory_accounting_corrections as corrections

        if restricted(evidence) or restricted(source_evidence):
            raise PermissionDenied('Use available Finance intake evidence for the correction.')
        pin = corrections.locked_selection(actor, case, correction)
        corrections.check_file(pin, payload, evidence.sha256)
    if receipt.data['parser_findings']:
        return record(actor, case, receipt, 'quarantined', receipt.data['parser_findings'])
    batch = FinancialImport.objects.get(case=case, pk=receipt.data['batch'], source_sha256=payload['sha256'])
    mismatches = [f"Line {row['line']}: {field} differs from declared {payload[field]}" for row in batch.rows
                  for field in ['period', 'currency'] if row[field] != payload[field]]
    if mismatches:
        return record(actor, case, receipt, 'quarantined', mismatches, batch=batch.pk)
    try:
        policies = require_operation('financial_import.validate', case)
    except PolicyHold as exc:
        return record(actor, case, receipt, 'configuration_needed', exc.messages, batch=batch.pk)
    pins = {item.component: item.configuration.pk for item in policies}
    validation = ImportValidation.objects.filter(batch=batch, policies=pins).order_by('-pk').first()
    if not validation:
        validation = services.validate_import(actor, case.pk, batch.pk, case.revision)
        case.refresh_from_db()
    if validation.status != 'validated_source':
        return record(actor, case, receipt, 'quarantined', validation.findings, batch=batch.pk, validation=validation.pk)
    source_fields = {k: payload[k] for k in ['entity', 'accounting_basis', 'completeness', 'control_total']}
    source_fields.update(extracted_at=datetime.fromisoformat(payload['extracted_at']), evidence_id=payload['source_evidence_id'])
    from apps.finance.source_units import capture as capture_units
    units = capture_units(batch, payload.get('unit_declaration'))
    source = FinanceSource.objects.filter(case=case, batch=batch, unit_declaration=units, **source_fields).order_by('-pk').first()
    if source and batch.contexts.order_by('-pk').first().pk != source.pk:
        return record(actor, case, receipt, 'followup_needed', ['This extraction context was superseded; select current source-owned inputs.'], batch=batch.pk)
    if not source:
        source = analysis.capture_source(actor, case.pk, batch.pk, payload['entity'], payload['accounting_basis'],
                                        source_fields['extracted_at'], payload['completeness'], payload['control_total'],
                                        payload['source_evidence_id'], case.revision, unit_declaration=units)
        case.refresh_from_db()
    from apps.finance.source_units import require_mapping
    try:
        require_mapping(source)
    except ValidationError as exc:
        return record(actor, case, receipt, 'source_units_needed', exc.messages, batch=batch.pk,
                      validation=validation.pk, source=source.pk, source_units=source.unit_state)
    if pin:
        from apps.finance.models import FinanceReview
        from .models import FactoryWork

        if (FinanceReview.objects.filter(case=case, purpose='source', source=source).exists()
                or FactoryWork.objects.filter(case=case, definition=accounting.DEFINITION,
                    request__batch=batch.pk, request__entity=source.entity).exists()):
            return record(actor, case, receipt, 'followup_needed',
                          ['This extract already has accounting work or a source decision. Choose a fresh corrected extract.'],
                          batch=batch.pk, validation=validation.pk, source=source.pk)
    try:
        work = accounting.start(actor, case.pk, 'intake:' + str(receipt.pk), source.pk, [], payload['reference'], case.revision)
    except ValidationError as exc:
        # Preserve a valid supplied source if an existing accounting work needs explicit rework.
        case.refresh_from_db()
        return record(actor, case, receipt, 'followup_needed', exc.messages, batch=batch.pk, source=source.pk, validation=validation.pk)
    case.refresh_from_db()
    if pin:
        corrections.link(actor, case, pin, receipt, work, source)
    return record(actor, case, receipt, 'started', [], batch=batch.pk, validation=validation.pk, source=source.pk, work=work.pk)


def can_confirm_units(receipt, result):
    return result['status'] == 'source_units_needed' and not receipt.data['request'].get('unit_declaration')


@transaction.atomic
def confirm_units(actor, case_id, receipt_id, unit, proof_id, note, expected):
    from apps.finance.source_units import ASSERTION, SCHEMA, evidence_identity

    case = lock_case(actor, case_id, 'factory.start', expected)
    authority(actor, case)
    receipt = Audit.objects.filter(case=case, pk=receipt_id, action=RECEIPT, actor=actor).first()
    if receipt is None:
        raise PermissionDenied('Confirm units on your own held submission in this workspace.')
    if not isinstance(unit, str) or unit not in dict(UNIT_CHOICES) or not isinstance(note, str) or not note.strip() or len(note) > 2000:
        raise ValidationError('Choose the observed units and explain where you confirmed them.')
    proof = subject(case, proof_id, 'finance_source', metadata_only=True)
    if restricted(proof):
        raise ValidationError('Choose available source evidence for the units.')
    require(proof.created_by, case, 'evidence.add')
    current = latest(receipt)
    if not can_confirm_units(receipt, current):
        raise ValidationError('Choose a submission held because its original file has no declared units.')
    prior = Audit.objects.filter(case=case, action=UNITS_CONFIRMED, data__previous=receipt.pk).first()
    confirmation = {'unit': unit, 'proof': proof.pk, 'reason': note.strip()}
    if prior:
        if any(prior.data.get(key) != value for key, value in confirmation.items()):
            raise ValidationError('This held submission already has a successor. Open the newer submission.')
        return latest(Audit.objects.get(case=case, actor=actor, action=RECEIPT, pk=prior.data['successor']))

    payload = receipt.data['request']
    batch = FinancialImport.objects.get(case=case, pk=current['batch'], source_sha256=payload['sha256'])
    if batch.contexts.order_by('-pk').values_list('pk', flat=True).first() != current['source']:
        raise ValidationError('The original extraction context changed. Open the latest source before continuing.')
    input_key, feed = f'unit-confirmation:{receipt.pk}', 'trial-balance'
    statement = {'schema': ASSERTION, 'batch_id': batch.pk, 'source_sha256': batch.source_sha256,
                 'input_key': input_key, 'feed': feed, 'unit': unit}
    evidence = add_evidence(actor, case.pk, 'finance_source_unit', json.dumps(statement, sort_keys=True),
                            evidence_identity(batch.pk, input_key, feed), case.revision)
    case.refresh_from_db()
    context = {key: payload[key] for key in ('entity', 'period', 'currency', 'accounting_basis',
                                             'completeness', 'control_total', 'source_evidence_id')}
    context.update(extracted_at=datetime.fromisoformat(payload['extracted_at']), unit_declaration={
        'schema': SCHEMA, 'batch': {'id': batch.pk, 'sha256': batch.source_sha256}, 'input_key': input_key,
        'declarations': [{'feed': feed, 'unit': unit,
                          'evidence': {'id': evidence.pk, 'version': evidence.version, 'sha256': evidence.sha256}}],
    })
    result = submit(actor, case.pk, input_key, payload['evidence_id'], context, payload['reference'], case.revision,
                    correction=receipt.data.get('correction'))
    event(actor, case, UNITS_CONFIRMED, previous=receipt.pk, successor=result['receipt'],
          unit_evidence=evidence.pk, **confirmation)
    return result


def provenance(actor, work, *, execution=False):
    """Bounded historical facts, never a review, eligibility input or authority grant."""
    from .factory import access
    if type(execution) is not bool or work.definition != accounting.DEFINITION:
        raise ValidationError('Exact accounting provenance scope required')
    access(actor, work.case, 'factory.execute' if execution else 'factory.read', accounting.DEFINITION)
    selected = accounting.source_for(work, allow_stale=True)
    query = Audit.objects.filter(case=work.case, action=RESULT, data__status='started', data__work=work.pk).order_by('-pk')
    total = query.count()
    records = list(query[:50])
    items = []
    unavailable = 0
    for result in records:
        data = result.data
        receipt = Audit.objects.filter(case=work.case, action=RECEIPT, pk=data.get('receipt')).first()
        source = FinanceSource.objects.select_related('batch__evidence', 'evidence').filter(
            case=work.case, pk=data.get('source'), batch_id=work.request['batch'], entity=work.request['entity']).first()
        validation = ImportValidation.objects.filter(pk=data.get('validation'), batch_id=data.get('batch')).first()
        payload = receipt.data.get('request', {}) if receipt else {}
        evidence = work.case.evidence.filter(pk=payload.get('evidence_id'), kind='financial_input').first()
        try:
            linked = (receipt is not None and receipt.data.get('schema') == 'factory-accounting-intake-receipt/v1'
                      and receipt.actor_id == result.actor_id == work.actor_id and source is not None
                      and validation is not None and validation.status == 'validated_source'
                      and evidence is not None and receipt.data['batch'] == data['batch'] == source.batch_id
                      and evidence.sha256 == payload['sha256'] == source.batch.source_sha256 == source.batch.evidence.sha256
                      and payload['source_evidence_id'] == source.evidence_id
                      and source.evidence.case_id == work.case_id and source.evidence.kind == 'finance_source'
                      and source.batch.evidence.case_id == work.case_id and source.batch.case_id == work.case_id
                      and payload['entity'] == source.entity and payload['reference'] == work.request['reference']
                      and all(payload[key] == getattr(source, key) for key in ['accounting_basis', 'completeness', 'control_total'])
                      and datetime.fromisoformat(payload['extracted_at']) == source.extracted_at
                      and all(row[field] == payload[field] for row in source.batch.rows for field in ['currency', 'period']))
        except (KeyError, TypeError, ValueError):
            linked = False
        if not linked:
            unavailable += 1
            continue
        items.append({'receipt': receipt.pk, 'result': result.pk, 'work': work.pk, 'source': source.pk,
                      'batch': source.batch_id, 'validation': validation.pk, 'validation_status': validation.status,
                      'validation_policies': validation.policies, 'submitted_evidence': evidence.pk,
                      'import_evidence': source.batch.evidence_id, 'context_evidence': source.evidence_id,
                      'sha256': payload['sha256'], 'entity': payload['entity'], 'period': payload['period'],
                      'currency': payload['currency'], 'extracted_at': payload['extracted_at'],
                      'selected_source': source.pk == selected.pk})
    return {'schema': 'factory-accounting-intake-provenance/v1', 'historical_only': True,
            'description': 'Historical local intake and validation facts; not current Finance approval or QuickBooks authenticity.',
            'selected_source': selected.pk, 'total': total, 'examined': len(records), 'shown': len(items),
            'unavailable': unavailable, 'omitted': max(0, total-len(records)), 'items': items,
            'selected_source_recorded': any(item['selected_source'] for item in items)}
