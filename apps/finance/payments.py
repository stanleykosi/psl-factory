"""D13 payment evidence and human decisions, independent of release authority.

The only effect here is an immutable local control reservation. No deployment,
cash movement, credit or debt waiver is implemented by this module.
"""
from decimal import Decimal,localcontext
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from apps.core.services import lock_case,event,bump
from apps.identity.services import require
from apps.identity.models import Grant
from apps.policy.services import resolve,active_component,reference_values,decision_authority
from apps.policy.payment_validators import ROLE,PEOPLE,DELEGATION,VALIDITY,DENOMINATOR,FUNDS
from apps.pmo.clocks import aware
from apps.pmo.services import subject
from apps.pmo.commercial import note_required
from apps.pmo.delivery import dossier_for,latest,ensure_open
from apps.documents.controlled import baseline_manifest
from .models import BillingCoverage,InvoiceIssue,PaymentAssessment,PaymentException,PaymentDecision,PaymentReleaseReservation
from .billing import digest
from .rules import number
from .receivables import calculate,facts
from .cash import lot_payload

def locked(actor,case_id,action,expected=None):
    case=lock_case(actor,case_id,action,expected)
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    require(actor,case,'payment.read');require(actor,case,'finance.read');require(actor,case,'delivery.read')
    return case

def context(d):
    ensure_open(d)
    request=latest(d,'glpi_request',False)
    return {'dossier':d.pk,'candidate':d.candidate_id,'baseline':baseline_manifest(d.case),'deployment_request':request.pk if request else None,'external_ref':request.data['external_ref'] if request else None}

def inputs(case,d,cov):
    if not BillingCoverage.objects.filter(case=case,pk=cov.pk).exists():raise ValidationError('Select exact case billing coverage')
    source,position=calculate(case,timezone.localdate())
    policy={};values={};findings=[]
    for key in [DENOMINATOR,FUNDS]:
        r=resolve(key,case);policy[key]={'status':r.status,'id':r.configuration.pk if r.configuration else None}
        if r.status=='ACTIVE':values[key]=reference_values(r.configuration)[0]
        else:findings.append(key+': '+r.status)
    manifest={'implementation':'payment-assessment/v1','context':context(d),'coverage':cov.pk,'coverage_version':cov.version,'source':source,'policies':policy}
    result={'status':'UNKNOWN','denominator':None,'qualifying_funds':None,'percentage':None,'expectation_percent':'80','currency':cov.currency,'amount_basis':None,'findings':findings,'debt_waived':False,'deployment_authorized':False,'scope':'selected complete billing coverage only'}
    if len(values)!=2:return manifest,result
    basis=values[DENOMINATOR]['amount_basis'];result['amount_basis']=basis
    if any(v['coverage_id']!=cov.pk or (v['currency'],v['amount_basis'])!=(cov.currency,basis) for v in values.values()):findings.append('Configured basis does not identify selected coverage/currency/amount basis')
    current=BillingCoverage.objects.filter(case=case,reference=cov.reference).order_by('-version').first()
    if current.pk!=cov.pk or cov.completeness!='complete':findings.append('Current explicitly complete coverage required; partial captured invoices are not a contract total')
    if position['findings'] or position['uncertain_issuance'] or position['uncertain_corrections'] or position['pending_corrections'] or position['pending_cash_successors']:findings.append('Financial conflicts, corrections or uncertain effects require reconciliation')
    selected=set(InvoiceIssue.objects.filter(invoice__preparation__coverage=cov).values_list('pk',flat=True))
    rows=[r for r in position['invoices'] if r['issue'] in selected]
    if not rows:findings.append('No proven issued invoices in selected coverage; denominator is unknown')
    if any((r['currency'],r['amount_basis'])!=(cov.currency,basis) or r['open'] is None for r in rows):findings.append('Invoice basis conflict')
    if findings:return manifest,result
    with localcontext() as ctx:
        ctx.prec=512
        denominator=sum((Decimal(r['adjusted_face']) for r in rows),Decimal(0))
        if denominator<=0:findings.append('Nonpositive denominator cannot establish a payment percentage');return manifest,result
        if values[FUNDS]['method']=='allocated_to_selected_invoices':funds=sum((Decimal(r['allocated']) for r in rows),Decimal(0))
        else:
            _,_,_,lots,assignments,allocations,reversals,_=facts(case)
            assigned={a.receipt_id:a for a in assignments};rev_lots={r.lot_id for r in reversals if r.lot_id};funds=Decimal(0)
            for lot in lots:
                a=assigned.get(lot.receipt_id);v=lot_payload(lot)
                if a and a.coverage_id==cov.pk and lot.pk not in rev_lots:
                    if (v['customer'],v['currency'],v['amount_basis'])!=(cov.customer,cov.currency,basis):findings.append('Assigned cash basis conflict');return manifest,result
                    # Funds already allocated to another coverage are unavailable here.
                    reversed_allocs={r.allocation_id for r in reversals if r.allocation_id}
                    elsewhere=sum((a.amount for a in allocations if a.lot_id==lot.pk and a.pk not in reversed_allocs and a.issue_id not in selected),Decimal(0))
                    funds+=lot.amount-elsewhere
        if funds<0:findings.append('Cash conservation conflict');return manifest,result
        percent=funds*100/denominator
        result.update(status='MEETS_EXPECTATION' if funds*100>=denominator*80 else 'BELOW_EXPECTATION',denominator=number(denominator),qualifying_funds=number(funds),percentage=number(percent),open_debt=number(sum((Decimal(r['open']) for r in rows),Decimal(0))))
    return manifest,result

