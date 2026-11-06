"""Reviewed inert reconstitution plans. Archived business jobs never dispatch here."""
from datetime import timedelta
import psycopg
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.models import Case
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.reconstitution_validators import COMPONENT,DISPOSITIONS
from adapters import reconstitution as adapter, native_application_archive as n
from . import cold_recovery as cold
from .reconstitution_models import ReconstitutionPlan as Plan,ReconstitutionJob as Job,ReconstitutionDisposition as Disposition,ReconstitutionReview as Review


def access(actor,case,purpose='read',locked=True):
    cold.access(actor,case,purpose if purpose in ['read','capture','review','agent','configure'] else 'operate',locked=locked)
    require(actor,case,'reconstitution.archive')
    require(actor,case,'reconstitution.'+purpose)


def recovered(actor,recovery):
    result=cold.report(actor,recovery.plan.case_id,recovery.plan_id)
    if recovery.status!='confirmed' or not result['physical_receipt_current'] or not result['human_recovered_review_current']:
        raise ValidationError('Current physically verified, independently reviewed isolated recovery required')


@transaction.atomic
def capture(actor,case_id,recovery_id,reference,profile_ref):
    c=Case.objects.get(pk=case_id)
    access(actor,c,'capture')
    if not isinstance(reference,str) or not reference.strip() or len(reference)>100:
        raise ValidationError('Bounded stable reconstitution reference required')
    r=cold.Job.objects.select_related('plan__case').get(pk=recovery_id,plan__case=c)
    recovered(actor,r)
    inventory=adapter.inventory(r,profile_ref)
    profile,*_=adapter.runtime(r,profile_ref)
    payload={'profile_ref':profile_ref,'destination_ref':profile['destination_ref'],'inventory':inventory}
    old=Plan.objects.filter(case=c,reference=reference).order_by('-version').first()
    if old and old.payload==payload and old.recovery_id==r.pk:return old
    return Plan.objects.create(case=c,recovery=r,reference=reference,version=old.version+1 if old else 1,payload=payload,sha256=n.digest(payload),actor=actor)


def rules(p):
    cfg=active_component(COMPONENT,p.case)
    v=reference_values(cfg)[0]
    if v['profile_ref']!=p.payload['profile_ref'] or v['destination_ref']!=p.payload['destination_ref']:
        raise ValidationError('Exact current reconstitution profile and destination criteria required')
    if Plan.objects.filter(case=p.case,reference=p.reference,version__gt=p.version).exists():
        raise ValidationError('Use the current explicit reconstitution successor')
    return cfg,v


def principal(actor,p,purpose,v):
    access(actor,p.case,purpose)
    prefix='reviewer' if purpose=='review' else 'operator'
    if actor.pk!=v[prefix+'_id']:
        raise PermissionDenied('Exact current configured reconstitution purpose principal required')
    decision_authority(actor,p.case,v[prefix+'_role'])
    if purpose=='review' and (actor.pk==p.actor_id or Job.objects.filter(plan=p,actor=actor).exists()):
        raise PermissionDenied('Independent reviewer cannot prepare this plan or its jobs')


def pin(p,actor):
    cfg,v=rules(p)
    recovered(actor,p.recovery)
    actual=adapter.inventory(p.recovery,p.payload['profile_ref'],v['max_records'])
    if actual!=p.payload['inventory']:
        raise ValidationError('Physical inventory/profile changed; capture a successor')
    return {'plan_sha256':p.sha256,'runtime_sha256':actual['runtime_sha256'],'policy':cfg.pk,
            'role_policy':active_component('D05.role_principal_assignments',p.case).pk}


def effect(p,key):
    result=next((r for r in p.payload['inventory']['effects'] if r['effect_key']==key),None)
    if not result:raise ValidationError('Exact captured effect required')
    return result


def current_probe(p,job,row,v):
    if job.plan_id!=p.pk or job.kind!='receipt' or job.effect_key!=row['effect_key'] or job.status!='confirmed':
        raise ValidationError('Confirmed same-plan exact-effect receipt probe required')
    receipt=adapter.lookup(p.recovery,job.intent)
    if receipt!=job.receipt or receipt['payload']!=adapter.gateway(p.recovery,p.payload['profile_ref'],row,v):
        raise ValidationError('Current authenticated receipt evidence differs or expired; reserve a fresh probe')
    return receipt['payload']


def latest_dispositions(p):
    rows={}
    for d in Disposition.objects.filter(plan=p).select_related('actor','probe').order_by('pk'):rows[d.effect_key]=d
    return rows


