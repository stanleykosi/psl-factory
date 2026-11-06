"""Reviewed execution recovery; never changes the starter or grants domain permissions."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case,event
from apps.core.models import Evidence
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.factory_recovery_validators import COMPONENT,METHOD
from apps.policy.role_assignments import instant
from .factory_definitions import definition
from .models import FactoryWork,FactoryExecutionBinding

def origin_access(actor,configuration):
    from apps.policy.models import ScopeApplication
    from apps.policy.scopes import authorized
    inherited=ScopeApplication.objects.select_related('source__configuration__case').filter(configuration=configuration).first()
    if inherited:authorized(actor,inherited.source.configuration.case,'policy.read')

def qualified_rule(work):
    config=active_component(COMPONENT,work.case)
    matches=[r for r in reference_values(config)[0]['rules'] if r['definition']==work.definition]
    if len(matches)!=1:raise ValidationError('configuration_needed: one recovery rule for this work type is required')
    rule=matches[0]
    if any(rule[k] is None for k in ['method','principal_id','reviewer_id','review_role','independent_of_worker','valid_from','valid_until']):
        raise ValidationError('configuration_needed: recovery principal, reviewer, authority and validity remain undecided')
    if rule['method']!=METHOD or not instant(rule['valid_from'])<=timezone.now()<instant(rule['valid_until']):
        raise ValidationError('owner_needed: current reviewed execution recovery authority is required')
    people=[]
    for key,action in [('principal_id','factory.execute'),('reviewer_id','factory.manage')]:
        user=get_user_model().objects.filter(pk=rule[key],is_active=True).first()
        if not user:raise PermissionDenied('Current active recovery principals required')
        for name in ['case.read','factory.read',definition(work.definition)['read'],action]:require(user,work.case,name)
        origin_access(user,config);people.append(user)
    principal,reviewer=people
    if rule['independent_of_worker'] and principal.pk==reviewer.pk:raise PermissionDenied('Independent current recovery reviewer required')
    decision_authority(reviewer,work.case,rule['review_role'])
    return config,rule,principal,reviewer

def execution_actor(work):
    if work.execution_binding_id is None:return work.actor
    config,rule,principal,_=qualified_rule(work)
    bound=work.execution_binding
    if bound.work_id!=work.pk or bound.configuration_id!=config.pk or bound.rule!=rule or bound.principal_id!=principal.pk:
        raise ValidationError('owner_needed: execution recovery authority changed; reviewed replacement required')
    return principal

def available_actor(work):
    """Read-only availability; an unavailable owner must not suppress human decisions."""
    try:
        actor=execution_actor(work)
        from .factory import access
        access(actor,work.case,'factory.execute',work.definition)
        return actor
    except (ValidationError,PermissionDenied):return None

def require_control(actor,work):
    from .factory import access
    access(actor,work.case,'factory.execute',work.definition)
    owner=available_actor(work)
    if owner is None or actor.pk!=owner.pk:require(actor,work.case,'factory.manage')

def can_control(actor,work):
    try:require_control(actor,work);return True
    except (ValidationError,PermissionDenied):return False

@transaction.atomic
def bind(actor,work_id,expected,evidence_id,reason):
    if any(type(value) is not int or value<1 for value in [work_id,expected,evidence_id]):
        raise ValidationError('Exact work, revision and authority evidence identities required')
    work=FactoryWork.objects.select_for_update(of=('self',)).select_related('case','execution_binding').get(pk=work_id)
    from .factory import access
    access(actor,work.case,'factory.manage',work.definition);work.case=lock_case(actor,work.case_id,'factory.manage')
    if work.revision!=expected:raise ValidationError('STALE_VERSION: work changed before execution recovery')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Stopped or completed work needs its native follow-up')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker still owns this work')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the reviewed execution recovery')
    proof=Evidence.objects.filter(pk=evidence_id,case=work.case,kind='policy_decision').first()
    if not proof:raise ValidationError('Same-workspace recorded authority decision required')
    config,rule,principal,reviewer=qualified_rule(work)
    if actor.pk!=reviewer.pk:raise PermissionDenied('Only the currently configured recovery reviewer may authorise replacement')
    binding=FactoryExecutionBinding.objects.create(work=work,previous=work.execution_binding,
        sequence=(work.execution_binding.sequence+1 if work.execution_binding_id else 1),work_revision=work.revision+1,
        principal=principal,reviewer=actor,configuration=config,evidence=proof,rule=rule,reason=reason.strip())
    work.execution_binding=binding;work.fence+=1;work.revision+=1;work.lease_until=None
    # Unknown effects stay on their original jobs; this decision neither resends nor resets them.
    if work.status!='waiting_effect':work.status='ready'
    work.finding='';work.save()
    event(actor,work.case,'factory.execution_authority_recovered',work=work.pk,binding=binding.pk,
        original_starter=work.actor_id,principal=principal.pk,configuration=config.pk,budget_used=work.budget_used)
    return binding
