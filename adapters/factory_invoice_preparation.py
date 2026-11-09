"""Scoped native invoice investigation; no arithmetic duplication or external effects."""
from typing import TypedDict
from django.core.exceptions import ValidationError
from apps.workflows.models import FactoryWork


class InvoiceInvestigationResult(TypedDict):
    agent_run: int
    coverage: int
    evidence_ids: list[int]


class NativeInvoicePreparationAdapter:
    def investigate(self, work: FactoryWork) -> InvoiceInvestigationResult:
        if work.definition != 'pmo-finance/v1':
            raise ValidationError('Invoice investigation requires its exact registered work type')
        from apps.agents.billing import investigate
        from apps.workflows.factory_invoice_intake import bound, check
        prep = check(work, work.execution_actor) if bound(work) else None
        run = investigate(work.execution_actor, work.case_id, work.request['coverage'], prep.pk if prep else None, work.case.revision)
        return {'agent_run': run.pk, 'coverage': work.request['coverage'],
                'evidence_ids': [row['id'] for row in run.result['citations']]}


class NativeFixedContractPreparationAdapter:
    """Explicit internal command only. Never draft, approve or issue an invoice."""
    def prepare(self, actor, case_id: str, charge_id: int, expected: int) -> dict:
        from apps.finance.fixed_charge import prepare, recovered
        from apps.finance.preparation_continuation import latest
        prep = prepare(actor, case_id, charge_id, expected)
        binding = recovered(actor, prep)
        continuation = latest(prep.fixed_charge.request)
        return {'preparation_id': prep.pk, 'receipt_id': binding.pk, 'original_receipt_id': binding.receipt_id,
                'continuation_id': continuation.pk if continuation else None,
                'status': prep.result['status'], 'invoice_issued': False}
