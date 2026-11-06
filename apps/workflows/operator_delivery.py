from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.documents.contracts import digest
from apps.policy.operator_validators import PROTECTION
from adapters.operator_protection import NativeMetadataProtectionAdapter,storage_identity,target_identity,file_receipt
from .operator_recovery import locked,readable,authority,config
from .operator_inventory import bundle,readable_manifest,lock_scope
from .operator_models import RecoveryJob,RecoveryArtifact
from .protection import plan_for,current_plan
from . import private_readiness_operations as private
from apps.finance.acceptance_evaluation import evaluated

@evaluated
def intent(a,p,kind,input_id):
    private.plan_access(a,p);current_plan(p);auth=authority(a,p.case,kind);pol,rules=config(p.case,PROTECTION)
    if kind not in ['export','backup','restore']:raise ValidationError('Implemented metadata effect required')
    if p.payload['scope']!='portable_case_metadata_v1' or p.payload['source_ref']!='case:'+str(p.case_id):raise ValidationError('Native metadata projection requires exact case source reference')
    private.rules(p,rules)
    source=None
    if kind=='export':
        if input_id:raise ValidationError('Export reads scoped metadata; no arbitrary input artifact')
        manifest=bundle(a,p.case,rules['max_records'],private.ids(p),private.protection.ids(p))
    else:
        source=RecoveryArtifact.objects.select_related('job__plan').filter(pk=input_id,job__plan=p,job__kind='export' if kind=='backup' else 'backup').first()
        if not source:raise ValidationError('Exact plan export/backup artifact required')
        manifest=source.manifest;readable_manifest(a,p.case,manifest)
        if kind=='restore':
            if rules['restore_adapter']!='isolated_postgres_metadata_v1' or p.payload['target_ref']!=rules['restore_target']:raise ValidationError('Native isolated metadata target/adapter not configured for this plan')
            if not file_receipt(source.job):raise ValidationError('Sealed backup bytes unavailable')
    if private.has_private(p):private.current(a,p,manifest)
    target=target_identity() if kind=='restore' else None
    return {**({'accepted_protection_policy':private.protection.rules(p)} if private.protection.ids(p) else {}),'plan_sha256':p.sha256,'authority':auth,'protection_policy':pol.pk,'manifest':manifest,'input_artifact':source.pk if source else None,'storage_identity':storage_identity(),'target_identity':target,'lease_seconds':rules['lease_seconds'],'max_attempts':rules['max_attempts']}

@transaction.atomic
def reserve(a,case_id,plan_id,kind,input_id=None,expected=None):
    c=locked(a,case_id,'ops.'+kind,expected);p=plan_for(c,plan_id);value=intent(a,p,kind,input_id);old=RecoveryJob.objects.filter(plan=p,kind=kind).order_by('-generation').first()
    if old:
        if old.intent==value and old.actor_id==a.pk and old.status not in ['cancelled','replaced']:return old
        raise ValidationError('Existing effect intent differs; reconcile or explicitly replace held work')
    j=RecoveryJob.objects.create(plan=p,kind=kind,generation=1,operation_key=digest({'case':str(c.pk),'plan':p.pk,'kind':kind,'generation':1}),intent=value,actor=a);private.audit(a,c,p,'effect_reserved',job=j.pk,kind=kind);bump(c);return j

@transaction.atomic
def claim():
    now=timezone.now();j=RecoveryJob.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now)).order_by('pk').first()
    if not j:return None
    j.status='leased';j.fence+=1;j.attempts+=1;j.lease_until=now+timedelta(seconds=j.intent['lease_seconds']);j.save(update_fields=['status','fence','attempts','lease_until']);return j.pk,j.fence
def fence_check(j,fence):
    if j.status!='leased' or j.fence!=fence or j.lease_until<=timezone.now():raise ValidationError('Expired protection worker fence')
@transaction.atomic
def finish(pk,fence,status,receipt=None):
    initial=RecoveryJob.objects.select_related('plan').get(pk=pk);Case.objects.select_for_update().get(pk=initial.plan.case_id);j=RecoveryJob.objects.select_for_update().get(pk=pk);fence_check(j,fence)
    if status=='confirmed':
        old=RecoveryArtifact.objects.filter(job=j).first()
        if old and (old.manifest!=j.intent['manifest'] or old.sha256!=digest(j.intent['manifest'])):raise ValidationError('Prior artifact conflicts with receipt')
        if not old:RecoveryArtifact.objects.create(job=j,manifest=j.intent['manifest'],sha256=digest(j.intent['manifest']),receipt=receipt)
    j.status=status;j.error='' if status=='confirmed' else 'Outcome unknown; receipt lookup required' if status=='unknown' else 'Current source/authority/target controls require operator review';j.save(update_fields=['status','error']);private.audit(j.actor,j.plan.case,j.plan,'effect_'+status,job=j.pk)
