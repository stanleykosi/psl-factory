import re,json
from decimal import localcontext
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction,IntegrityError
from apps.core.services import event,bump
from apps.identity.services import require
from apps.policy.services import active_component,reference_values,decision_authority
from apps.pmo.services import subject
from apps.finance.analysis import digest,note
from apps.finance.rules import decimal
from adapters.reconciliation import request as parse_request,outcome as parse_outcome,at
from . import reconciliation as recon
from .models import CorrectiveRequest,CorrectiveDecision,CorrectiveJob,CorrectiveDelivery,EngineeringOutcome,OutcomeVerification,ReconciliationRun

def config(request):
    c=active_component(recon.COMMANDS,request.case);m=reference_values(c)[0];choices=[r for r in m['commands'] if r['key']==request.payload['command']]
    if len(choices)!=1:raise ValidationError('Configure this exact business command')
    return c,m,choices[0]

@transaction.atomic
def capture(actor,case_id,run_id,reference,operation_key,evidence_id,reason,expected):
    case=recon.locked(actor,case_id,'baas.corrective.capture',expected);note(reason)
    if any(not isinstance(v,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}',v) for v in [reference,operation_key]):raise ValidationError('Use bounded explicit request and operation references')
    run=recon.exact(case,ReconciliationRun,run_id);e=subject(case,evidence_id,'corrective_request');v=parse_request(e.body)
    if not any((r['partner'],r['transaction'])==(v['partner'],v['transaction']) for r in run.result['rows']):raise ValidationError('Request must identify a captured transaction on this exact run')
    prev=CorrectiveRequest.objects.filter(case=case,reference=reference).order_by('-version').first()
    if prev and prev.operation_key!=operation_key:raise ValidationError('Request revisions retain their logical operation key')
    if CorrectiveRequest.objects.filter(case=case,operation_key=operation_key).exclude(reference=reference).exists():raise ValidationError('Logical operation belongs to another request family')
    if prev and prev.run_id==run.pk and prev.evidence_id==e.pk:return prev
    r=CorrectiveRequest.objects.create(case=case,run=run,reference=reference,version=prev.version+1 if prev else 1,operation_key=operation_key,payload=v,evidence=e,reason=reason,actor=actor)
    event(actor,case,'baas.corrective_captured',request=r.pk,run=run.pk);bump(case);return r

def snapshot(r):
    recon.ensure_current(r.run);require(r.actor,r.case,'baas.corrective.capture');require(r.actor,r.case,'baas.read')
    if CorrectiveRequest.objects.filter(case=r.case,reference=r.reference,version__gt=r.version).exists():raise ValidationError('A newer corrective request version exists')
    c,m,command=config(r);v=r.payload
    row=next(x for x in r.run.result['rows'] if (x['partner'],x['transaction'])==(v['partner'],v['transaction']))
    if r.run.result['status']=='held':raise ValidationError('Reconciliation method is not configured')
    if command['kind']!=v['kind'] or row['finding'] not in command['allowed_findings']:raise ValidationError('Finding does not satisfy configured command prerequisites')
    ledger=row['ledger']
    if not ledger or (ledger['customer'],ledger['currency'])!=(v['customer'],v['currency']) or v['currency']!=command['currency']:raise ValidationError('Request customer/currency differs from exact ledger/command dimensions')
    if command['require_queue_state'] is not None and (not row['queue_ready'] or row['queue']['queue_state']!=command['require_queue_state']):raise ValidationError('Current authoritative declared queue state prerequisite is unavailable or changed')
    if v['kind']=='queue_transition':
        if (v['from_state'],v['to_state'])!=(command['from_state'],command['to_state']):raise ValidationError('Queue transition is not the configured business command')
    else:
        if v['amount'] is None or ledger['amount'] is None:raise ValidationError('Financial request amount or source amount remains unknown')
        method=reference_values(active_component(recon.CONTRACT,r.case))[0];recon.precise(v['amount'],method)
        if decimal(v['amount'])>decimal(command['max_amount']):raise ValidationError('Requested amount exceeds configured human limit')
        if command['amount_rule']=='exact_ledger_amount' and decimal(v['amount'])!=decimal(ledger['amount']) or command['amount_rule']=='up_to_ledger_amount' and decimal(v['amount'])>decimal(ledger['amount']):raise ValidationError('Requested amount conflicts with configured source amount rule')
        if {'from_account':v['from_account'],'to_account':v['to_account']} not in command['account_pairs']:raise ValidationError('Requested account route is not explicitly allowed')
    return {'implementation':'engineering-corrective-request/v1','run':r.run_id,'run_hash':r.run.sha256,'request_hash':digest(v),'evidence_hash':r.evidence.sha256,'command_config':c.pk,'command':command}

def authority(actor,r,role,field,preparer=False):
    c,m,command=config(r)
    if role not in command[field] or preparer and actor.pk==r.actor_id and not command['allow_preparer_review']:raise PermissionDenied('Configured corrective role/preparer separation is not satisfied')
    return dict(decision_authority(actor,r.case,role),**{recon.COMMANDS:c.pk,'command_rule':command})

@transaction.atomic
def decide(actor,case_id,request_id,role,verdict,evidence_id,reason,expected):
    case=recon.locked(actor,case_id,'baas.corrective.decide',expected);r=recon.exact(case,CorrectiveRequest,request_id);note(reason)
    if verdict not in ['approve','return','reject']:raise ValidationError('Choose approve, return or reject')
    value=snapshot(r) if verdict=='approve' else {'request_hash':digest(r.payload)}
    auth=authority(actor,r,role,'approver_roles',True)
    d=CorrectiveDecision.objects.create(request=r,role=role,verdict=verdict,snapshot=value,authority=auth,evidence=subject(case,evidence_id,'corrective_decision'),reason=reason,actor=actor)
    event(actor,case,'baas.corrective_decided',decision=d.pk,request=r.pk,verdict=verdict);bump(case);return d

def approved(r):
    d=CorrectiveDecision.objects.filter(request=r).order_by('-pk').first()
    if not d or d.verdict!='approve':raise ValidationError('Exact configured human approval is required')
    require(d.actor,r.case,'baas.corrective.decide');require(d.actor,r.case,'baas.read')
    if authority(d.actor,r,d.role,'approver_roles',True)!=d.authority or snapshot(r)!=d.snapshot:raise ValidationError('Corrective decision/source/authority is stale')
    return d

def subject_key(r):
    return digest({k:r.payload[k] for k in ['partner','transaction','kind','from_state','to_state']})

def intent(actor,r,role):
    require(actor,r.case,'baas.corrective.dispatch');require(actor,r.case,'baas.read');d=approved(r);auth=authority(actor,r,role,'sender_roles');c,m,command=config(r)
    from django.contrib.auth import get_user_model
    recipient=get_user_model().objects.get(pk=m['recipient_id']);require(recipient,r.case,'baas.engineering.receive');decision_authority(recipient,r.case,'Engineering')
    if CorrectiveDelivery.objects.filter(tenant=r.case.tenant,subject_key=subject_key(r)).exists():raise ValidationError('This transaction command already has an Engineering receipt; reconcile its outcome')
    for j in CorrectiveJob.objects.filter(request__case__tenant=r.case.tenant,status__in=['pending','leased','unknown','held']).select_related('request'):
        if j.request_id!=r.pk and (j.request.operation_key==r.operation_key or subject_key(j.request)==subject_key(r)):raise ValidationError('Another matching request is reserved or uncertain; reconcile it first')
    public={'operation_key':r.operation_key,'request_hash':digest(r.payload),'command':r.payload,'reason':r.reason,'delivery_only':True,'financial_execution_authorized':False}
    return {'decision':d.pk,'snapshot':d.snapshot,'authority':auth,'sender_role':role,'recipient':recipient.pk,'command_config':c.pk,'lease_seconds':m['lease_seconds'],'max_attempts':m['max_attempts'],'execution_source':m['execution_source'],'public':public,'subject_key':subject_key(r)}

@transaction.atomic
def reserve(actor,case_id,request_id,role,expected):
    case=recon.locked(actor,case_id,'baas.corrective.dispatch',expected);r=recon.exact(case,CorrectiveRequest,request_id)
    value=intent(actor,r,role);old=CorrectiveJob.objects.filter(request=r).order_by('-generation').first()
    if old:
        if old.intent!=value or old.actor_id!=actor.pk:raise ValidationError('Reserved intent changed; use explicit operator reconciliation')
        return old
    try:
        with transaction.atomic():j=CorrectiveJob.objects.create(request=r,generation=1,intent=value,actor=actor,tenant=case.tenant,operation_key=r.operation_key,subject_key=value['subject_key'])
    except IntegrityError:raise ValidationError('A matching transaction command is already reserved; reconcile before another request')
    event(actor,case,'baas.engineering_handoff_reserved',request=r.pk,job=j.pk);bump(case);return j

@transaction.atomic
def record_outcome(actor,case_id,delivery_id,evidence_id,expected):
    case=recon.locked(actor,case_id,'baas.engineering.record',expected)
    delivery=CorrectiveDelivery.objects.filter(pk=delivery_id,request__case=case,recipient=actor).first()
    if not delivery:raise ValidationError('Select this authenticated Engineering recipient delivery')
    require(actor,case,'baas.engineering.receive');auth=decision_authority(actor,case,'Engineering');e=subject(case,evidence_id,'engineering_outcome');v=parse_outcome(e.body)
    if (v['operation_key'],v['request_hash'],v['command'],v['source'])!=(delivery.operation_key,delivery.payload['request_hash'],delivery.payload['command'],delivery.job.intent['execution_source']):raise ValidationError('Outcome correlation, command or source differs from exact delivered request')
    old=EngineeringOutcome.objects.filter(delivery=delivery,evidence=e).first()
    if old:return old
    r=EngineeringOutcome.objects.create(delivery=delivery,evidence=e,payload=v,authority=auth,actor=actor);event(actor,case,'baas.engineering_outcome_reported',outcome=r.pk,delivery=delivery.pk,status=v['status']);bump(case);return r

@transaction.atomic
def verify_outcome(actor,case_id,outcome_id,role,evidence_id,expected):
    case=recon.locked(actor,case_id,'baas.corrective.verify_outcome',expected)
    outcome=EngineeringOutcome.objects.filter(pk=outcome_id,delivery__request__case=case).first()
    if not outcome:raise ValidationError('Select this case exact Engineering outcome')
    r=outcome.delivery.request;c,m,command=config(r);auth=authority(actor,r,role,'verifier_roles')
    if command['distinct_outcome_verifier'] and actor.pk==outcome.actor_id:raise PermissionDenied('Configured outcome verifier must differ from reporting engineer')
    proof=subject(case,evidence_id,'engineering_outcome_verification')
    if parse_outcome(proof.body)!=outcome.payload or outcome.payload['status']=='unknown':raise ValidationError('Exact terminal outcome verification required; unknown is not success')
    if at(outcome.payload['observed_at'])<outcome.delivery.created_at:raise ValidationError('Reported execution predates its actual request delivery')
    old=OutcomeVerification.objects.filter(delivery=outcome.delivery).first()
    if old:
        if old.outcome_id!=outcome.pk:raise ValidationError('A terminal verified outcome already exists; preserve history and investigate')
        return old
    v=OutcomeVerification.objects.create(delivery=outcome.delivery,outcome=outcome,evidence=proof,authority=auth,actor=actor);event(actor,case,'baas.engineering_outcome_verified',verification=v.pk,status=outcome.payload['status'],source_assurance='supplied_engineering_evidence_only');bump(case);return v
