"""ACT10 resolves trusted native facts; it cannot grant a Finance business role."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.policy.services import resolve,reference_values
from apps.policy.factory_routing_validators import COMPONENT,OWNERS,principal

def binding(work):
    result=resolve(COMPONENT,work.case)
    config=result.configuration
    value=reference_values(config)[0] if result.status=='ACTIVE' else None
    return {'schema':'factory-finance-responsibility-binding/v1','status':result.status,
        'configuration':config.pk if config is not None else None,'value':value}

def evaluate(work):
    from . import factory
    from apps.finance import invoices
    from django.contrib.auth import get_user_model
    bound=binding(work);value=bound['value'];missing=[]
    if value is None:missing=['responsibility_configuration']
    else:missing=[name for name in OWNERS if principal(work.case,value[name]) is None]
    from apps.policy.factory_routing_validators import METHOD_V2,METHOD_V3
    if value and value['method'] in [METHOD_V2,METHOD_V3] and value['authority_mode'] is None:missing.append('finance_authority_mode')
    if value and value['method']==METHOD_V3 and value['availability_mode'] is None:missing.append('reviewer_availability_mode')
    users=[];authorities=[];findings=[]
    if not missing and work.invoice_id:
        for user in get_user_model().objects.filter(is_active=True,grant__case=work.case,grant__active=True,grant__action='finance.invoice.review').distinct().order_by('pk'):
            try:
                factory.access(user,work.case)
                try:authority=invoices.review_authority(user,work.case,'invoice','Finance','approve',work.invoice.actor_id,invoice=work.invoice)
                except (ValidationError,PermissionDenied) as direct_error:
                    if value.get('authority_mode')!='direct_or_configured_delegate':raise
                    try:authority=invoices.review_authority(user,work.case,'invoice','Finance','approve',work.invoice.actor_id,delegated=True,invoice=work.invoice)
                    except (ValidationError,PermissionDenied):
                        if 'availability_needed:' in str(direct_error) or 'reviewer_unavailable:' in str(direct_error):raise direct_error
                        raise
            except (ValidationError,PermissionDenied) as exc:
                if value['method'] in [METHOD_V2,METHOD_V3]:
                    message=str(exc).casefold()
                    code=('reviewer_unavailable' if 'reviewer_unavailable:' in message else
                        'availability_needs_configuration' if 'availability_needed:' in message else
                        'scope_needs_configuration' if 'scope needs configured' in message else
                        'conflicting_delegations' if 'conflicting current invoice delegations' in message else
                        'independent_reviewer_required' if 'different reviewer' in message else 'no_current_review_authority')
                    summary={'reviewer_unavailable':'A configured reviewer is unavailable during the decision window.',
                        'availability_needs_configuration':'A current reviewer availability window still needs an owner decision.',
                        'scope_needs_configuration':'A delegated review rule still needs its permitted decisions, currency or amount limit.',
                        'conflicting_delegations':'Several current delegated rules match; the policy owner must resolve the conflict.',
                        'independent_reviewer_required':'The invoice requires a reviewer who did not prepare it.',
                        'no_current_review_authority':'A current role, qualified delegation or review permission is unavailable.'}[code]
                    findings.append({'principal_id':user.pk,'code':code,'summary':summary})
                continue
            users.append(user.pk)
            authorities.append(authority)
    if not missing and not users:missing=['eligible_finance_reviewer']
    resolver=principal(work.case,value['governance_resolver_id'],True) if value else None
    result={'binding':bound,'method':value['method'] if value else 'native_finance_single_review/v1','role':'Finance',
        'missing':missing,'eligible_principals':users,'governance_resolver_id':resolver.pk if resolver else None,
        'invoice':work.invoice_id,'approval_granted':False,'authority':authorities}
    if value and value['method'] in [METHOD_V2,METHOD_V3]:result['reviewer_findings']=findings
    return result


def availability_authority(invoice,actor):
    """Read trusted native scope; never infer presence from a role or a calendar gap."""
    from .models import FactoryWork
    from apps.policy.factory_routing_validators import METHOD_V3
    from apps.policy.reviewer_availability_validators import COMPONENT as AVAILABILITY
    from apps.policy.role_assignments import instant
    from apps.finance.billing import digest
    work=FactoryWork.objects.filter(invoice=invoice,definition='pmo-finance/v1').select_related('case').first()
    if work is None:return None
    bound=binding(work);value=bound['value']
    if not value or value['method']!=METHOD_V3:return None
    mode=value['availability_mode']
    if mode is None:raise ValidationError('availability_needed: choose whether this decision requires current availability')
    if mode=='not_applied':return {'mode':mode,'responsibility':bound['configuration']}
    result=resolve(AVAILABILITY,work.case)
    if result.status!='ACTIVE':raise ValidationError('availability_needed: current reviewer availability source is not active')
    now=timezone.now();records=reference_values(result.configuration)[0]['records']
    matches=[r for r in records if r['principal_id']==actor.pk and instant(r['valid_from'])<=now<instant(r['valid_until'])]
    if len(matches)!=1 or matches[0]['status'] is None:raise ValidationError('availability_needed: one explicit current availability window is required')
    record=matches[0]
    if record['status']=='unavailable':raise PermissionDenied('reviewer_unavailable: current owner-evidenced absence prevents this decision')
    return {'mode':mode,'configuration':result.configuration.pk,'record_sha256':digest(record),'valid_until':record['valid_until']}


def relevant_authority(value):
    # Native Finance deliberately ignores unrelated namespaces in this matrix.
    return {k:v for k,v in value.items() if k!='D05.decision_action_matrix'}


def review_binding(evaluated):
    """Compare recorded facts without mutating historical task context or policy."""
    if not isinstance(evaluated,dict) or 'authority' not in evaluated:return None
    if not isinstance(evaluated['authority'],list) or any(not isinstance(value,dict) for value in evaluated['authority']):return None
    if not isinstance(evaluated.get('eligible_principals'),list) or len(evaluated['authority'])!=len(evaluated['eligible_principals']):return None
    return {k:evaluated.get(k) for k in ['binding','method','role','invoice','eligible_principals']} | {
        'authority':[relevant_authority(value) for value in evaluated['authority']]}


def task_authority_current(work,task,evaluated=None):
    from apps.finance.billing import digest
    recorded=review_binding(task.context.get('routing_at_creation'))
    return recorded is not None and digest(recorded)==digest(review_binding(evaluated if evaluated is not None else evaluate(work)))


def native_review_current(work,review):
    """Old native decisions stay history; only a currently valid one satisfies a wait."""
    from apps.finance import invoices
    from apps.identity.services import require
    try:
        if review.publication_packet!=invoices.review_packet(work.invoice):return False
        if review.verdict=='approve':invoices.reviewed(work.invoice)
        else:
            invoices.current(work.invoice);require(review.actor,work.case,'finance.invoice.review')
            require_ready(work,review.actor)
            current=invoices.review_authority(review.actor,work.case,'invoice',review.role,review.verdict,work.invoice.actor_id,
                delegated='D05.delegation_rules' in review.authority,invoice=work.invoice)
            if relevant_authority(current)!=relevant_authority(review.authority):return False
    except (ValidationError,PermissionDenied):return False
    return True

def require_ready(work,actor=None):
    evaluated=evaluate(work)
    if evaluated['missing']:raise ValidationError('owner_needed: resolve current responsibility nominations and native Finance review eligibility')
    if actor is not None and actor.pk not in evaluated['eligible_principals']:raise PermissionDenied('Current native Finance reviewer eligibility required')
    return evaluated

def delegated_for(work,actor,evaluated=None):
    evaluated=evaluated if evaluated is not None else require_ready(work,actor)
    if actor.pk not in evaluated['eligible_principals']:raise PermissionDenied('Current native Finance reviewer eligibility required')
    authority=evaluated['authority'][evaluated['eligible_principals'].index(actor.pk)]
    return 'D05.delegation_rules' in authority


def review_capabilities(work,actor):
    from apps.finance import invoices
    delegated=delegated_for(work,actor);allowed=[]
    for verdict in ['approve','return','reject']:
        try:invoices.review_authority(actor,work.case,'invoice','Finance',verdict,work.invoice.actor_id,delegated=delegated,invoice=work.invoice)
        except (ValidationError,PermissionDenied):continue
        allowed.append(verdict)
    return {'delegated':delegated,'verdicts':allowed}


def for_invoice(invoice,actor=None,delegated=None):
    from .models import FactoryWork
    work=FactoryWork.objects.filter(invoice=invoice,definition='pmo-finance/v1').select_related('case','invoice').first()
    if work is None:return None
    evaluated=require_ready(work,actor)
    if delegated is not None and (type(delegated) is not bool or actor is None or delegated_for(work,actor,evaluated)!=delegated):
        raise PermissionDenied('Configured factory Finance authority mode changed')
    return evaluated

@transaction.atomic
def recheck(actor,task_id,expected,reason):
    from . import factory
    from .models import HumanTask,FactoryWork,TaskEvent
    initial=HumanTask.objects.get(pk=task_id)
    if initial.kind!='factory_governance':raise ValidationError('Exact responsibility review task required')
    work=FactoryWork.objects.select_for_update(of=('self',)).select_related('case','invoice').get(pk=initial.context['work'],case=initial.case)
    task=HumanTask.objects.select_for_update().get(pk=task_id)
    factory.access(actor,work.case);factory.profile(work,recovery=True)
    from apps.core.services import lock_case
    lock_case(actor,work.case_id,'policy.configure')
    if work.cancel_requested or work.status in ['verified','cancelled','followup_needed']:raise ValidationError('Stopped work requires its native follow-up')
    if work.lease_until and work.lease_until>timezone.now():raise ValidationError('CONFLICT: current worker owns this work')
    if task.status!='open' or task.claimed_by_id!=actor.pk or task.revision!=expected:raise ValidationError('STALE_VERSION: current claimed responsibility task required')
    evaluated=evaluate(work)
    if evaluated['governance_resolver_id']!=actor.pk:raise PermissionDenied('Current configured governance resolver required')
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValidationError('Explain the responsibility recheck in at most2000 characters')
    require_ready(work)
    TaskEvent.objects.create(task=task,actor=actor,action='factory.owners_rechecked',data={'routing':evaluated,'reason':reason,'approval_granted':False})
    task.status='completed';task.revision+=1;task.save(update_fields=['status','revision'])
    work.status='ready';work.finding='';work.revision+=1;work.save()
    return task
