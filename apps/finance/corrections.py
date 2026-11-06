from decimal import Decimal,localcontext
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.contrib.auth import get_user_model
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values
from apps.pmo.services import subject
from adapters.financial_corrections import parse_note
from .analysis import note
from .billing import digest
from .rules import decimal,number
from .models import InvoiceIssue,InvoiceJob,InvoiceCorrection,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery,CashReversal
from . import cash,financial_reviews

KINDS={'credit':'invoice_credit_note','debit':'invoice_debit_note','void':'invoice_void_note'}

def accepted(issue):return InvoiceCorrectionAcceptance.objects.filter(correction__issue=issue).select_related('correction').order_by('pk')
def adjusted_face(issue):
    with localcontext() as ctx:
        ctx.prec=512;n=issue.invoice.amount
        for a in accepted(issue):n+=Decimal(a.payload['signed_delta'])
        return n

def state(issue):
    applied=list(accepted(issue))
    return {'issue':issue.pk,'obligation':issue.obligation_key,'invoice_hash':issue.sha256,'applied':[[a.pk,a.sha256] for a in applied],
        'face':number(adjusted_face(issue)),'voided':any(a.correction.kind=='void' for a in applied),
        'allocations':[[a.pk,number(a.amount)] for a in cash.allocations(issue=issue).order_by('pk')]}

def unresolved(issue,exclude=None):
    q=InvoiceJob.objects.filter(invoice=issue.invoice,kind='adjust',status__in=['pending','leased','unknown','held'])
    for job in q:
        if job.intent.get('correction')==exclude:continue
        if not InvoiceCorrectionAcceptance.objects.filter(correction_id=job.intent.get('correction')).exists():return True
    return False

@transaction.atomic
def capture(actor,case_id,issue_id,evidence_id,allocation_evidence_id,reason,expected):
    case=lock_case(actor,case_id,'finance.invoice.correction.draft',expected);require(actor,case,'finance.read');note(reason)
    issue=InvoiceIssue.objects.filter(pk=issue_id,invoice__case=case).first()
    if not issue:raise ValidationError('Correction requires this case proven issued invoice')
    evidence=case.evidence.filter(pk=evidence_id).first()
    if not evidence:raise ValidationError('Select this case supplied legal note')
    doc=parse_note(evidence.body)
    if evidence.kind!=KINDS[doc['kind']]:raise ValidationError('Note kind does not match its correction action')
    i=issue.invoice
    if (doc['invoice_reference'],doc['currency'],doc['amount_basis'])!=(i.reference,i.currency,i.amount_basis):raise ValidationError('Legal note does not identify exact invoice dimensions')
    old=InvoiceCorrection.objects.filter(case=case,evidence=evidence,issue=issue).order_by('-pk').first()
    current=state(issue)
    if old and old.payload['base_state']==current:return old
    if current['voided']:raise ValidationError('Void is terminal in this implementation; reopening needs a separate reviewed method')
    amount=Decimal(current['face']) if doc['kind']=='void' else decimal(doc['amount'],positive=True) if doc['amount'] is not None else None
    if doc['kind']=='void' and doc['amount'] is not None and decimal(doc['amount'],nonnegative=True)!=amount:raise ValidationError('Full void note must match current adjusted face')
    reference=doc['document_ref']
    if InvoiceCorrection.objects.filter(case=case,reference=reference).exclude(issue=issue).exists():raise ValidationError('Correction document reference belongs to a different invoice')
    if InvoiceCorrectionAcceptance.objects.filter(correction__case=case,correction__reference=reference).exists():raise ValidationError('This legal correction document was already applied')
    prev=InvoiceCorrection.objects.filter(case=case,reference=reference).order_by('-version').first()
    r=InvoiceCorrection.objects.create(case=case,issue=issue,reference=reference,version=prev.version+1 if prev else 1,kind=doc['kind'],amount=amount,
        payload={'document':doc,'base_state':current},evidence=evidence,allocation_evidence=subject(case,allocation_evidence_id,'cash_correction') if allocation_evidence_id else None,reason=reason,actor=actor)
    event(actor,case,'invoice.correction_captured',correction=r.pk,issue=issue.pk);bump(case);return r

