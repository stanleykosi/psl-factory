"""Finance-owned exact receipt evidence and inert reviewed companion publication."""
from datetime import timedelta
import psycopg
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.models import Case
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.native_finance_validators import COMPONENT
from apps.documents.contracts import validate,digest
from adapters.forecast import KEY
from adapters import native_finance as adapter
from . import reconstitution as d,domain_contracts as domains
from .native_finance_models import NativeFinanceMapping as Mapping,NativeFinanceObservation as Observation,NativeFinancePacket as Packet,NativeFinanceReview as Review,NativeFinancePublicationJob as Job

def access(actor,case,purpose='read',locked=True,family=None):
    d.access(actor,case,purpose,locked=locked)
    if family is None:
        try:require(actor,case,'finance.handoff.read')
        except PermissionDenied:require(actor,case,'finance.read')
    else:require(actor,case,'finance.read' if family=='invoice' else 'finance.handoff.read')
    require(actor,case,'reconstitution.native_finance.'+purpose)

def visible_mappings(actor,case):
    versions=[]
    for action,version in [('finance.handoff.read','psl.internal-finance-handoff/v1'),('finance.read','psl.internal-finance-invoice/v1')]:
        try:require(actor,case,action);versions.append(version)
        except PermissionDenied:pass
    return Mapping.objects.filter(plan__case=case,payload__contract_version__in=versions)

def get(actor,case_id,mapping_id,purpose='read'):
    m=Mapping.objects.select_related('plan__case','plan__recovery__plan__case').get(pk=mapping_id,plan__case_id=case_id)
    access(actor,m.plan.case,purpose,family='invoice' if 'variant' in m.payload else 'handoff');return m

def rules(m):
    cfg=active_component(COMPONENT,m.plan.case);v=reference_values(cfg)[0]
    if v['provider_ref']!=m.provider_ref or v['destination_ref']!=m.plan.payload['destination_ref'] or Mapping.objects.filter(plan=m.plan,reference=m.reference,version__gt=m.version).exists():
        raise ValidationError('Exact current Finance mapping/provider/destination criteria required')
    return cfg,v

def principal(actor,m,purpose,v):
    family='invoice' if 'variant' in m.payload else 'handoff'
    access(actor,m.plan.case,purpose,family=family)
    require(actor,m.plan.case,'reconstitution.domain.'+family+'.'+('review' if purpose=='review' else 'verify'))
    prefix='reviewer' if purpose=='review' else 'operator'
    if actor.pk!=v[prefix+'_id']:raise PermissionDenied('Exact current native Finance purpose principal required')
    decision_authority(actor,m.plan.case,v[prefix+'_role'])
    if purpose=='review' and (actor.pk==m.actor_id or Observation.objects.filter(mapping=m,actor=actor).exists() or Packet.objects.filter(mapping=m,actor=actor).exists() or Job.objects.filter(packet__mapping=m,actor=actor).exists()):
        raise PermissionDenied('Independent Finance source-owner review required')

def pin(actor,m):
    cfg,v=rules(m);physical=d.pin(m.plan,actor)
    metadata,_,_=adapter.original(m.plan,d.effect(m.plan,m.effect_key),v['max_payload_bytes'])
    if metadata!=m.payload:raise ValidationError('Original Finance mapping changed')
    binding,_=adapter.binding(m)
    evidence={'mapping_sha256':m.sha256,'policy':cfg.pk,'reconstitution':physical,'provider':binding}
    if 'variant' in m.payload:
        from apps.policy.invoice_receipt_validators import VARIANTS
        variants=active_component(VARIANTS,m.plan.case)
        if m.payload['variant'] not in reference_values(variants)[0]['variants']:raise ValidationError('Configure this exact invoice receipt variant')
        evidence['variant_policy']=variants.pk
    return evidence,v

@transaction.atomic
def capture(actor,case_id,plan_id,reference,effect_key,provider_ref,evidence_id,predecessor=None):
    p=d.Plan.objects.select_related('case','recovery__plan__case').get(pk=plan_id,case_id=case_id)
    effect=d.effect(p,effect_key);family=effect['family']
    access(actor,p.case,'capture',family=family);require(actor,p.case,'reconstitution.domain.'+family+'.verify')
    validate(KEY,reference);validate(KEY,provider_ref)
    evidence=p.case.evidence.filter(pk=evidence_id,kind='integration_contract').first()
    if evidence is None:raise ValidationError('Same-case Finance mapping/contract evidence required')
    d.pin(p,actor) # Current whole-archive scope and physical proof before private projection.
    payload,_,_=adapter.original(p,effect)
    old=Mapping.objects.filter(plan=p,reference=reference).order_by('-version').first()
    if old and old.payload==payload and old.provider_ref==provider_ref and old.evidence_id==evidence_id:return old
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit current Finance mapping predecessor required')
    return Mapping.objects.create(plan=p,reference=reference,version=old.version+1 if old else 1,provider_ref=provider_ref,effect_key=effect_key,payload=payload,sha256=digest(payload),evidence=evidence,actor=actor)

