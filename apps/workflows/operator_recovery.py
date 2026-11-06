"""Scoped operator diagnostics and source-service recovery; no authority from source text."""
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.models import Grant
from apps.identity.services import require
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.operator_validators import OPERATOR,PROTECTION
from adapters.forecast import KEY
from .operator_inventory import jobs,recover_source,PRIVATE_FAMILIES
from .operator_models import OperatorInventory

def readable(a,c,source=False):
    if not get_user_model().objects.filter(pk=a.pk,is_active=True).exists():raise PermissionDenied('Active scoped operator required')
    require(a,c,'case.read');require(a,c,'ops.read')
    if source:require(a,c,'ops.proof.read')
def locked(a,case_id,action,expected=None):
    from .operator_inventory import lock_scope
    lock_scope(case_id)
    c=lock_case(a,case_id,action,expected);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'));readable(a,c);return c
def config(c,key):
    p=active_component(key,c);return p,reference_values(p)[0]
def authority(a,c,purpose):
    readable(a,c);require(a,c,'ops.'+purpose);p,v=config(c,OPERATOR)
    rows=[r for r in v['operators'] if r['user_id']==a.pk and purpose in r['purposes']]
    if len(rows)!=1:raise PermissionDenied('Exact configured operator purpose required')
    return {'operator_policy':p.pk,'role':rows[0]['role'],'role_authority':decision_authority(a,c,rows[0]['role'])}
@transaction.atomic
def snapshot(a,case_id,operation_key,expected=None):
    c=locked(a,case_id,'ops.snapshot',expected);validate(KEY,operation_key);rows,omitted,grants=jobs(a,c)
    from .private_readiness_operations import private_job
    private_inventory=any(j['family']=='protection' and private_job(c,j['id']) for j in rows)
    manifest={'jobs':rows,'omitted_families':omitted,'source_grants':grants,'evidence_bodies_read':False,'errors_or_intents_exported':False};old=OperatorInventory.objects.filter(case=c,operation_key=operation_key).first()
    if old:
        if old.actor_id!=a.pk:raise ValidationError('Inventory intent belongs to another principal')
        from .operator_inventory import readable_manifest
        readable_manifest(a,c,dict(old.manifest,case_id=str(old.case_id)))
        return old
    r=OperatorInventory.objects.create(case=c,operation_key=operation_key,manifest=manifest,sha256=digest(manifest),actor=a);event(a,c,'agent.data.private_inventory_observed' if private_inventory or any(j['family'] in PRIVATE_FAMILIES for j in rows) else 'ops.inventory_observed',inventory=r.pk);bump(c);return r
@transaction.atomic
def recover(a,case_id,family,job_id,operation,reason,expected=None):
    c=locked(a,case_id,'ops.recover',expected);auth=authority(a,c,'recover');p,rules=config(c,OPERATOR)
    if not isinstance(reason,str) or not 1<=len(reason.strip())<=400:raise ValidationError('Bounded recovery reason required')
    if not any(r['family']==family and operation in r['actions'] for r in rules['routes']):raise PermissionDenied('Recovery route/action is not configured')
    from .private_readiness_operations import private_job
    private_recovery=family=='protection' and private_job(c,job_id)
    result=recover_source(a,c,family,job_id,operation,reason)
    event(a,c,'agent.data.private_operator_recovery' if private_recovery or family in PRIVATE_FAMILIES else 'ops.source_recovery',family=family,job=job_id,operation=operation,authority=auth,reason=reason);return result

def operate_handoff(a,c,job_id,operation,reason):
    from .models import Outbox
    from adapters.finance import InternalFinanceAdapter
    require(a,c,'workflow.operate');j=Outbox.objects.select_for_update().filter(case=c,pk=job_id).first()
    if not j or operation not in ['cancel','retry'] or j.status not in ['pending','held']:raise ValidationError('Only pending/held known handoffs can be changed; worker reconciles uncertain or leased effects')
    if InternalFinanceAdapter().lookup(j.operation_key,j.payload):raise ValidationError('Actual handoff receipt exists; source worker must reconcile it')
    if operation=='retry':
        if j.status!='held':raise ValidationError('Only held work needs retry')
        require(a,c,'milestone.complete');
        if not get_user_model().objects.filter(pk=j.actor_id,is_active=True).exists():raise PermissionDenied('Original source actor is inactive')
        require(j.actor,c,'milestone.complete');j.status='pending';j.attempts=0
    else:j.status='cancelled'
    j.error='Scoped operator '+operation;j.save(update_fields=['status','attempts','error']);event(a,c,'handoff.operator_'+operation,job=j.pk,reason=reason);bump(c);return j