def guard_assess(actor,case,dossier_id,coverage_id):
    for action in ['payment.assess','payment.read','finance.read','delivery.read']:require(actor,case,action)
    d=dossier_for(case,dossier_id)
    cov=BillingCoverage.objects.filter(case=case,pk=coverage_id).first()
    if not cov:raise ValidationError('Select this case coverage')
    manifest,result=inputs(case,d,cov)
    return d,cov,manifest,result


@transaction.atomic
def assess(actor,case_id,dossier_id,coverage_id,expected):
    case=locked(actor,case_id,'payment.assess',expected)
    d,cov,manifest,result=guard_assess(actor,case,dossier_id,coverage_id)
    r=PaymentAssessment.objects.create(case=case,dossier=d,coverage=cov,manifest=manifest,result=result,sha256=digest({'manifest':manifest,'result':result}),actor=actor)
    event(actor,case,'payment.assessed',assessment=r.pk,status=result['status']);bump(case);return r

def assessment_for(case,pk):
    r=PaymentAssessment.objects.select_related('case','dossier__case','dossier__candidate','coverage').filter(case=case,pk=pk).first()
    if not r:raise ValidationError('Select this case payment assessment')
    return r

def assessment_current(r):
    d=dossier_for(r.case,r.dossier_id)
    manifest,result=inputs(r.case,d,r.coverage)
    if digest({'manifest':manifest,'result':result})!=r.sha256:raise ValidationError('Payment, contract, deployment or assessment policy changed; reassess')
    return r

@transaction.atomic
def request_exception(actor,case_id,assessment_id,operation_key,reason,evidence_id,valid_from,valid_until,expected):
    case=locked(actor,case_id,'payment.exception.request',expected);r=assessment_for(case,assessment_id);assessment_current(r);note_required(reason)
    start,end=aware(valid_from),aware(valid_until)
    if start>=end or not operation_key.strip() or len(operation_key)>100:raise ValidationError('Explicit increasing requested validity window and operation key required')
    evidence=subject(case,evidence_id)
    old=PaymentException.objects.filter(assessment=r,operation_key=operation_key).first()
    if old:
        if (old.actor_id,old.reason,old.evidence_id,old.valid_from,old.valid_until)!=(actor.pk,reason,evidence.pk,start,end):raise ValidationError('Operation key already identifies another request')
        return old
    q=PaymentException.objects.create(assessment=r,operation_key=operation_key,reason=reason,evidence=evidence,valid_from=start,valid_until=end,actor=actor)
    event(actor,case,'payment.exception_requested',request=q.pk);bump(case);return q

def request_for(case,pk):
    q=PaymentException.objects.select_related('assessment__case','assessment__dossier','actor').filter(assessment__case=case,pk=pk).first()
    if not q:raise ValidationError('Select this case exception request')
    return q

def authority(actor,case):
    require(actor,case,'payment.exception.decide')
    configs={k:active_component(k,case) for k in [ROLE,PEOPLE,DELEGATION,VALIDITY]}
    v={k:reference_values(c) for k,c in configs.items()};role=v[ROLE][0]['role'];people={r['user_id'] for r in v[PEOPLE]};now=timezone.now()
    principal=actor
    if actor.pk not in people:
        from django.contrib.auth import get_user_model
        matches=[r for policy in v[DELEGATION] if policy['mode']=='explicit' for r in policy['delegations'] if r['delegate_id']==actor.pk and r['principal_id'] in people and aware(r['valid_from'])<=now<aware(r['valid_until'])]
        if len(matches)!=1:raise PermissionDenied('No exact current D13 human authority or delegation')
        principal=get_user_model().objects.get(pk=matches[0]['principal_id'])
        require(principal,case,'payment.exception.decide')
    pins=decision_authority(principal,case,role)
    return {'components':{**pins,**{k:c.pk for k,c in configs.items()}},'principal_id':principal.pk,'actor_id':actor.pk},v[VALIDITY][0]

