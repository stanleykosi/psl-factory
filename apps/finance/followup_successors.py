"""Source-owned lineage only. Financial actions retain their ordinary service controls."""
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.core.services import lock_case
from apps.policy.services import active_component,reference_values,decision_authority
from apps.policy.followup_successor_validators import COMPONENT,KINDS,EVIDENCE
from apps.documents.contracts import validate,digest
from adapters.forecast import KEY
from adapters.invoices import InternalInvoiceAdapter
from . import receipt_followup as source
from .models import FinanceFollowupSuccessor as Proposal,FinanceFollowupSuccessorReview as Review,InvoiceJob,InvoiceCorrection

def rationale(note):
    if not isinstance(note,str) or not 1<=len(note.strip())<=1000:raise ValidationError('Explicit bounded human lineage rationale required')

def scope(r,original,successor,relation):
    p=r.projection
    if relation not in KINDS or original.pk==successor.pk:raise ValidationError('Distinct original and successor with a supported relationship required')
    if original.invoice.case_id!=r.case_id or successor.invoice.case_id!=r.case_id or original.invoice_id!=p['source_invoice_id'] or successor.invoice_id!=original.invoice_id:
        raise ValidationError('Exact same-case incumbent invoice and obligation required')
    if original.kind!=p['variant'] or original.intent.get('correction')!=p['source_correction_id']:raise ValidationError('Original intent must match the exact follow-up subject')
    if relation=='intent_generation':
        if successor.kind!=original.kind or successor.generation<=original.generation or successor.intent.get('correction')!=original.intent.get('correction'):
            raise ValidationError('Later generation of the exact original financial subject required')
    else:
        if successor.kind not in ['adjust','adjust_deliver'] or not successor.intent.get('correction'):raise ValidationError('Explicit legal correction intent required')
        target=InvoiceCorrection.objects.filter(pk=successor.intent['correction'],case_id=r.case_id,issue__invoice_id=original.invoice_id).first()
        if target is None or target.pk==p['source_correction_id']:raise ValidationError('Distinct same-obligation legal correction document required')
        if p['source_correction_id'] is not None:
            old=InvoiceCorrection.objects.get(pk=p['source_correction_id'],case_id=r.case_id,issue__invoice_id=original.invoice_id)
            if target.reference==old.reference and target.version<=old.version:raise ValidationError('A legal document successor must advance its version')

