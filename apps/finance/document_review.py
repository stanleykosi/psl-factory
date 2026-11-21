"""Private Finance files, AI proposals and human decisions on the exact source version."""
import csv
import hashlib
import io
import json
import logging
import os
import re
from datetime import timedelta
from pathlib import PurePath
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from adapters import case_uploads, finance_documents
from apps.core.models import Case
from apps.core.services import add_evidence, event
from apps.core.workbench import active, granted
from apps.identity.factory_access import department_cases, role_managed
from apps.identity.services import subject_actions
from apps.policy.registry import components
from .document_models import FinanceDocument, ReviewedFinanceFigure
from .document_forms import AccountsForm, FigureForm, ReviewForm
from .rules import decimal, number

LEASE = timedelta(minutes=5)


def review_rule():
    return components()['D06.import_unit_conversion']['reviewed_document_path']


def workspaces(actor):
    active(actor)
    if role_managed(actor):
        return department_cases(actor, review_rule()['reviewer_department'])
    return granted(actor, ['finance.read', 'finance.review'], include_roles=False).filter(kind='project')


def authorize(actor, case):
    if not workspaces(actor).filter(pk=case.pk).exists():
        raise PermissionDenied('Finance access to this project is required.')


def submit(actor, case, file):
    authorize(actor, case)
    if not file or PurePath(file.name).suffix.lower() not in finance_documents.EXTENSIONS:
        raise ValidationError('Choose a PDF, Excel, CSV, Word or text file.')
    data = file.read(case_uploads.LIMIT + 1)
    if not 0 < len(data) <= case_uploads.LIMIT:
        raise ValidationError('Choose a nonempty file of up to 5 MB.')
    sha = hashlib.sha256(data).hexdigest()
    existing = FinanceDocument.objects.filter(case=case, sha256=sha).first()
    if existing:
        return existing
    key = hashlib.sha256(f'finance-document:{case.pk}:{sha}'.encode()).hexdigest()
    case_uploads.put(key, data)
    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)
        authorize(actor, case)
        doc, created = FinanceDocument.objects.get_or_create(case=case, sha256=sha, defaults={
            'uploader': actor, 'requested_by': actor, 'name': PurePath(file.name).name[:160], 'key': key, 'size': len(data)})
        if created:
            event(actor, case, 'finance.document_received', document=doc.pk, sha256=sha)
        return doc


@transaction.atomic
def claim():
    expired = FinanceDocument.objects.select_for_update(skip_locked=True).filter(
        status='reading', updated_at__lt=timezone.now()-LEASE).order_by('pk')[:20]
    for doc in expired:
        doc.status, doc.message = 'held', 'The reading was interrupted. A Finance user can request another reading.'
        doc.save(update_fields=['status', 'message', 'updated_at'])
    doc = FinanceDocument.objects.select_for_update(skip_locked=True).filter(status='queued').order_by('pk').first()
    if doc:
        doc.attempt, doc.status, doc.model = uuid4(), 'reading', os.getenv('OPENROUTER_MODEL', '')
        doc.save(update_fields=['attempt', 'status', 'model', 'updated_at'])
    return doc


def run_once():
    doc = claim()
    if doc is None:
        return False
    result, message = {}, ''
    stage = 'private storage'
    try:
        authorize(doc.requested_by, doc.case)
        if not doc.model or not os.getenv('OPENROUTER_API_KEY'):
            raise ValidationError('The Finance reader is unavailable. Retry when the model is connected.')
        contents = case_uploads.read(doc)
        authorize(doc.requested_by, doc.case)
        stage = 'document reader'
        result = finance_documents.read(doc.model, doc.name, contents)
    except ValidationError as exc:
        message = ' '.join(exc.messages)
    except Exception as exc:
        logging.getLogger(__name__).warning('Finance document %s held in %s: %s (%s)', doc.pk, stage,
            type(exc).__name__, getattr(exc, 'code', None) or type(getattr(exc, 'reason', None)).__name__)
        message = 'The reading did not finish. Check the original and request another reading.'
    with transaction.atomic():
        current = FinanceDocument.objects.select_for_update().get(pk=doc.pk)
        if current.attempt != doc.attempt or current.status != 'reading':
            return True
        try:
            authorize(doc.requested_by, doc.case)
        except PermissionDenied:
            message = 'The person who submitted this reading no longer has Finance access.'
        current.status = 'held' if message else 'review'
        current.draft, current.message = ({} if message else result), message
        current.save(update_fields=['draft', 'message', 'status', 'updated_at'])
        event(doc.requested_by, doc.case, 'finance.document_reading_finished', document=doc.pk, status=current.status,
              attempt=str(doc.attempt), model=doc.model)
    return True


