from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.pmo.emergencies import outcome_for, timing, retrospective_inputs
from adapters.emergencies import LocalEmergencyEvidenceAdapter
from .models import AgentRun


@transaction.atomic
def investigate_emergency(actor,case_id,outcome_id,expected):
    case=lock_case(actor,case_id,'agent.emergencies',expected);require(actor,case,'emergency.read')
    outcome=outcome_for(case,outcome_id)
    result=LocalEmergencyEvidenceAdapter().read(case,outcome)
    result['timing']=timing(case,outcome);result['findings']=[]
    try:result['retrospective']=retrospective_inputs(case,outcome)
    except (ValidationError,PermissionDenied) as exc:result['findings']=exc.messages if isinstance(exc,ValidationError) else [str(exc)]
    result.update(capability='A03/A04/A07/A08 emergency source, timing and authority investigation',
        approval_granted=False,deployment_dispatched=False,external_authenticity_verified=False,
        next_work='Investigate cited source gaps and late/missing decisions with human owners; do not backdate authorization or waive financial/release controls.')
    run=AgentRun.objects.create(case=case,actor=actor,evidence=outcome.evidence,provider='deterministic-emergency-investigation-v1',process_id='P62',result=result)
    event(actor,case,'agent.emergency_investigation',run=run.pk,outcome=outcome.pk);return run
