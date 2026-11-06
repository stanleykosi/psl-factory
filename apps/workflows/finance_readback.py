"""Current readback of an actually published inert follow-up, with independent review."""
from datetime import timedelta
from django.db import transaction,DatabaseError
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.documents.contracts import digest,validate
from apps.policy.services import active_component,reference_values
from apps.policy.followup_readback_validators import COMPONENT
from adapters.forecast import KEY
from adapters import finance_followup_readback as adapter
from . import native_finance as d
from .finance_readback_models import FinanceFollowupReadback as Observation,FinanceFollowupReadbackReview as Review

def packet(actor,case_id,packet_id,purpose):
    p=d.Packet.objects.select_related('mapping__plan__case','mapping__plan__recovery__plan__case','observation').get(pk=packet_id,mapping__plan__case_id=case_id)
    m=d.get(actor,case_id,p.mapping_id,purpose)
    if 'variant' not in m.payload:raise ValidationError('Published invoice/correction companion required')
    _,v=d.rules(m);d.principal(actor,m,purpose,v)
    return p

def published_context(actor,p):
    """Exact historical published request with current physical scope, without a readback-policy dependency."""
    m=p.mapping
    evidence,_=d.pin(actor,m) # Current complete physical source proof and exact provider/mapping scope.
    j=d.Job.objects.filter(packet=p,status='confirmed').order_by('-pk').first()
    if not j or d.adapter.lookup(j.intent)!=j.receipt or j.intent['manifest']!=p.payload:raise ValidationError('Original exact published Finance companion receipt required')
    # Preserve the original published request even when later business evidence changes.
    projection={'format':'psl.finance-receipt-followup/v1','source_case_id':m.payload['source_case_id'],'source_invoice_id':m.payload['source_invoice_id'],
        'source_correction_id':m.payload['source_correction_id'],'variant':m.payload['variant'],'mapping_sha256':m.sha256,
        'observation_sha256':digest(p.observation.result),'packet_sha256':p.sha256,'publication_operation':j.operation_key,'outcome':p.observation.result['outcome'],
        'business_jobs_reenacted':False,'debt_waived':False,'activation_enabled':False}
    return {'native':evidence,'packet_sha256':p.sha256,'publication_sha256':digest(j.receipt),'request_sha256':digest(projection)},projection

def context(actor,p):
    cfg=active_component(COMPONENT,p.mapping.plan.case);v=reference_values(cfg)[0]
    pin,projection=published_context(actor,p)
    return {**pin,'policy':cfg.pk},v,projection

@transaction.atomic
def probe(actor,case_id,packet_id,operation_key,include_successors=False):
    p=packet(actor,case_id,packet_id,'operate');validate(KEY,operation_key)
    evidence,v,projection=context(actor,p)
    if include_successors:evidence['lineage_contract']='psl.finance-successor-lineage/v1'
    old=Observation.objects.filter(packet=p,operation_key=operation_key).first()
    if old:
        if old.pin!=evidence or old.actor_id!=actor.pk:raise ValidationError('Readback key binds another immutable observation')
        return old
    from adapters import finance_successor_readback
    reader=finance_successor_readback if include_successors else adapter
    result=reader.read(p.mapping,projection,v,evidence['native']['provider'])
    return Observation.objects.create(packet=p,operation_key=operation_key,projection=projection,result=result,pin=evidence,actor=actor)

def current(actor,o):
    evidence,v,projection=context(actor,o.packet)
    from adapters import finance_successor_readback
    reader=adapter
    if o.pin.get('lineage_contract')==finance_successor_readback.VERSION:
        evidence['lineage_contract']=finance_successor_readback.VERSION;reader=finance_successor_readback
    if o.pin!=evidence or projection!=o.projection or timezone.now()>=o.created_at+timedelta(seconds=v['observation_valid_seconds']):raise ValidationError('Readback is stale; collect successor evidence')
    d.principal(o.actor,o.packet.mapping,'operate',d.rules(o.packet.mapping)[1])
    if reader.read(o.packet.mapping,projection,v,evidence['native']['provider'])!=o.result:raise ValidationError('Current source disposition changed; collect successor evidence')
    return evidence,v

@transaction.atomic
def review(actor,case_id,observation_id,verdict,rationale,operation_key):
    o=Observation.objects.select_related('packet__mapping__plan__case','packet__mapping__plan__recovery__plan__case','packet__observation','actor').get(pk=observation_id,packet__mapping__plan__case_id=case_id)
    packet(actor,case_id,o.packet_id,'review');validate(KEY,operation_key)
    if actor.pk==o.actor_id:raise PermissionDenied('Independent readback evidence reviewer required')
    if verdict not in ['approve','hold'] or not isinstance(rationale,str) or not 1<=len(rationale.strip())<=1000:raise ValidationError('Bounded human readback verdict/rationale required')
    evidence,v=current(actor,o);pin={**evidence,'result_sha256':digest(o.result)}
    values=dict(verdict=verdict,rationale=rationale,pin=pin,actor=actor)
    old=Review.objects.filter(observation=o,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=x for k,x in values.items()):raise ValidationError('Readback review key binds another decision')
        return old
    return Review.objects.create(observation=o,operation_key=operation_key,**values)

@transaction.atomic
def report(actor,case_id,observation_id):
    o=Observation.objects.select_related('packet__mapping__plan__case','packet__mapping__plan__recovery__plan__case','packet__observation','actor').get(pk=observation_id,packet__mapping__plan__case_id=case_id)
    d.get(actor,case_id,o.packet.mapping_id)
    result={'observation':o.pk,'recorded':o.result,'observation_current':False,'independent_review_current':False,'holds':[],
        'execution_authorized':False,'financial_effect_verified':False}
    try:
        evidence,v=current(actor,o);result['observation_current']=True
        r=Review.objects.filter(observation=o).select_related('actor').order_by('-pk').first()
        if not r or r.verdict!='approve' or r.pin!={**evidence,'result_sha256':digest(o.result)} or timezone.now()>=r.created_at+timedelta(seconds=v['review_valid_seconds']):raise ValidationError('Current independent readback review required')
        packet(r.actor,case_id,o.packet_id,'review');result['independent_review_current']=True
    except (ValidationError,PermissionDenied,OSError,DatabaseError,d.psycopg.Error):result['holds'].append('Current source acknowledgement, provider, policy, physical scope and independent review required')
    return result
