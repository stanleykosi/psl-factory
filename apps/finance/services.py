from django.db import transaction
from django.core.exceptions import ValidationError
from apps.core.services import lock_case, event, bump
from apps.identity.services import require
from apps.pmo.services import subject
from apps.policy.services import require_operation
from apps.policy.models import RegisteredReference
from adapters.finance_inputs import preview_csv
from .models import FinancialImport, ImportValidation, Handoff, InvoicePreparation


@transaction.atomic
def capture_import(actor, case_id, evidence_id, expected):
    case = lock_case(actor, case_id, 'finance.import', expected)
    evidence = subject(case, evidence_id, 'financial_input')
    rows, findings = preview_csv(evidence.body)
    if FinancialImport.objects.filter(case=case, source_sha256=evidence.sha256).exists():
        raise ValidationError('This exact source content is already captured')
    batch = FinancialImport.objects.create(case=case,evidence=evidence,source_sha256=evidence.sha256,rows=rows,findings=findings)
    event(actor,case,'finance.import_captured',batch=batch.pk,evidence=evidence.pk,rows=len(rows),findings=len(findings))
    bump(case)
    return batch


@transaction.atomic
def validate_import(actor, case_id, batch_id, expected):
    case = lock_case(actor, case_id, 'finance.validate', expected)
    batch = FinancialImport.objects.get(case=case,pk=batch_id)
    results = require_operation('financial_import.validate',case)
    conventions = next(r.configuration.envelope['value'] for r in results if r.component == 'D06.unit_sign_currency_period')
    data = RegisteredReference.objects.get(case=case,ref=conventions['artifact_ref'],version=conventions['artifact_version']).content
    findings = list(batch.findings)
    for row in batch.rows:
        for key in ['currency','period']:
            if row[key] != data[key]:
                findings.append({'line':row['line'],'field':key,'message':'Does not match configured source convention'})
    validation = ImportValidation.objects.create(batch=batch,policies={r.component:r.configuration.pk for r in results},
        findings=findings,status='invalid' if findings else 'validated_source')
    event(actor,case,'finance.import_validated',batch=batch.pk,validation=validation.pk,status=validation.status)
    bump(case)
    return validation


@transaction.atomic
def begin_invoice_preparation(actor, case_id, handoff_id, expected):
    case = lock_case(actor, case_id, 'finance.prepare', expected)
    handoff = Handoff.objects.get(case=case,pk=handoff_id)
    result, created = InvoicePreparation.objects.get_or_create(handoff=handoff)
    if not created:
        raise ValidationError('Preparation already exists for this handoff')
    event(actor,case,'finance.preparation_started',preparation=result.pk,handoff=handoff.pk)
    bump(case)
    return result