def reviewed(m,evidence,v,observation=None,packet=None):
    r=Review.objects.filter(mapping=m,observation=observation,packet=packet).select_related('actor').order_by('-pk').first()
    expected={**evidence,'observation_sha256':digest(observation.result) if observation else None,'packet_sha256':packet.sha256 if packet else None}
    if not r or r.verdict!='approve' or r.pin!=expected or timezone.now()>=r.created_at+timedelta(seconds=v['review_valid_seconds']):
        raise ValidationError('Current independent exact Finance review required')
    principal(r.actor,m,'review',v);return r

def current_observation(m,o,evidence,v):
    if o.mapping_id!=m.pk or o.pin!=evidence or timezone.now()>=o.created_at+timedelta(seconds=v['observation_valid_seconds']):
        raise ValidationError('Exact current bounded native Finance observation required')
    principal(o.actor,m,'operate',v)
    if adapter.verify(m,d.effect(m.plan,m.effect_key),v,evidence['provider'])!=o.result:
        raise ValidationError('Current native Finance receipt changed; collect and review successor evidence')

def destination(actor,m,o):
    r=o.contract
    if r.plan_id!=m.plan_id or r.kind!='destination':raise ValidationError('Same-plan exact destination observation required')
    domains.get(actor,m.plan.case_id,r.pk)
    evidence,v=domains.pin(actor,r);domains.reviewed(actor,r,evidence,v)
    if o.pin!=evidence:raise ValidationError('Destination contract/credential/policy changed')
    acceptance=domains.reviewed(actor,r,evidence,v,o)
    return {'observation':o.pk,'contract_sha256':r.sha256,'result_sha256':digest(o.result),'review':acceptance.pk,
        'prerequisites':o.result['prerequisites'],'classification':o.result['classification'],'physical_provisioning_verified':False}

def packet_payload(actor,m,o,dest,evidence,v):
    reviewed(m,evidence,v);current_observation(m,o,evidence,v);accepted=reviewed(m,evidence,v,o)
    return {'format':adapter.FORMAT,'scope':'single_invoice_companion' if 'variant' in m.payload else 'single_handoff_companion','plan_sha256':m.plan.sha256,'inventory_sha256':digest(m.plan.payload['inventory']),
        'mapping':m.pk,'mapping_sha256':m.sha256,'effect_key':m.effect_key,'source_payload_sha256':m.payload['payload_sha256'],
        'native_observation':o.pk,'native_result':o.result,'native_review':accepted.pk,'destination':destination(actor,m,dest),
        'activation_enabled':False,'business_jobs_reenacted':False,'debt_waived':False,'archived_authority_accepted':False}

@transaction.atomic
def capture_packet(actor,case_id,mapping_id,observation_id,destination_id,reference,predecessor=None):
    m=get(actor,case_id,mapping_id,'capture');_,v=rules(m);principal(actor,m,'capture',v);validate(KEY,reference)
    o=Observation.objects.filter(pk=observation_id,mapping=m).first()
    dest=domains.Observation.objects.select_related('contract__plan__case').filter(pk=destination_id,contract__plan=m.plan).first()
    if o is None or dest is None:raise ValidationError('Exact same-mapping observation and same-plan destination required')
    evidence,v=pin(actor,m);payload=packet_payload(actor,m,o,dest,evidence,v)
    old=Packet.objects.filter(mapping=m,reference=reference).order_by('-version').first()
    if old and old.payload==payload:return old
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit companion packet predecessor required')
    return Packet.objects.create(mapping=m,observation=o,destination=dest,reference=reference,version=old.version+1 if old else 1,payload=payload,sha256=digest(payload),actor=actor)

def packet_pin(actor,p,evidence,v):
    if Packet.objects.filter(mapping=p.mapping,reference=p.reference,version__gt=p.version).exists():raise ValidationError('Current explicit companion successor required')
    if p.payload!=packet_payload(actor,p.mapping,p.observation,p.destination,evidence,v):raise ValidationError('Companion evidence/acceptances changed')
    _,store_binding=adapter.store(v['store_ref'])
    return {**evidence,'store_binding':store_binding}