def subject_pin(r,original,successor):
    return {'request_sha256':r.sha256,'original_intent_sha256':digest(original.intent),'successor_intent_sha256':digest(successor.intent),
        'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}

@transaction.atomic
def propose(a,case_id,request_id,original_id,successor_id,relation,evidence_id,note,operation_key):
    c=lock_case(a,case_id,'finance.receipt_followup.decide');source.access(a,c,'decide')
    r=source.Request.objects.get(pk=request_id,case=c);validate(KEY,operation_key);rationale(note)
    original=InvoiceJob.objects.get(pk=original_id,invoice__case=c);successor=InvoiceJob.objects.get(pk=successor_id,invoice__case=c)
    scope(r,original,successor,relation)
    e=c.evidence.filter(pk=evidence_id,kind__in=EVIDENCE).first()
    if e is None:raise ValidationError('Same-case lineage evidence required')
    # Proposal capture works before missing owner/reviewer policy; acceptance is separately gated.
    values=dict(original=original,successor=successor,relation=relation,evidence=e,note=note,pin=subject_pin(r,original,successor),actor=a)
    old=Proposal.objects.filter(followup=r,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=v for k,v in values.items()):raise ValidationError('Proposal key already binds different lineage')
        return old
    return Proposal.objects.create(followup=r,operation_key=operation_key,**values)

def acceptance(p):
    r=p.followup;c=r.case;cfg=active_component(COMPONENT,c);v=reference_values(cfg)[0]
    if p.relation not in v['relations'] or p.evidence.kind not in v['evidence_kinds']:raise ValidationError('Relationship/evidence not enabled by current criteria')
    if timezone.now()>=p.created_at+timedelta(seconds=v['valid_seconds']):raise ValidationError('Lineage proposal expired')
    owner_cfg,owner_values,owner_authority=source.owner(p.actor,c)
    latest=source.Decision.objects.filter(followup=r).select_related('actor','job').defer('note','actor__password','actor__username','actor__first_name','actor__last_name','actor__email').order_by('-pk').first()
    if source.disposition(r,latest)['status']!='current' or latest.verdict=='decline':raise ValidationError('Current source-owned non-declining investigation required')
    scope(r,p.original,p.successor,p.relation)
    if p.pin!=subject_pin(r,p.original,p.successor) or not source.current_job(p.successor):raise ValidationError('Successor intent changed or was superseded')
    if InvoiceJob.objects.filter(invoice_id=p.original.invoice_id,status='unknown').exists() or InvoiceJob.objects.filter(invoice_id=p.original.invoice_id,status='leased',lease_until__gt=timezone.now()).exists():raise ValidationError('Reconcile uncertain or actively leased effects before lineage acceptance')
    if p.successor.status in ['cancelled','replaced']:raise ValidationError('Current successor required')
    adapter=InternalInvoiceAdapter()
    old_receipt=adapter.lookup(p.original)
    if p.relation=='intent_generation' and (p.original.status!='replaced' or old_receipt and p.original.kind in ['adjust','adjust_deliver'] and old_receipt.job_id==p.original_id):
        raise ValidationError('Use normal operator replacement and canonical receipt reconciliation')
    if p.relation=='legal_correction' and not old_receipt and p.original.status not in ['cancelled','replaced']:
        raise ValidationError('Original effect must be proven or explicitly cancelled/replaced through normal controls')
    return cfg,v,{'subject':p.pin,'policy':cfg.pk,'owner_policy':owner_cfg.pk,'owner_authority':owner_authority,'decision':latest.pk}

def reviewer(a,c,v):
    source.access(a,c,'review_successor')
    if a.pk!=v['reviewer_id']:raise PermissionDenied('Configured Finance lineage reviewer required')
    return decision_authority(a,c,v['reviewer_role'])

@transaction.atomic
def review(a,case_id,proposal_id,verdict,evidence_id,note,operation_key):
    c=lock_case(a,case_id,'finance.receipt_followup.review_successor');source.access(a,c,'review_successor')
    p=Proposal.objects.select_related('followup__case','original__invoice','successor__invoice','actor','evidence').get(pk=proposal_id,followup__case=c)
    validate(KEY,operation_key);rationale(note)
    cfg=active_component(COMPONENT,c);v=reference_values(cfg)[0];authority=reviewer(a,c,v)
    if a.pk==p.actor_id:raise PermissionDenied('Independent human lineage review required')
    if verdict not in ['approve','hold']:raise ValidationError('Approve or hold required')
    e=c.evidence.filter(pk=evidence_id,kind__in=v['evidence_kinds']).first()
    if e is None:raise ValidationError('Current same-case review evidence required')
    pin=acceptance(p)[2] if verdict=='approve' else {'policy':cfg.pk,'subject':p.pin}
    pin={**pin,'reviewer_authority':authority,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}
    values=dict(verdict=verdict,pin=pin,evidence=e,note=note,actor=a)
    old=Review.objects.filter(proposal=p,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=v for k,v in values.items()):raise ValidationError('Review key binds different evidence')
        return old
    if verdict=='approve':
        # Case lock serialises competing source-owned proposals. Prior acceptance must be explicitly held first.
        others=Proposal.objects.filter(followup=p.followup).exclude(pk=p.pk)
        for other in others:
            prior=Review.objects.filter(proposal=other).order_by('-pk').first()
            if prior and prior.verdict=='approve' and status(other)['status']=='current':raise ValidationError('Another current accepted successor exists; record an explicit hold first')
    return Review.objects.create(proposal=p,operation_key=operation_key,**values)

def status(p):
    latest=Review.objects.filter(proposal=p).select_related('actor').only('id','verdict','pin','actor__id','actor__is_active').order_by('-pk').first()
    result={'proposal_ref':str(p.pk),'relation':p.relation,'successor_ref':str(p.successor_id),'status':'proposed' if latest is None else 'held',
        'review_ref':str(latest.pk) if latest else None,'successor_receipt':'unverified','execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}
    if latest is None or latest.verdict!='approve':return result
    try:
        cfg,v,pin=acceptance(p);authority=reviewer(latest.actor,p.followup.case,v)
        if latest.actor_id==p.actor_id or latest.pin!={**pin,'reviewer_authority':authority,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}:raise ValidationError('Reviewed lineage authority changed')
        receipt=InternalInvoiceAdapter().lookup(p.successor)
        result.update(status='current',successor_receipt='present' if receipt else 'unknown')
    except (ValidationError,PermissionDenied):result['status']='stale'
    return result

@transaction.atomic
def report(a,case_id,request_id):
    c=lock_case(a,case_id,'finance.receipt_followup.read');source.access(a,c)
    r=source.Request.objects.get(pk=request_id,case=c)
    return {'request_sha256':r.sha256,'lineage':[status(p) for p in Proposal.objects.filter(followup=r).select_related('followup__case','original__invoice','successor__invoice','actor','evidence').order_by('-pk')[:50]],
        'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}
