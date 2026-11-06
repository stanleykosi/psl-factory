from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.models import Case
from apps.core.evidence_access import restricted
from apps.core.services import lock_case, event
from apps.identity.services import require
from apps.pmo.services import subject
from apps.pmo.models import ActionItem
from apps.pmo.meetings import action_timing
from .models import AgentRun


class SyntheticMeetingProvider:
    name='synthetic-meeting-extractive-v1'
    def suggest(self,evidence):
        lines=[line.strip() for line in evidence.body.splitlines() if line.strip()][:8]
        return {'decisions':[{'quote':lines[0],'evidence_id':evidence.pk}] if lines else [],
            'actions':[{'quote':line,'evidence_id':evidence.pk,'owner_id':None,'due_at':None} for line in lines[1:]]}


def suggest_commitments(actor,case_id,evidence_id,expected,provider=None):
    case=Case.objects.get(pk=case_id);require(actor,case,'agent.meetings')
    evidence=subject(case,evidence_id)
    if restricted(evidence):raise ValidationError('Restricted source evidence requires its domain investigation interface')
    if len(evidence.body)>16000:raise ValidationError('Meeting extraction input budget exceeded')
    if provider is None:
        if not case.synthetic:raise ValidationError('Operational meeting interpretation requires an approved real provider')
        provider=SyntheticMeetingProvider()
    result=provider.suggest(evidence)
    if not isinstance(result,dict) or set(result)!={'decisions','actions'}:
        raise ValidationError('Meeting provider returned an ungranted operation')
    for kind,values in result.items():
        if not isinstance(values,list) or len(values)>12:raise ValidationError('Meeting proposal budget exceeded')
        for proposal in values:
            required={'quote','evidence_id'}|({'owner_id','due_at'} if kind=='actions' else set())
            if not isinstance(proposal,dict) or set(proposal)!=required or not isinstance(proposal['quote'],str) or not proposal['quote'] or len(proposal['quote'])>2000 or proposal['quote'] not in evidence.body or type(proposal['evidence_id']) is not int or proposal['evidence_id']!=evidence.pk:
                raise ValidationError('Every suggestion needs an exact citation within the granted source')
            if kind=='actions' and (proposal['owner_id'] is not None or proposal['due_at'] is not None):
                raise ValidationError('Owner/deadline assignment requires a separate authenticated human command')
    with transaction.atomic():
        case=lock_case(actor,case_id,'agent.meetings',expected)
        run=AgentRun.objects.create(case=case,actor=actor,evidence=evidence,provider=provider.name,process_id='P43',
            result={'capability':'A02/A04 cited meeting proposals','proposals':result,'human_confirmation_required':True,'scope_changed':False})
        event(actor,case,'agent.meeting_suggestions',run=run.pk,evidence=evidence.pk)
        return run


@transaction.atomic
def investigate_actions(actor,case_id):
    case=lock_case(actor,case_id,'agent.meetings')
    require(actor,case,'meeting.read')
    items=list(ActionItem.objects.filter(case=case).select_related('current').order_by('pk')[:1001])
    if not items:raise ValidationError('Record an evidence-linked action before running the commitment investigation')
    if len(items)>1000:raise ValidationError('Action investigation budget exceeded')
    findings=[{'action_id':item.pk,'state_id':item.current_id,'evidence_id':item.current.evidence_id,
        'owner_missing':item.current.owner_id is None,'deadline_missing':item.current.due_at is None,
        'timing':action_timing(item.current),'status':item.current.status} for item in items]
    run=AgentRun.objects.create(case=case,actor=actor,evidence_id=items[0].current.evidence_id,provider='deterministic-action-investigation-v1',process_id='P04',
        result={'capability':'A04/A08 commitment evidence investigation','as_of':timezone.now().isoformat(),
            'findings':findings,'automatic_escalation_authorized':False,'scope_changed':False})
    event(actor,case,'agent.actions_investigated',run=run.pk,actions=len(items))
    return run
