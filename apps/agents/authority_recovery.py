from django.db import transaction
from apps.core.services import lock_case,event
from apps.identity.services import require
from adapters.authority_recovery import LocalAuthorityRecoveryAdapter
from apps.pmo.recoveries import request_for
from .models import AgentRun


@transaction.atomic
def investigate_recovery(actor,case_id,request_id,expected):
    case=lock_case(actor,case_id,'agent.authority',expected);require(actor,case,'authority.read')
    r=request_for(case,request_id);result=LocalAuthorityRecoveryAdapter().read(case,r.pk)
    result.update(capability='A03/A04/A07 historical authority comparison',approval_granted=False,
        next_work='Resolve cited source changes, then obtain each configured current human decision. Preserve original times and independent financial/release controls.')
    run=AgentRun.objects.create(case=case,actor=actor,evidence=r.evidence,provider='deterministic-authority-investigation-v1',process_id='P62' if r.outcome_id else 'P09',result=result)
    event(actor,case,'agent.authority_investigation',run=run.pk,request=r.pk);return run