@transaction.atomic
def retry(actor, case, pk, attempt):
    authorize(actor, case)
    doc = FinanceDocument.objects.select_for_update().get(pk=pk, case=case)
    if doc.status != 'held' or str(doc.attempt) != attempt:
        raise ValidationError('This reading has changed. Refresh the page.')
    # The next request is made by the current Finance user. Keep original upload provenance.
    doc.status, doc.message, doc.requested_by = 'queued', '', actor
    doc.save(update_fields=['status', 'message', 'requested_by', 'updated_at'])
    event(actor, case, 'finance.document_reading_requested', document=doc.pk, previous_attempt=attempt)


def full_amount(raw, unit):
    factors = review_rule()['units']
    if unit not in factors:
        raise ValidationError('Confirm the units for each figure against the original.')
    raw = raw.strip()
    if raw.startswith('(') and raw.endswith(')') and not raw[1:-1].startswith(('+', '-')):
        raw = '-' + raw[1:-1]
    if not re.fullmatch(r'[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,8})?', raw):
        raise ValidationError('Enter a signed amount as printed, such as 1,250.50 or (250).')
    value = decimal(raw.replace(',', '')) * factors[unit]
    if abs(value) >= 10 ** 18:
        raise ValidationError('A converted figure exceeds the accounting import limit.')
    return number(value)


@transaction.atomic
def approve(actor, case, pk, attempt, values, rows):
    authorize(actor, case)
    doc = FinanceDocument.objects.select_for_update().get(case=case, pk=pk)
    if str(doc.attempt) != attempt or doc.status not in ['review', 'approved']:
        raise ValidationError('Open the current reading before approving it.')
    header = ReviewForm(values)
    if not header.is_valid() or not isinstance(rows, list) or not 1 <= len(rows) <= finance_documents.MAX_ROWS:
        raise ValidationError('Confirm the reporting details, units, and one to 100 figures against the original.')
    values = dict(header.cleaned_data)
    if values['unit'] == 'unknown':
        raise ValidationError('Confirm the file units, or choose separate units for each row.')
    if doc.draft.get('issues') and not values['note']:
        raise ValidationError('Explain how you resolved the questions raised during the reading.')
    confirmed = []
    for item in rows:
        form = FigureForm(item)
        if not form.is_valid():
            raise ValidationError('Each figure needs an account, amount, unit and a reference to the original.')
        row = form.cleaned_data
        unit = values['unit'] if row['unit'] == 'file' else row['unit']
        confirmed.append({**row, 'unit': unit, 'full_amount': full_amount(row['amount'], unit)})
    approved = {**values, 'rows': confirmed, 'decision_version': review_rule()['decision_version']}
    if values['control_total']:
        unit = values['unit'] if values['control_unit'] == 'file' else values['control_unit']
        expected = full_amount(values['control_total'], unit)
        if sum(decimal(r['full_amount']) for r in confirmed) != decimal(expected):
            raise ValidationError('The rows do not add up to the printed check total. Recheck the amounts, signs and units.')
        approved['full_control_total'] = expected
    if doc.status == 'approved':
        saved = {'decision_version': approved['decision_version'], 'no_total': not bool(doc.approved.get('control_total')),
                 **doc.approved}
        if saved != approved or doc.reviewer_id != actor.pk:
            raise ValidationError('Finance has already approved this file. Open the saved decision.')
        return doc
    doc.status, doc.approved, doc.reviewer, doc.reviewed_at = 'approved', approved, actor, timezone.now()
    doc.save(update_fields=['status', 'approved', 'reviewer', 'reviewed_at', 'updated_at'])
    ReviewedFinanceFigure.objects.bulk_create([ReviewedFinanceFigure(document=doc, account=r['account'],
        amount=r['full_amount'], currency=values['currency'], period=values['period'], citation=r['citation']) for r in confirmed])
    event(actor, case, 'finance.document_approved', document=doc.pk, sha256=doc.sha256, attempt=attempt)
    return doc


