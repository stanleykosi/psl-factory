"""Current source-owned review of read-only recovery companion contracts."""
from datetime import timedelta
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.domain_contract_validators import COMPONENT
from apps.documents.contracts import validate,digest
from adapters import domain_contracts as adapter
from adapters.forecast import KEY
from . import reconstitution as d
from .domain_contract_models import DomainContract as Contract,DomainObservation as Observation,DomainContractReview as Review


def get(actor,case_id,contract_id,purpose='read'):
    r=Contract.objects.select_related('plan__case','plan__recovery__plan__case').get(pk=contract_id,plan__case_id=case_id)
    d.access(actor,r.plan.case,purpose)
    return r

def owner(actor,r,purpose):
    action='reconstitution.domain.'+r.payload['family']+'.'+purpose if r.kind=='provider' else 'reconstitution.destination.'+purpose
    require(actor,r.plan.case,action)

def rules(r):
    cfg=active_component(COMPONENT,r.plan.case);v=reference_values(cfg)[0]
    if r.payload['provider_ref'] not in v['allowed_provider_refs'] or v['destination_ref']!=r.plan.payload['destination_ref']:
        raise ValidationError('Current allowed provider and exact destination criteria required')
    if r.kind=='destination' and r.payload['destination_ref']!=v['destination_ref']:
        raise ValidationError('Exact intended destination required')
    if Contract.objects.filter(plan=r.plan,reference=r.reference,version__gt=r.version).exists():
        raise ValidationError('Use the explicit current contract successor')
    return cfg,v

def principal(actor,r,purpose,v):
    d.access(actor,r.plan.case,purpose);owner(actor,r,'review' if purpose=='review' else 'verify')
    prefix='reviewer' if purpose=='review' else 'operator'
    if actor.pk!=v[prefix+'_id']:raise PermissionDenied('Exact current configured domain purpose principal required')
    decision_authority(actor,r.plan.case,v[prefix+'_role'])
    if purpose=='review' and (actor.pk==r.actor_id or Observation.objects.filter(contract=r,actor=actor).exists()):
        raise PermissionDenied('Independent source-owned review required')

def pin(actor,r):
    cfg,v=rules(r)
    physical=d.pin(r.plan,actor)
    binding,_=adapter.binding(r)
    return {'contract_sha256':r.sha256,'policy':cfg.pk,'reconstitution':physical,'binding':binding},v

@transaction.atomic
def capture(actor,case_id,plan_id,reference,kind,payload,evidence_id,predecessor=None):
    p=d.Plan.objects.select_related('case','recovery__plan__case').get(pk=plan_id,case_id=case_id)
    d.access(actor,p.case,'capture');validate(KEY,reference);validate(adapter.schema(kind),payload)
    if kind=='destination' and payload['destination_ref']!=p.payload['destination_ref']:
        raise ValidationError('Exact captured intended destination required')
    evidence=p.case.evidence.filter(pk=evidence_id,kind='integration_contract').first()
    if evidence is None:raise ValidationError('Same-case integration contract evidence required')
    old=Contract.objects.filter(plan=p,reference=reference).order_by('-version').first()
    if old and old.kind!=kind:raise ValidationError('Contract kind cannot change across successors')
    if old and old.payload==payload and old.evidence_id==evidence_id:return old
    if (old.pk if old else None)!=predecessor:raise ValidationError('Explicit current predecessor required')
    return Contract.objects.create(plan=p,reference=reference,kind=kind,payload=payload,sha256=digest(payload),
        version=old.version+1 if old else 1,evidence=evidence,actor=actor)

def reviewed(actor,r,evidence,v,observation=None):
    review=Review.objects.filter(contract=r,observation=observation).select_related('actor').order_by('-pk').first()
    expected={**evidence,'observation':observation.pk if observation else None,
              'observation_sha256':digest(observation.result) if observation else None}
    if not review or review.verdict!='approve' or review.pin!=expected or timezone.now()>=review.created_at+timedelta(seconds=v['review_valid_seconds']):
        raise ValidationError('Current independent exact contract/evidence review required')
    principal(review.actor,r,'review',v)
    if observation:adapter.current(observation.result,v['observation_valid_seconds'])
    if observation:principal(observation.actor,r,'operate',v)
    return review

