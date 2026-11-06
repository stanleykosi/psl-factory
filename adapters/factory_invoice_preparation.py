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
        run = investigate(work.execution_actor, work.case_id, work.request['coverage'], None, work.case.revision)
        return {'agent_run': run.pk, 'coverage': run.result['coverage'],
                'evidence_ids': [row['id'] for row in run.result['citations']]}