@transaction.atomic
def review(actor,case_id,mapping_id,verdict,rationale,operation_key,observation_id=None,packet_id=None):
    m=get(actor,case_id,mapping_id,'review');_,v=rules(m);principal(actor,m,'review',v);validate(KEY,operation_key)
    if verdict not in ['approve','hold'] or not isinstance(rationale,str) or not 1<=len(rationale.strip())<=1000 or observation_id is not None and packet_id is not None:
        raise ValidationError('Independent bounded single-subject Finance review required')
    evidence,v=pin(actor,m);o=None;p=None
    if observation_id is not None:
        o=Observation.objects.get(pk=observation_id,mapping=m);current_observation(m,o,evidence,v)
    if packet_id is not None:
        p=Packet.objects.select_related('mapping','observation','destination__contract').get(pk=packet_id,mapping=m)
        evidence=packet_pin(actor,p,evidence,v)
    evidence={**evidence,'observation_sha256':digest(o.result) if o else None,'packet_sha256':p.sha256 if p else None}
    values=dict(observation=o,packet=p,verdict=verdict,pin=evidence,rationale=rationale,actor=actor)
    old=Review.objects.filter(mapping=m,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=x for k,x in values.items()):raise ValidationError('Finance review key binds another immutable decision')
        return old
    return Review.objects.create(mapping=m,operation_key=operation_key,**values)

@transaction.atomic
def probe(actor,case_id,mapping_id,operation_key):
    m=get(actor,case_id,mapping_id,'operate');_,v=rules(m);principal(actor,m,'operate',v);validate(KEY,operation_key)
    evidence,v=pin(actor,m);reviewed(m,evidence,v)
    old=Observation.objects.filter(mapping=m,operation_key=operation_key).first()
    if old:
        if old.pin!=evidence or old.actor_id!=actor.pk:raise ValidationError('Native observation key binds another immutable intent')
        return old
    result=adapter.verify(m,d.effect(m.plan,m.effect_key),v,evidence['provider'])
    return Observation.objects.create(mapping=m,operation_key=operation_key,result=result,pin=evidence,actor=actor)

@transaction.atomic
def reserve(actor,case_id,packet_id,operation_key):
    p=Packet.objects.select_related('mapping__plan__case','mapping__plan__recovery__plan__case','observation','destination__contract').get(pk=packet_id,mapping__plan__case_id=case_id)
    m=p.mapping;_,v=rules(m);principal(actor,m,'operate',v);validate(KEY,operation_key)
    evidence,v=pin(actor,m);evidence=packet_pin(actor,p,evidence,v);r=reviewed(m,evidence,v,packet=p)
    op=digest({'packet':p.pk,'key':operation_key})
    intent={'format':adapter.FORMAT,'operation_key':op,'packet':p.pk,'packet_sha256':p.sha256,'manifest':p.payload,
        'pin':evidence,'authorization':r.pk,'rules':v,'store_ref':v['store_ref'],'store_binding':evidence['store_binding']}
    old=Job.objects.filter(operation_key=op).first()
    if old:
        if old.intent!=intent or old.actor_id!=actor.pk:raise ValidationError('Companion key binds another immutable publication')
        return old
    return Job.objects.create(packet=p,operation_key=op,intent=intent,actor=actor)

@transaction.atomic
def retry(actor,case_id,job_id):
    j=Job.objects.select_for_update().select_related('packet__mapping__plan__case').get(pk=job_id,packet__mapping__plan__case_id=case_id)
    _,v=rules(j.packet.mapping);principal(actor,j.packet.mapping,'operate',v)
    if j.status not in ['held','unknown']:raise ValidationError('Reconcile only an original held/uncertain publication')
    j.status='pending';j.save(update_fields=['status']);return j

def finish(j,receipt):
    if j.lease_until is None or j.lease_until<=timezone.now():raise ValidationError('Expired original companion fence')
    j.status,j.receipt,j.error='confirmed',receipt,'';j.save(update_fields=['status','receipt','error'])

