from django.core.exceptions import ValidationError
from django.db import transaction
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.pmo.models import Issue
from apps.pmo.issue_access import state_public
from .models import AgentRun

@transaction.atomic
def investigate_issues(actor,case_id,expected):
    case=lock_case(actor,case_id,'agent.issues',expected);require(actor,case,'issue.read')
    issues=[i for i in Issue.objects.filter(case=case).select_related('case','current').order_by('pk')[:1001] if i.current and state_public(i.current)]
    if not issues or len(issues)>1000:raise ValidationError('Issue investigation requires 1 to 1000 case-scoped records')
    from apps.pmo.issue_references import report
    # Re-check source-reader authority even for legacy diagnostics containing only link identities.
    for issue in issues:report(actor,issue)
    findings=[{'issue_id':i.pk,'state_id':i.current_id,'evidence_id':i.current.evidence_id,'severity':i.current.severity,
        'acknowledged':i.current.acknowledged_at is not None,'status':i.current.status,
        'critical_root_cause_missing':i.current.severity=='Critical' and i.current.root_cause_id is None,
        'external_owner_refs':i.current.external_links} for i in issues]
    run=AgentRun.objects.create(case=case,actor=actor,evidence=issues[0].current.evidence,provider='deterministic-issue-investigation-v1',process_id='P50',
        result={'capability':'A03/A08 owned issue evidence investigation','findings':findings,'sla_evaluated':False,
            'automatic_escalation_authorized':False,'external_risk_or_incident_lifecycle_changed':False})
    event(actor,case,'agent.issues_investigated',run=run.pk)
    return run
