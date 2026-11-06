"""Bounded A01/A03/A04/A05/A06 partner investigation; no completion or financial authority."""
from django.db import transaction
from django.core.exceptions import ValidationError,PermissionDenied
from apps.core.services import event,bump
from apps.agents.models import AgentRun
from apps.baas import partner_operations as domain
from apps.baas.models import PartnerRecord,PartnerDecision,OnboardingEvent,PartnerReport,PartnerReportReview,PartnerFinanceReceipt,PartnerFollowup,PartnerBillingImport
from apps.baas.partner_operations import locked

@transaction.atomic
def investigate(actor,case_id,expected):
    case=locked(actor,case_id,'agent.partners',expected);records=list(PartnerRecord.objects.filter(case=case).order_by('pk'));citations=[];findings=[];plan=[]
    if not records:raise ValidationError('Capture partner evidence before investigation')
    for r in records:
        citations.append({'id':r.evidence_id,'sha256':r.evidence.sha256,'record':r.pk})
        try:domain.current(r)
        except (ValidationError,PermissionDenied):continue
        if r.kind=='agreement':
            position=domain.agreement_position(r);findings+=position['findings'];plan.append({'record':r.pk,'position':position,'next_step':'Obtain business/legal clause validation and explicit owner renewal/notice intent; no automatic acceptance or external notice.'})
        elif r.kind=='onboarding':
            position=domain.age(r);findings+=position['findings'];plan.append({'record':r.pk,'position':position,'missing_documents':r.payload['missing_documents'],'next_step':'Ask configured stage holder to reconcile tracker/portal evidence and choose an owned internal follow-up; visibility is not completion.'})
        else:
            try:_,result,_=domain.activity_calculation(r);findings+=result['findings'];plan.append({'record':r.pk,'metrics':result,'next_step':'Reconcile user/product/source anomalies, review aggregate disclosure, then hand off to Finance. Activity metrics are not invoice quantities.'})
            except (ValidationError,PermissionDenied) as exc:findings.append(str(exc))
    for query in [PartnerDecision.objects.filter(record__case=case),OnboardingEvent.objects.filter(record__case=case),PartnerReportReview.objects.filter(report__record__case=case)]:
        for fact in query:citations.append({'id':fact.evidence_id,'sha256':fact.evidence.sha256,'history_type':fact._meta.model_name,'history_id':fact.pk})
    lineage=[{'receipt':r.pk,'report':r.report_id,'report_hash':r.report.sha256,'delivered_at':r.created_at.isoformat(),'meter_acceptance':PartnerBillingImport.objects.filter(receipt=r).values_list('pk',flat=True).first(),'meaning':'Aggregate report delivery only; meter acceptance and invoice review are separate.'} for r in PartnerFinanceReceipt.objects.filter(report__record__case=case)]
    tasks=[{'followup':f.pk,'record':f.record_id,'action':f.action_id,'status':f.action.current.status,'owner':f.action.current.owner_id,'due_at':f.action.current.due_at.isoformat() if f.action.current.due_at else None} for f in PartnerFollowup.objects.filter(record__case=case)]
    result={'capabilities':['A01','A03','A04','A05','A06'],'findings':findings,'investigation_plan':plan,'handoff_lineage':lineage,'owned_followups':tasks,'citations':citations,'tools':['partner_evidence_read','configured_age_compare','activity_compare','restricted_followup_draft'],'onboarding_completed':False,'renewal_executed':False,'external_message_sent':False,'invoice_created':False}
    run=AgentRun.objects.create(case=case,actor=actor,evidence=records[0].evidence,provider='deterministic-partners-v1',process_id='B11',result=result)
    event(actor,case,'agent.partner_investigated',agent_run=run.pk);bump(case);return run