@transaction.atomic
def dispose(actor,case_id,plan_id,effect_key,verdict,rationale,operation_key,probe_id=None):
    p=Plan.objects.select_related('case','recovery__plan__case').get(pk=plan_id,case_id=case_id)
    _,v=rules(p);principal(actor,p,'review',v)
    if verdict not in v['allowed_dispositions'] or verdict not in DISPOSITIONS or not rationale.strip() or len(rationale)>1000 or not operation_key or len(operation_key)>100:
        raise ValidationError('Configured human disposition, bounded rationale and exact key required')
    row=effect(p,effect_key);evidence=pin(p,actor);probe=None
    if verdict=='receipt_confirmed':
        probe=Job.objects.filter(pk=probe_id,plan=p).first()
        if probe is None:
            raise ValidationError('Select a confirmed same-plan exact-effect receipt probe')
        observation=current_probe(p,probe,row,v)
        if observation['outcome']!='present':
            raise ValidationError('Absence is unknown, never proof of no effect or authority to retry')
        evidence['probe_receipt_sha256']=n.digest(probe.receipt)
    elif probe_id is not None:
        raise ValidationError('Only receipt-confirmed dispositions bind a receipt probe')
    old=Disposition.objects.filter(plan=p,operation_key=operation_key).first()
    values=dict(effect_key=effect_key,verdict=verdict,rationale=rationale,probe=probe,pin=evidence,actor=actor)
    if old:
        if any(getattr(old,k)!=x for k,x in values.items()):raise ValidationError('Disposition key binds another immutable decision')
        return old
    previous=Disposition.objects.filter(plan=p,effect_key=effect_key).order_by('-version').first()
    return Disposition.objects.create(plan=p,operation_key=operation_key,version=previous.version+1 if previous else 1,**values)


def manifest(p,actor,base=None):
    base=base or pin(p,actor)
    _,v=rules(p);latest=latest_dispositions(p);rows=[]
    for row in p.payload['inventory']['effects']:
        d=latest.get(row['effect_key']);state='unresolved';evidence_sha=None;observation_sha=None
        if d:
            principal(d.actor,p,'review',v)
            if any(d.pin.get(k)!=x for k,x in base.items()):raise ValidationError('Disposition authority/policy changed')
            state=d.verdict
            if d.verdict=='receipt_confirmed':
                proof=current_probe(p,d.probe,row,v)
                if proof['outcome']!='present' or d.pin.get('probe_receipt_sha256')!=n.digest(d.probe.receipt):raise ValidationError('Exact current receipt-confirmed evidence required')
                evidence_sha=proof['receipt_sha256']
                observation_sha=n.digest(d.probe.receipt)
        rows.append({'effect_key':row['effect_key'],'family':row['family'],'disposition_id':d.pk if d else None,'verdict':state,'receipt_sha256':evidence_sha,'observation_sha256':observation_sha})
    return {'format':adapter.FORMAT,'plan_sha256':p.sha256,'inventory_sha256':n.digest(p.payload['inventory']),
            'destination_ref':p.payload['destination_ref'],'effects':rows,'unresolved_count':sum(r['verdict']=='unresolved' for r in rows),
            'replacement_required_count':sum(r['verdict']=='replacement_required' for r in rows),
            'activation_enabled':False,'business_jobs_reenacted':False,'debt_waived':False,'archived_authority_accepted':False}


@transaction.atomic
def review(actor,case_id,plan_id,verdict,rationale,operation_key):
    p=Plan.objects.select_related('case','recovery__plan__case').get(pk=plan_id,case_id=case_id)
    _,v=rules(p);principal(actor,p,'review',v)
    if verdict not in ['approve','hold'] or not rationale.strip() or len(rationale)>1000 or not operation_key or len(operation_key)>100:
        raise ValidationError('Explicit bounded independent review required')
    evidence=pin(p,actor);packet=manifest(p,actor,evidence)
    if verdict=='approve' and any(r['disposition_id'] is None for r in packet['effects']):
        raise ValidationError('Every effect needs a human disposition; unresolved/retained effects stay quarantined')
    evidence['manifest_sha256']=n.digest(packet)
    values=dict(verdict=verdict,rationale=rationale,pin=evidence,actor=actor)
    old=Review.objects.filter(plan=p,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=x for k,x in values.items()):raise ValidationError('Review key binds another immutable decision')
        return old
    return Review.objects.create(plan=p,operation_key=operation_key,**values)


def approved(p,actor,evidence,packet):
    r=Review.objects.filter(plan=p).select_related('actor').order_by('-pk').first();_,v=rules(p)
    if not r or r.verdict!='approve' or r.pin!={**evidence,'manifest_sha256':n.digest(packet)} or timezone.now()>=r.created_at+timedelta(seconds=v['review_valid_seconds']):
        raise ValidationError('Current independent reviewed-plan authorization required')
    principal(r.actor,p,'review',v)
    return r.pk