@transaction.atomic
def review(actor,case_id,contract_id,verdict,rationale,operation_key,observation_id=None):
    r=get(actor,case_id,contract_id,'review');_,v=rules(r);principal(actor,r,'review',v)
    validate(KEY,operation_key)
    if verdict not in ['approve','hold'] or not isinstance(rationale,str) or not 1<=len(rationale.strip())<=1000:
        raise ValidationError('Explicit bounded human review required')
    evidence,v=pin(actor,r);observation=None
    if observation_id is not None:
        observation=Observation.objects.filter(pk=observation_id,contract=r).first()
        if not observation or observation.pin!=evidence:raise ValidationError('Exact current same-contract observation required')
        principal(observation.actor,r,'operate',v)
        adapter.current(observation.result,v['observation_valid_seconds'])
    evidence={**evidence,'observation':observation.pk if observation else None,'observation_sha256':digest(observation.result) if observation else None}
    values=dict(observation=observation,verdict=verdict,pin=evidence,rationale=rationale,actor=actor)
    old=Review.objects.filter(contract=r,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=x for k,x in values.items()):raise ValidationError('Review key binds another immutable decision')
        return old
    return Review.objects.create(contract=r,operation_key=operation_key,**values)

@transaction.atomic
def probe(actor,case_id,contract_id,operation_key,effect_key=''):
    r=get(actor,case_id,contract_id,'operate');_,v=rules(r);principal(actor,r,'operate',v);validate(KEY,operation_key)
    evidence,v=pin(actor,r);reviewed(actor,r,evidence,v)
    request={'format':r.payload['contract_version'],'contract_sha256':r.sha256,'plan_sha256':r.plan.sha256,
        'archive_sha256':r.plan.recovery.receipt['archive_sha256'],'destination_ref':r.plan.payload['destination_ref']}
    if r.kind=='provider':
        row=d.effect(r.plan,effect_key)
        if row['family']!=r.payload['family']:raise ValidationError('Exact reviewed source family required')
        request.update(effect={k:row[k] for k in ['case_id','family','effect_key','operation_sha256','intent_sha256']},
            source_payload_version=r.payload['source_payload_version'],operation_mapping=r.payload['operation_mapping'],intent_mapping=r.payload['intent_mapping'])
    else:
        if effect_key:raise ValidationError('Destination preflight has no business effect')
        request['prerequisites']={k:r.payload[k+'_ref'] for k in adapter.PREREQUISITES}
    old=Observation.objects.filter(contract=r,operation_key=operation_key).first()
    if old:
        if old.actor_id!=actor.pk or old.request!=request or old.pin!=evidence or old.effect_key!=effect_key:
            raise ValidationError('Observation key binds another immutable request')
        # Historical identity is returned, freshness is an explicit report/review question.
        return old
    result=adapter.verify(r,request,evidence['binding'],v['observation_valid_seconds'])
    return Observation.objects.create(contract=r,operation_key=operation_key,effect_key=effect_key,request=request,result=result,pin=evidence,actor=actor)

@transaction.atomic
def report(actor,case_id,contract_id):
    r=get(actor,case_id,contract_id)
    result={'contract':r.pk,'kind':r.kind,'version':r.version,'policy_status':resolve(COMPONENT,r.plan.case).status,
        'review_current':False,'observations':[],'holds':[],'activation_enabled':False,'business_jobs_reenacted':False,'debt_waived':False}
    evidence=None;v=None
    try:
        evidence,v=pin(actor,r);reviewed(actor,r,evidence,v);result['review_current']=True
    except (ValidationError,PermissionDenied,OSError):result['holds'].append('Current physical recovery, source-owned review, protocol and deployment binding required')
    for o in Observation.objects.filter(contract=r).order_by('pk'):
        current=False;accepted=False
        try:
            if evidence is None or o.pin!=evidence:raise ValidationError('Stale contract evidence')
            adapter.current(o.result,v['observation_valid_seconds']);current=True
            if not result['review_current']:raise ValidationError('Contract review held')
            reviewed(actor,r,evidence,v,o);accepted=True
        except (ValidationError,PermissionDenied):pass
        result['observations'].append({'id':o.pk,'effect_key':o.effect_key,'current':current,'human_review_current':accepted,
            'outcome':o.result.get('outcome'),'prerequisites':o.result.get('prerequisites'),
            'classification':o.result['classification'],'direct_vendor_verification':False})
    return result
