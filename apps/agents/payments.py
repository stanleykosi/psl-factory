"""Cited deterministic D13 investigation. No approval or release tool is exposed."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import event,bump
from apps.finance import payments as domain
from apps.finance.models import PaymentAssessment,PaymentException
from .models import AgentRun

@transaction.atomic
def investigate(actor,case_id,expected):
    case=domain.locked(actor,case_id,'agent.payments',expected)
    citations=set();findings=[];plan=[];drafts=[];approved_assessments=set()
    for q in PaymentException.objects.filter(assessment__case=case).order_by('-pk')[:30]:
        citations.add(q.evidence_id)
        try:
            d=domain.usable(q);status='current approval #'+str(d.pk);approved_assessments.add(q.assessment_id)
        except (ValidationError,PermissionDenied) as exc:status=str(exc)
        findings.append({'request':q.pk,'use_status':status})
        citations.update(q.decisions.values_list('evidence_id',flat=True))
    assessments=list(PaymentAssessment.objects.filter(case=case).select_related('coverage').order_by('-pk')[:20])
    if not assessments:raise ValidationError('Capture a payment assessment before investigation')
    for r in assessments:
        citations.add(r.coverage.evidence_id)
        citations.update(v for k,v in r.manifest['context']['baseline'].items() if k in ['plan_id','costing_id','sow_id','signed_id'] and isinstance(v,int))
        try:domain.assessment_current(r);current=True
        except (ValidationError,PermissionDenied):current=False
        findings.append({'assessment':r.pk,'status':r.result['status'],'current':current,'holds':r.result['findings'],'sha256':r.sha256,'denominator':r.result['denominator'],'qualifying_funds':r.result['qualifying_funds'],'open_debt':r.result.get('open_debt'),'deployment_context':r.manifest['context']})
        if not current:plan.append({'assessment':r.pk,'action':'Reconcile changed evidence and reassess; preserve the old snapshot'})
        elif r.result['status']=='UNKNOWN':plan.append({'assessment':r.pk,'action':'Resolve only the reported basis/financial holds; exception requests remain available'})
        elif r.result['status']=='BELOW_EXPECTATION':
            if r.pk in approved_assessments:plan.append({'assessment':r.pk,'action':'A current human exception exists; check independent release controls at prospective use'})
            else:drafts.append({'assessment':r.pk,'text':'Please review the captured payment shortfall for this exact deployment. A human decision requires configured authority and validity. Debt and independent release controls remain in force.','human_request_required':True})
    # Cite actual local financial and policy evidence, not only the interpreted snapshot.
    from apps.finance.models import CashReceipt,CashVerification,CashAllocation,CashReversal,InvoiceCorrection
    from apps.policy.models import Configuration
    from apps.finance.models import InvoiceIssue
    for issue in InvoiceIssue.objects.filter(invoice__case=case).select_related('invoice__preparation__usage','invoice__preparation__coverage')[:100]:
        prep=issue.invoice.preparation;citations.add(prep.coverage.evidence_id)
        if prep.usage_id:citations.add(prep.usage.evidence_id)
    for model,path in [(CashReceipt,'case'),(CashVerification,'receipt__case'),(CashAllocation,'lot__receipt__case'),(CashReversal,'lot__receipt__case'),(CashReversal,'allocation__lot__receipt__case'),(InvoiceCorrection,'case')]:
        citations.update(model.objects.filter(**{path:case}).order_by('-pk').values_list('evidence_id',flat=True)[:100])
    pinned={p['id'] for r in assessments for p in r.manifest['policies'].values() if p['id']}
    for c in Configuration.objects.filter(case=case,pk__in=pinned):citations.update(int(ref.split(':')[-1]) for ref in c.envelope['evidence_refs'])
    source=case.evidence.filter(pk__in=citations).first()
    run=AgentRun.objects.create(case=case,actor=actor,evidence=source,provider='deterministic-payments-v1',process_id='F34',result={'findings':findings,'plan':plan,'drafts':drafts,'citations':sorted(citations),'citation_scope':'20 latest assessments, 30 requests, up to100 financial records per evidence category; selected case only','tools':['assessment_current','exception_use_check','draft_followup'],'debt_waived':False,'deployment_dispatched':False,'provider_evaluation':'local deterministic only'})
    event(actor,case,'agent.payment_investigation',run=run.pk);bump(case);return run