def run_once():
    d.cold.control()
    with transaction.atomic():
        j=Job.objects.select_for_update(skip_locked=True).filter(Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lt=timezone.now())).order_by('pk').first()
        if not j:return False
        j.status,j.fence,j.attempts='leased',j.fence+1,j.attempts+1;j.lease_until=timezone.now()+timedelta(seconds=j.intent['rules']['lease_seconds'])
        j.save(update_fields=['status','fence','attempts','lease_until']);pk,fence=j.pk,j.fence
    with transaction.atomic():
        j=Job.objects.select_for_update().select_related('packet__mapping__plan__case','packet__mapping__plan__recovery__plan__case','packet__observation','packet__destination__contract','actor').get(pk=pk)
        if j.status!='leased' or j.fence!=fence:return True
        try:
            receipt=adapter.lookup(j.intent) # Reconcile the original file before effect authority/budget.
            if receipt is None:
                p=j.packet;m=p.mapping;_,v=rules(m);principal(j.actor,m,'operate',v)
                evidence,v=pin(j.actor,m);evidence=packet_pin(j.actor,p,evidence,v)
                r=reviewed(m,evidence,v,packet=p)
                if evidence!=j.intent['pin'] or v!=j.intent['rules'] or r.pk!=j.intent['authorization'] or j.attempts>v['max_attempts']:raise ValidationError('Current companion publication controls/original attempt budget differ')
                receipt=adapter.deliver(j.intent)
            finish(j,receipt)
        except (ValidationError,PermissionDenied,OSError,ValueError,psycopg.Error):
            j.status,j.error='held','native_finance_controls_held';j.save(update_fields=['status','error'])
    return True

@transaction.atomic
def report(actor,case_id,mapping_id):
    m=get(actor,case_id,mapping_id);result={'mapping':m.pk,'effect_key':m.effect_key,'policy_status':resolve(COMPONENT,m.plan.case).status,
        'mapping_review_current':False,'observations':[],'jobs':[],'holds':[],'activation_enabled':False,'business_jobs_reenacted':False}
    if 'variant' in m.payload:
        from apps.policy.invoice_receipt_validators import VARIANTS
        result['variant']=m.payload['variant'];result['variant_policy_status']=resolve(VARIANTS,m.plan.case).status
    evidence=None;v=None
    try:evidence,v=pin(actor,m);reviewed(m,evidence,v);result['mapping_review_current']=True
    except (ValidationError,PermissionDenied,OSError,psycopg.Error):result['holds'].append('Current physical mapping, Finance provider/criteria and independent review required')
    for o in Observation.objects.filter(mapping=m).select_related('actor').order_by('pk'):
        current=False;accepted=False
        try:
            if evidence is None:raise ValidationError('Current mapping required')
            current_observation(m,o,evidence,v);current=True;reviewed(m,evidence,v,o);accepted=True
        except (ValidationError,PermissionDenied,OSError,psycopg.Error):pass
        result['observations'].append({'id':o.pk,'outcome':o.result['outcome'],'current':current,'human_review_current':accepted,'classification':o.result['classification'],'direct_vendor_verification':False})
    for j in Job.objects.filter(packet__mapping=m).order_by('pk'):
        try:physical=j.status=='confirmed' and adapter.lookup(j.intent)==j.receipt
        except (ValidationError,OSError,ValueError):physical=False
        result['jobs'].append({'id':j.pk,'status':j.status,'attempts':j.attempts,'artifact_current':physical})
    return result

@transaction.atomic
def followup_projection(actor,case_id,packet_id):
    p=Packet.objects.select_related('mapping__plan__case','mapping__plan__recovery__plan__case','observation','destination__contract').get(pk=packet_id,mapping__plan__case_id=case_id)
    m=p.mapping
    if 'variant' not in m.payload:raise ValidationError('Invoice/correction companion required')
    principal(actor,m,'operate',rules(m)[1]);evidence,v=pin(actor,m);evidence=packet_pin(actor,p,evidence,v);reviewed(m,evidence,v,packet=p)
    j=Job.objects.filter(packet=p,status='confirmed').order_by('-pk').first()
    if not j or adapter.lookup(j.intent)!=j.receipt:raise ValidationError('Exact published companion receipt required')
    return {'format':'psl.finance-receipt-followup/v1','source_case_id':m.payload['source_case_id'],'source_invoice_id':m.payload['source_invoice_id'],
        'source_correction_id':m.payload['source_correction_id'],'variant':m.payload['variant'],'mapping_sha256':m.sha256,
        'observation_sha256':digest(p.observation.result),'packet_sha256':p.sha256,'publication_operation':j.operation_key,
        'outcome':p.observation.result['outcome'],'business_jobs_reenacted':False,'debt_waived':False,'activation_enabled':False}
