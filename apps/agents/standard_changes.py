from django.db import transaction
from apps.core.services import lock_case, event
from apps.identity.services import require
from adapters.standard_changes import LocalStandardChangeAdapter
from .models import AgentRun


@transaction.atomic
def investigate_standard(actor, case_id, version_id, expected):
    case = lock_case(actor, case_id, 'agent.changes', expected)
    require(actor, case, 'change.read')
    result = LocalStandardChangeAdapter().investigate(case, version_id)
    result.update(capability='A03/A07/A08 Standard procedure and authority investigation',
        approval_granted=False, deployment_authorized=False, remote_procedure_verified=False,
        next_work='PM confirms procedure applicability; mapped humans decide. Conditional, costing and release controls stay independent.')
    from apps.pmo.models import ChangeVersion
    run = AgentRun.objects.create(case=case, actor=actor,
        evidence=ChangeVersion.objects.get(pk=version_id, change__case=case).evidence,
        provider='deterministic-standard-investigation-v1', process_id='P56', result=result)
    event(actor, case, 'agent.standard_investigation', run=run.pk, version=version_id)
    return run
