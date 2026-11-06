"""Current source-owned follow-up. Supplied control metadata never grants authority."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError,PermissionDenied
from apps.identity.services import require
from apps.core.services import lock_case
from apps.policy.services import active_component,reference_values,decision_authority,resolve
from apps.policy.invoice_receipt_validators import FOLLOWUP
from apps.documents.contracts import validate,digest
from adapters.forecast import obj,KEY
from .models import FinanceReceiptFollowup as Request,FinanceReceiptFollowupDecision as Decision,InvoiceJob

SHA={'type':'string','pattern':'^[a-f0-9]{64}$'}
PROJECTION=obj({'format':{'const':'psl.finance-receipt-followup/v1'},'source_case_id':{'type':'string','format':'uuid'},
 'source_invoice_id':{'type':'integer','minimum':1},'source_correction_id':{'anyOf':[{'type':'integer','minimum':1},{'type':'null'}]},
 'variant':{'enum':['issue','deliver','adjust','adjust_deliver']},'mapping_sha256':SHA,'observation_sha256':SHA,
 'packet_sha256':SHA,'publication_operation':SHA,'outcome':{'enum':['present','unknown','conflict']},
 'business_jobs_reenacted':{'const':False},'debt_waived':{'const':False},'activation_enabled':{'const':False}})

def access(a,c,purpose='read'):
    require(a,c,'finance.read');require(a,c,'finance.receipt_followup.'+purpose)

@transaction.atomic
def receive(a,case_id,projection,evidence_id):
    c=lock_case(a,case_id,'finance.receipt_followup.receive');access(a,c,'receive');validate(PROJECTION,projection)
    if projection['source_case_id']!=str(c.pk):raise ValidationError('Exact current source Finance case required')
    if (projection['source_correction_id'] is not None)!=(projection['variant'] in ['adjust','adjust_deliver']):raise ValidationError('Exact invoice/correction subject required')
    e=c.evidence.filter(pk=evidence_id,kind='integration_contract').first()
    if e is None:raise ValidationError('Source owner supplied same-case handoff evidence required')
    key=digest(projection)
    old=Request.objects.filter(request_key=key).first()
    if old:return old
    return Request.objects.create(case=c,request_key=key,projection=projection,sha256=key,evidence=e,actor=a)

def owner(a,c):
    access(a,c,'decide');cfg=active_component(FOLLOWUP,c);v=reference_values(cfg)[0]
    if a.pk!=v['owner_id']:raise PermissionDenied('Configured current Finance follow-up owner required')
    authority=decision_authority(a,c,v['owner_role'])
    return cfg,v,authority

def current_job(job):
    q=InvoiceJob.objects.filter(invoice_id=job.invoice_id,kind=job.kind,generation__gt=job.generation)
    if job.kind in ['adjust','adjust_deliver']:q=q.filter(intent__correction=job.intent.get('correction'))
    return job.status not in ['cancelled','replaced'] and not q.exists()

@transaction.atomic
def decide(a,case_id,request_id,verdict,note,operation_key,job_id=None):
    c=lock_case(a,case_id,'finance.receipt_followup.decide');r=Request.objects.get(pk=request_id,case=c)
    cfg,v,authority=owner(a,c);validate(KEY,operation_key)
    if verdict not in v['resolutions'] or not isinstance(note,str) or not 1<=len(note.strip())<=1000:raise ValidationError('Configured resolution and human rationale required')
    if timezone.now()>=r.created_at+timedelta(seconds=v['request_valid_seconds']):raise ValidationError('Follow-up is stale; collect fresh reviewed evidence')
    job=None
    if verdict=='link_current_intent':
        job=InvoiceJob.objects.filter(pk=job_id,invoice__case=c,invoice_id=r.projection['source_invoice_id']).first()
        if job is None:raise ValidationError('Explicit same-case incumbent invoice intent required')
        if not current_job(job):raise ValidationError('Select the current unreplaced invoice intent')
        if r.projection['source_correction_id'] is not None and job.intent.get('correction')!=r.projection['source_correction_id']:
            raise ValidationError('Explicit exact correction intent required')
        # This link is an investigation disposition, never evidence that execution is authorised.
    elif job_id is not None:raise ValidationError('Only link-current-intent may reference a job')
    pin={'request_sha256':r.sha256,'policy':cfg.pk,'authority':authority,'job_intent_sha256':digest(job.intent) if job else None,
        'execution_authorized':False,'financial_effect_verified':False}
    values=dict(verdict=verdict,job=job,pin=pin,note=note,actor=a)
    old=Decision.objects.filter(followup=r,operation_key=operation_key).first()
    if old:
        if any(getattr(old,k)!=x for k,x in values.items()):raise ValidationError('Follow-up key binds another decision')
        return old
    return Decision.objects.create(followup=r,operation_key=operation_key,**values)

@transaction.atomic
def report(a,case_id,request_id):
    c=lock_case(a,case_id,'finance.receipt_followup.read');access(a,c)
    r=Request.objects.get(pk=request_id,case=c);latest=Decision.objects.filter(followup=r).select_related('actor','job').order_by('-pk').first()
    evaluation=disposition(r,latest)
    from .transport_models import FinanceAuthenticatedIntake
    authenticated=FinanceAuthenticatedIntake.objects.filter(followup=r).exists()
    return {'request':r.pk,'request_sha256':r.sha256,'source':'authenticated_metadata_intake_history' if authenticated else 'human_supplied_reviewed_companion_metadata',
        'variant':r.projection['variant'],'supplied_outcome':r.projection['outcome'],
        'policy_status':resolve(FOLLOWUP,c).status,'latest_decision':latest.verdict if latest else None,'decision_current':evaluation['status']=='current',
        'disposition_status':evaluation['status'],'hold_code':evaluation['hold_code'],
        'job':latest.job_id if latest else None,'execution_authorized':False,'financial_effect_verified':False,'debt_waived':False}

def disposition(r,latest):
    """Read-only shared source evaluator. Authority comes from current source records."""
    status,hold='absent','no_owner_disposition'
    if latest:
        state=resolve(FOLLOWUP,r.case).status
        if state!='ACTIVE':return {'status':'revoked' if state=='REVOKED' else 'stale' if state=='EXPIRED' else 'unavailable','hold_code':'owner_policy_'+state.lower()}
        try:
            cfg,v,authority=owner(latest.actor,r.case)
            status,hold='stale','owner_policy_or_role_changed'
            if cfg.pk==latest.pin.get('policy') and authority==latest.pin.get('authority') and latest.verdict in v['resolutions']:
                if timezone.now()>=r.created_at+timedelta(seconds=v['request_valid_seconds']):hold='request_expired'
                elif (digest(latest.job.intent) if latest.job else None)!=latest.pin.get('job_intent_sha256') or latest.job is not None and not current_job(latest.job):hold='intent_changed_or_superseded'
                else:status,hold='current',None
        except PermissionDenied:status,hold='revoked','owner_identity_or_grant_revoked'
        except ValidationError:status,hold='unavailable','current_owner_authority_unavailable'
    return {'status':status,'hold_code':hold}