@transaction.atomic
def reserve(actor,case_id,plan_id,kind,operation_key,effect_key='all'):
    p=Plan.objects.select_related('case','recovery__plan__case').get(pk=plan_id,case_id=case_id)
    _,v=rules(p);principal(actor,p,'operate',v)
    if kind not in ['receipt','publish'] or not operation_key or len(operation_key)>100:
        raise ValidationError('Typed receipt/plan publication and bounded original intent key required')
    evidence=pin(p,actor);row=None;packet=None;authorization=None
    if kind=='receipt':row=effect(p,effect_key)
    else:
        if effect_key!='all':raise ValidationError('Publish the exact complete reviewed plan')
        packet=manifest(p,actor,evidence);authorization=approved(p,actor,evidence,packet)
    op=n.digest({'plan':p.pk,'kind':kind,'key':operation_key})
    intent={'format':adapter.FORMAT,'operation_key':op,'plan':p.pk,'plan_sha256':p.sha256,'kind':kind,'profile_ref':p.payload['profile_ref'],
            'rules':v,'pin':evidence,'effect':row,'manifest':packet,'authorization':authorization}
    old=Job.objects.filter(operation_key=op).first()
    if old:
        if old.intent!=intent or old.actor_id!=actor.pk:raise ValidationError('Job key binds another immutable reconstitution intent')
        return old
    return Job.objects.create(plan=p,kind=kind,effect_key=effect_key,operation_key=op,intent=intent,actor=actor)


@transaction.atomic
def retry(actor,case_id,job_id):
    j=Job.objects.select_for_update().select_related('plan__case').get(pk=job_id,plan__case_id=case_id)
    _,v=rules(j.plan);principal(actor,j.plan,'operate',v)
    if j.status not in ['held','unknown']:raise ValidationError('Only original held/uncertain work can be reconciled')
    j.status='pending';j.save(update_fields=['status']);return j


def finish(j,receipt):
    j.status,j.receipt,j.error='confirmed',receipt,''
    j.save(update_fields=['status','receipt','error'])


def run_once():
    cold.control()
    with transaction.atomic():
        j=Job.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lt=timezone.now())).order_by('pk').first()
        if not j:return False
        j.status,j.fence,j.attempts='leased',j.fence+1,j.attempts+1
        j.lease_until=timezone.now()+timedelta(seconds=j.intent['rules']['lease_seconds'])
        j.save(update_fields=['status','fence','attempts','lease_until']);pk,fence=j.pk,j.fence
    with transaction.atomic():
        j=Job.objects.select_for_update().select_related('plan__case','plan__recovery__plan__case','actor').get(pk=pk)
        if j.fence!=fence or j.status!='leased':return True
        try:
            receipt=adapter.lookup(j.plan.recovery,j.intent)
            if receipt is None:
                _,v=rules(j.plan);principal(j.actor,j.plan,'operate',v)
                evidence=pin(j.plan,j.actor)
                if evidence!=j.intent['pin'] or v!=j.intent['rules'] or j.attempts>v['max_attempts']:raise ValidationError('Current controls/original attempt budget differ')
                if j.kind=='publish':
                    packet=manifest(j.plan,j.actor,evidence)
                    if packet!=j.intent['manifest'] or approved(j.plan,j.actor,evidence,packet)!=j.intent['authorization']:raise ValidationError('Current complete reviewed packet differs')
                receipt=adapter.deliver(j.plan.recovery,j.intent)
            finish(j,receipt)
        except (ValidationError,PermissionDenied,OSError,psycopg.Error):
            j.status,j.error='held','reconstitution_controls_held';j.save(update_fields=['status','error'])
    return True


@transaction.atomic
def report(actor,case_id,plan_id):
    p=Plan.objects.select_related('case','recovery__plan__case').get(pk=plan_id,case_id=case_id);access(actor,p.case)
    result={'plan':p.pk,'activation_enabled':False,'business_jobs_reenacted':False,'review_current':False,'physical_inventory_current':False,
            'policy_status':resolve(COMPONENT,p.case).status,'effects':p.payload['inventory']['effects'],'holds':[],'jobs':[]}
    try:
        evidence=pin(p,actor);result['physical_inventory_current']=True
        packet=manifest(p,actor,evidence);result['manifest']=packet
        try:approved(p,actor,evidence,packet);result['review_current']=True
        except (ValidationError,PermissionDenied):result['holds'].append('Current independent complete-packet review required')
    except (ValidationError,PermissionDenied,OSError,psycopg.Error):result['holds'].append('Current criteria, fresh recovery review and complete physical inventory required')
    for j in Job.objects.filter(plan=p).order_by('pk'):
        try:physical=j.status=='confirmed' and adapter.lookup(p.recovery,j.intent)==j.receipt
        except (ValidationError,OSError):physical=False
        result['jobs'].append({'id':j.pk,'kind':j.kind,'status':j.status,'attempts':j.attempts,'artifact_current':physical})
    return result