def method(case):
    c=active_component('D08.duplicate_correction_rules',case);v=reference_values(c)[0]
    if 'correction' not in v:raise ValidationError('Configure the versioned canonical invoice correction method')
    return c,v['correction']

def review_snapshot(r):
    require(r.actor,r.case,'finance.invoice.correction.draft')
    if InvoiceCorrection.objects.filter(case=r.case,reference=r.reference,pk__gt=r.pk).exists():raise ValidationError('A newer legal correction document version exists')
    if state(r.issue)!=r.payload['base_state']:raise ValidationError('Invoice debt/allocation changed; capture a current correction version')
    if r.amount is None:raise ValidationError('Correction amount is unknown; capture exact known terms')
    c,m=method(r.case);p=financial_reviews.policy(r.case,'invoice_'+r.kind)
    if r.evidence.kind!=p['legal']['evidence_kind']:raise ValidationError('Required configured legal correction evidence missing')
    if r.kind not in m['allowed_kinds']:raise ValidationError('Correction kind is not enabled by policy')
    with localcontext() as ctx:
        ctx.prec=512
        if r.amount!=r.amount.quantize(Decimal(1).scaleb(-m['decimal_places'])):raise ValidationError('Correction exceeds configured precision; no implicit rounding')
        face=adjusted_face(r.issue)
        if r.kind in ['credit','void'] and r.amount>face:raise ValidationError('Credit/void exceeds current canonical face; no negative debt or implicit refund')
        if r.kind=='void' and r.amount!=face:raise ValidationError('Void must remove the full current face')
        paid=cash.sum_amount(cash.allocations(issue=r.issue));newface=face+r.amount if r.kind=='debit' else face-r.amount
        if newface>=Decimal('1e24'):raise ValidationError('Correction numeric budget exceeded')
        reverse=(r.kind=='void' and paid>0) or newface<paid
    if reverse:
        treatment=m['void_allocations'] if r.kind=='void' else m['credit_allocation_conflict']
        if treatment!='reverse_all_live_allocations':raise ValidationError('Configured correction holds until allocations are reversed')
        if not r.allocation_evidence_id:raise ValidationError('Explicit allocation-reversal evidence is required')
    return {'implementation':'financial-corrections/v1','request_hash':digest(r.payload),'state':state(r.issue),'method':c.pk,'policy':p,'reverse_allocations':reverse}

def effect_intent(actor,invoice,kind,role,correction_id):
    r=InvoiceCorrection.objects.filter(pk=correction_id,issue__invoice=invoice,case=invoice.case).first()
    if not r:raise ValidationError('Select exact invoice correction')
    from .invoices import adapter_config
    policies,adapter,identity=adapter_config(invoice.case)
    if kind=='adjust_deliver':
        a=InvoiceCorrectionAcceptance.objects.filter(correction=r).first()
        if not a:raise ValidationError('Correction must be proven applied before note delivery')
        require(get_user_model().objects.get(pk=adapter['recipient_id']),invoice.case,'finance.invoice.receive')
        return {'correction':r.pk,'policies':policies,'adapter':adapter,'identity':identity,'recipient':adapter['recipient_id'],'delivery_hash':digest(public_payload(a))}
    review=financial_reviews.approved(r);auth=financial_reviews.execution_authority(actor,r,'invoice_'+r.kind,role,'finance.invoice.correct')
    if role not in adapter['issuer_roles']:raise ValidationError('Correction issuer role is not configured')
    if unresolved(r.issue,exclude=r.pk):raise ValidationError('Another correction is reserved or uncertain; reconcile it before a competing change')
    snap=review_snapshot(r)
    if snap['reverse_allocations']:
        for a in cash.allocations(issue=r.issue):cash.correction_authority(actor,r.case,'allocation',role,a.lot)
    return {'correction':r.pk,'policies':policies,'adapter':adapter,'identity':identity,'review':review.pk,'issuer_role':role,'authority':auth,'snapshot':snap}