@transaction.atomic
@evaluated
def dispatch(pk,fence,adapter):
    initial=RecoveryJob.objects.select_related('plan').get(pk=pk);lock_scope(initial.plan.case_id);c=Case.objects.select_for_update().get(pk=initial.plan.case_id);j=RecoveryJob.objects.select_for_update().select_related('plan__case','actor').get(pk=pk);fence_check(j,fence);list(Grant.objects.select_for_update().filter(case=c).order_by('pk'))
    value=intent(j.actor,j.plan,j.kind,j.intent['input_artifact'])
    if value!=j.intent:raise ValidationError('Reserved protection intent changed; explicit replacement required')
    from .private_file_readiness import selection as file_selection
    from .accepted_protection_readiness import selection as accepted_selection
    if j.kind=='restore' or file_selection(c,j.pk) or accepted_selection(c,j.pk):
        from .readiness import gate
        gate(c,'protection',j.pk)
    fence_check(j,fence) # Current proof/gate checks may outlast the reserved lease.
    return adapter.deliver(j)
def run_once(adapter=None):
    adapter=adapter or NativeMetadataProtectionAdapter();lease=claim()
    if not lease:return False
    pk,fence=lease;j=RecoveryJob.objects.select_related('plan__case').get(pk=pk)
    if type(adapter) is not NativeMetadataProtectionAdapter and not j.plan.case.synthetic:finish(pk,fence,'held');return True
    try:
        old=adapter.lookup(j) # Receipt-first recovery of actual committed metadata effects, even after revocation.
        if old:finish(pk,fence,'confirmed',old);return True
        if j.attempts>j.intent['max_attempts']:finish(pk,fence,'held');return True
        receipt=dispatch(pk,fence,adapter)
    except (TimeoutError,ConnectionError):finish(pk,fence,'unknown')
    except (ValidationError,PermissionDenied,ValueError,OSError):finish(pk,fence,'held')
    else:finish(pk,fence,'confirmed',receipt)
    return True

@transaction.atomic
def operate(a,case_id,job_id,operation,reason,expected=None):
    c=locked(a,case_id,'ops.operate',expected);auth=authority(a,c,'recover');j=RecoveryJob.objects.select_for_update().select_related('plan__case').filter(pk=job_id,plan__case=c).first()
    if j:private.plan_access(a,j.plan)
    if not j or operation not in ['cancel','retry','replace_intent'] or not isinstance(reason,str) or not 1<=len(reason.strip())<=400:raise ValidationError('Exact protection job/action and bounded reason required')
    if j.status in ['confirmed','cancelled','replaced'] or j.status=='leased' and j.lease_until>timezone.now():raise ValidationError('Proven, terminal or actively leased work cannot change')
    if NativeMetadataProtectionAdapter().lookup(j):raise ValidationError('Committed metadata effect exists; let worker reconcile')
    if j.status=='unknown':raise ValidationError('Uncertain effect requires receipt lookup before operator changes')
    if operation=='cancel':j.status='cancelled'
    else:
        if j.status!='held':raise ValidationError('Only held work requires retry/replacement')
        value=intent(a,j.plan,j.kind,j.intent['input_artifact'])
        if operation=='retry':
            if j.actor_id!=a.pk or value!=j.intent:raise ValidationError('Intent changed; use explicit replacement')
            j.status='pending'
            if not private.has_private(j.plan):j.attempts=0
        else:
            if private.has_private(j.plan) and value==j.intent and a.pk==j.actor_id:raise ValidationError('Private replacement requires changed context; original attempt budget cannot be reset')
            if RecoveryJob.objects.filter(plan=j.plan,kind=j.kind,generation__gt=j.generation).exists():raise ValidationError('Newer protection intent exists')
            generation=j.generation+1;RecoveryJob.objects.create(plan=j.plan,kind=j.kind,generation=generation,actor=a,operation_key=digest({'case':str(c.pk),'plan':j.plan_id,'kind':j.kind,'generation':generation}),intent=value);j.status='replaced'
    j.save(update_fields=['status','attempts']);private.audit(a,c,j.plan,'effect_operator_'+operation,job=j.pk,authority=auth,reason=reason);bump(c);return j
