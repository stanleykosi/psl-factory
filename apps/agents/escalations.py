from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import F
from apps.core.services import lock_case,event
from apps.identity.services import require
from apps.pmo.models import EscalationProfile
from apps.pmo.escalations import timing
from .models import AgentRun

@transaction.atomic
def investigate_escalations(actor,case_id,expected,profile_ids=None):
    case=lock_case(actor,case_id,'agent.issues',expected);require(actor,case,'issue.read')
    profiles=EscalationProfile.objects.filter(state__issue__case=case,state__issue__current_id=F('state_id')).select_related('state__issue')
    if profile_ids is not None:
        from apps.pmo.escalations import current_profile
        if not isinstance(profile_ids,list) or not 1<=len(profile_ids)<=100 or len(set(profile_ids))!=len(profile_ids) or any(type(pk) is not int for pk in profile_ids):raise ValidationError('Select 1 to 100 exact distinct current profiles')
        profiles=[current_profile(case,pk) for pk in profile_ids]
    else:profiles=list(profiles.order_by('state__issue_id','-pk').distinct('state__issue_id')[:101])
    if not profiles or len(profiles)>100:raise ValidationError('Escalation investigation requires 1 to 100 scoped current profiles')
    findings=[{'profile_id':p.pk,'state_id':p.state_id,'evidence_id':p.evidence_id,'timing':timing(p)} for p in profiles]
    run=AgentRun.objects.create(case=case,actor=actor,evidence=profiles[0].evidence,provider='deterministic-escalation-investigation-v1',process_id='P44',
        result={'capability':'A03/A04/A08 escalation evidence and timing investigation','findings':findings,
            'human_client_decision_required':True,'communications_dispatched':False,'approval_granted':False})
    event(actor,case,'agent.escalations_investigated',run=run.pk)
    return run