def guard_reserve(actor,case,correction_id,kind,role):
    require(actor,case,'finance.invoice.correct' if kind=='adjust' else 'finance.invoice.correction_deliver')
    if kind not in ['adjust','adjust_deliver']:raise ValidationError('Choose correction application or note delivery')
    r=InvoiceCorrection.objects.filter(case=case,pk=correction_id).first()
    if not r:raise ValidationError('Correction belongs to a different case')
    if kind=='adjust' and InvoiceCorrectionAcceptance.objects.filter(correction=r).exists():raise ValidationError('Correction already applied; preserve acceptance')
    value=effect_intent(actor,r.issue.invoice,kind,role,r.pk)
    old=InvoiceJob.objects.filter(invoice=r.issue.invoice,kind=kind,intent__correction=r.pk).order_by('-generation').first()
    if old:
        if old.intent!=value or old.actor_id!=actor.pk:raise ValidationError('Correction intent changed; use explicit operator reconciliation')
    return r,value,old


@transaction.atomic
def reserve(actor,case_id,correction_id,kind,role,expected):
    action='finance.invoice.correct' if kind=='adjust' else 'finance.invoice.correction_deliver'
    case=lock_case(actor,case_id,action,expected)
    r,value,old=guard_reserve(actor,case,correction_id,kind,role)
    if old:return old
    generation=(InvoiceJob.objects.filter(invoice=r.issue.invoice,kind=kind).aggregate(n=Max('generation'))['n'] or 0)+1
    job=InvoiceJob.objects.create(invoice=r.issue.invoice,kind=kind,generation=generation,intent=value,operation_key=f'invoice:{r.issue.invoice_id}:{kind}:g{generation}',actor=actor)
    event(actor,case,'invoice.correction_reserved',job=job.pk,correction=r.pk);bump(case);return job

def public_payload(a):
    r=a.correction;i=r.issue.invoice
    return {'document_type':r.kind+'_note','reference':r.reference,'version':r.version,'corrects_invoice':i.reference,
        'kind':r.kind,'amount':a.payload['amount'],'currency':i.currency,'amount_basis':i.amount_basis,'adjusted_face':a.payload['adjusted_face']}

def apply_local(job):
    r=InvoiceCorrection.objects.get(pk=job.intent['correction'],issue__invoice=job.invoice)
    if job.kind=='adjust_deliver':
        a=InvoiceCorrectionAcceptance.objects.get(correction=r);p=public_payload(a)
        receipt,_=InvoiceCorrectionDelivery.objects.get_or_create(correction=r,defaults={'job':job,'recipient_id':job.intent['recipient'],'payload':p,'sha256':digest(p)})
        if receipt.recipient_id!=job.intent['recipient'] or receipt.payload!=p:raise ValidationError('Correction delivery differs from immutable acceptance')
        return receipt.pk
    if InvoiceCorrectionAcceptance.objects.filter(correction__case=r.case,correction__reference=r.reference).exists():raise ValidationError('Legal note reference already applied')
    if job.intent['snapshot']['reverse_allocations']:
        for a in cash.allocations(issue=r.issue):
            auth=cash.correction_authority(job.actor,r.case,'allocation',job.intent['issuer_role'],a.lot)
            CashReversal.objects.create(allocation=a,evidence=r.allocation_evidence,authority=dict(auth,invoice_correction=r.pk),reason=r.reason,actor=job.actor)
    with localcontext() as ctx:
        ctx.prec=512;delta=r.amount if r.kind=='debit' else -r.amount
        p={'correction':r.pk,'obligation_key':r.issue.obligation_key,'kind':r.kind,'amount':number(r.amount),'signed_delta':number(delta),
            'prior_face':job.intent['snapshot']['state']['face'],'adjusted_face':number(adjusted_face(r.issue)+delta),'review':job.intent['review'],'source_hash':r.evidence.sha256}
    a=InvoiceCorrectionAcceptance.objects.create(correction=r,job=job,payload=p,sha256=digest(p))
    event(job.actor,r.case,'invoice.correction_applied',correction=r.pk,acceptance=a.pk,kind=r.kind);return a.pk