@transaction.atomic
def decide(actor,case_id,request_id,verdict,evidence_id,reason,expected):
    action='payment.exception.withdraw' if verdict=='withdraw' else 'payment.exception.decide'
    case=locked(actor,case_id,action,expected);q=request_for(case,request_id);note_required(reason);e=subject(case,evidence_id)
    previous=q.decisions.order_by('-pk').first()
    if verdict=='withdraw':
        if actor.pk!=q.actor_id:raise PermissionDenied('Only the authenticated requester can withdraw')
        if previous and previous.verdict!='return':raise ValidationError('Only an undecided or returned request can be withdrawn')
        pins={}
    else:
        if verdict not in ['approve','reject','return','revoke']:raise ValidationError('Choose an explicit human verdict')
        pins,rules=authority(actor,case)
        if verdict=='revoke':
            if not previous or previous.verdict!='approve':raise ValidationError('Only a prior approval can be revoked')
        else:
            if previous and previous.verdict!='return':raise ValidationError('Decision is terminal; create a fresh assessed request')
            assessment_current(q.assessment)
            if verdict=='approve':
                now=timezone.now()
                if not q.valid_from<=now<q.valid_until or (q.valid_until-q.valid_from).total_seconds()>rules['max_validity_seconds']:raise ValidationError('Requested window is not current or exceeds configured duration')
                if not rules['allow_self_approval'] and q.actor_id in [actor.pk,pins['principal_id']]:raise PermissionDenied('Configured self approval prohibition')
    r=PaymentDecision.objects.create(request=q,verdict=verdict,authority=pins,reason=reason,evidence=e,actor=actor)
    event(actor,case,'payment.exception_decided',request=q.pk,decision=r.pk,verdict=verdict);bump(case);return r

def usable(q):
    r=q.decisions.order_by('-pk').first();now=timezone.now()
    if not r or r.verdict!='approve' or not q.valid_from<=now<q.valid_until:raise ValidationError('Current unrevoked human approval within its validity window required')
    require(q.actor,q.assessment.case,'payment.exception.request')
    pins,rules=authority(r.actor,q.assessment.case)
    if pins!=r.authority:raise ValidationError('Exception authority changed; new decision required')
    assessment_current(q.assessment)
    return r

def combined(actor,r,request_id=None):
    from apps.pmo.delivery import readiness_inputs
    case=r.case
    require(actor,case,'delivery.manage');decision_authority(actor,case,'PM')
    assessment_current(r)
    if r.result['status']=='UNKNOWN':raise ValidationError('Payment basis remains UNKNOWN; configure/reconcile and reassess before release use')
    decision=None
    if r.result['status']=='BELOW_EXPECTATION':
        q=request_for(case,request_id)
        if q.assessment_id!=r.pk:raise ValidationError('Exception must bind this exact assessment')
        decision=usable(q)
    elif request_id:raise ValidationError('Payment meets expectation; no exception use is required')
    return {'assessment':r.pk,'assessment_sha256':r.sha256,'decision':decision.pk if decision else None,'independent_release':readiness_inputs(dossier_for(case,r.dossier_id)),'debt_waived':False,'deployment_dispatched':False},decision

@transaction.atomic
def reserve(actor,case_id,assessment_id,operation_key,expected,request_id=None):
    case=locked(actor,case_id,'payment.release.reserve',expected)
    # Serialize against concurrent grant revocation as well as case/policy changes.
    r=assessment_for(case,assessment_id)
    if not operation_key.strip() or len(operation_key)>100:raise ValidationError('Bounded operation key required')
    key=digest({'tenant':case.tenant,'case':str(case.pk),'operation':operation_key})
    old=PaymentReleaseReservation.objects.filter(operation_key=key).first()
    if old:
        if (old.assessment_id,old.actor_id)!=(r.pk,actor.pk) or (old.decision.request_id if old.decision else None)!=request_id:raise ValidationError('Reservation key already used for another intent')
        return old # Historical receipt; use revalidate() for any new downstream use.
    manifest,decision=combined(actor,r,request_id)
    row=PaymentReleaseReservation.objects.create(assessment=r,decision=decision,operation_key=key,manifest=manifest,sha256=digest(manifest),actor=actor)
    event(actor,case,'payment.release_controls_reserved',reservation=row.pk);bump(case);return row

@transaction.atomic
def revalidate(actor,case_id,reservation_id):
    case=locked(actor,case_id,'payment.release.reserve')
    r=PaymentReleaseReservation.objects.select_related('assessment','decision').filter(assessment__case=case,pk=reservation_id).first()
    if not r:raise ValidationError('Select this case reservation')
    require(r.actor,case,'payment.release.reserve')
    manifest,_=combined(r.actor,r.assessment,r.decision.request_id if r.decision else None)
    if digest(manifest)!=r.sha256:raise ValidationError('Release reservation changed; reconcile before use')
    return r