@transaction.atomic
def return_file(actor, case, pk, attempt, reason):
    authorize(actor, case)
    doc = FinanceDocument.objects.select_for_update().get(pk=pk, case=case)
    if doc.status != 'review' or str(doc.attempt) != attempt:
        raise ValidationError('Open the current reading before returning this file.')
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1000:
        raise ValidationError('Explain what Finance needs clarified.')
    doc.status, doc.message, doc.reviewer, doc.reviewed_at = 'returned', reason.strip(), actor, timezone.now()
    doc.save(update_fields=['status', 'message', 'reviewer', 'reviewed_at', 'updated_at'])
    event(actor, case, 'finance.document_returned', document=doc.pk, attempt=attempt)


@transaction.atomic
def handoff(actor, case, pk, entity, basis, completeness):
    """Send the already approved figures to the existing management accounts intake."""
    from apps.workflows import factory_accounting_intake as intake
    from . import services
    from .models import FinancialImport
    from .source_units import ASSERTION, SCHEMA, evidence_identity

    case = Case.objects.select_for_update().get(pk=case.pk)
    authorize(actor, case)
    doc = FinanceDocument.objects.select_for_update().get(pk=pk, case=case)
    if doc.status != 'approved':
        raise ValidationError('Finance must approve the extracted figures first.')
    if not AccountsForm({'entity': entity, 'basis': basis, 'completeness': completeness}).is_valid():
        raise ValidationError('Confirm the company code, accounting basis and coverage before using the figures.')
    values = doc.approved
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['account', 'amount', 'currency', 'period'])
    for row in values['rows']:
        writer.writerow([row['account'], row['full_amount'], values['currency'], values['period']])
    key = f'finance-document:{doc.pk}'
    private = f'role-work:finance-document:{doc.pk}'
    actions = ['case.read', 'finance.read', 'factory.start', 'finance.import', 'finance.validate',
               'finance.source', 'finance.calculate', 'evidence.add']
    with subject_actions(actor, case, actions):
        if doc.receipt_id:
            receipt = doc.receipt
            result = intake.latest(receipt)
            if result['status'] == 'configuration_needed' and receipt.actor_id == actor.pk:
                return intake.resume(actor, case.pk, receipt.pk, case.revision)
            return result
        source = add_evidence(actor, case.pk, 'finance_source', f'Finance approved file {doc.pk}, SHA-256 {doc.sha256}.', private)
        file = add_evidence(actor, case.pk, 'financial_input', buffer.getvalue(), private)
        batch = FinancialImport.objects.filter(case=case, source_sha256=file.sha256).first()
        if not batch:
            case.refresh_from_db()
            batch = services.capture_import(actor, case.pk, file.pk, case.revision)
        feed = 'trial-balance'
        assertion = {'schema': ASSERTION, 'batch_id': batch.pk, 'source_sha256': batch.source_sha256,
                     'input_key': key, 'feed': feed, 'unit': 'major_currency'}
        proof = add_evidence(actor, case.pk, 'finance_source_unit', json.dumps(assertion, sort_keys=True),
                             evidence_identity(batch.pk, key, feed))
        context = {'entity': entity, 'period': values['period'], 'currency': values['currency'],
                   'accounting_basis': basis, 'completeness': completeness, 'control_total': values.get('full_control_total'),
                   'extracted_at': doc.reviewed_at, 'source_evidence_id': source.pk, 'unit_declaration': {
                       'schema': SCHEMA, 'batch': {'id': batch.pk, 'sha256': batch.source_sha256}, 'input_key': key,
                       'declarations': [{'feed': feed, 'unit': 'major_currency', 'evidence': {
                           'id': proof.pk, 'version': proof.version, 'sha256': proof.sha256}}]}}
        case.refresh_from_db()
        result = intake.submit(actor, case.pk, key, file.pk, context, doc.name[:100], case.revision)
    doc.receipt_id = result['receipt']
    doc.save(update_fields=['receipt', 'updated_at'])
    return result
