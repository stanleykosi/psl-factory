"""Closed record projections. IDs/status/heads only; never business bodies or effects."""
from dataclasses import dataclass
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db.models import Q, F, Func, JSONField
from apps.identity.services import require


@dataclass(frozen=True)
class Contract:
    model: str
    case_path: str
    grants: tuple
    pins: tuple


REGISTRY = {
 'documents.publication_effects':Contract('documents.Publication','version__document__case',('document.read',),('policies.{component}','review__authority.{component}')),
 'finance.ledger_projections':Contract('finance.LedgerProjection','case',('finance.read','ledger.read','ledger.private.read','ledger.agent.read','agent.data.read','agent.data.source'),('policy_id','snapshot.projector.native_authority.{component}','snapshot.owner.native_authority.{component}')),
 'finance.ledger_drafts':Contract('finance.LedgerAgentDraft','case',('finance.read','ledger.read','ledger.private.read','ledger.agent.read','agent.data.read','agent.data.source'),('snapshot.policy','snapshot.owner.native_authority.{component}','source__policy_id')),
 'finance.hr_disclosures':Contract('finance.HRDisclosure','need__case',('hrfinance.read',),('policy_ids.{component}',)),
 'finance.payroll_work':Contract('finance.PayrollRun','request__case',('payroll.read',),('metadata.policy_ids.{component}','hr_snapshot__contract.policy_ids.{component}')),
 'finance.bu_work':Contract('finance.BUWork','case',('bu.read',),('metadata.policy_ids.{component}','payroll__metadata.policy_ids.{component}')),
 'pmo.decisions':Contract('pmo.Decision','case',(),('policy_id',)),
 'pmo.actions':Contract('pmo.ActionState','item__case',('meeting.read',),('policies.{component}',)),
 'pmo.schedules':Contract('pmo.ReportSchedule','case',('meeting.read',),('policies.{component}',)),
 'finance.runs':Contract('finance.FinanceRun','case',('finance.read',),('snapshot.policies.{component}.id',)),
 'finance.billing':Contract('finance.BillingPreparation','case',('finance.read',),('snapshot.policies.{component}.id',)),
 'finance.invoice_effects':Contract('finance.InvoiceJob','invoice__case',('finance.read',),('intent.policies.{component}', 'intent.issuer_authority.{component}', 'invoice__preparation.snapshot.policies.{component}.id')),
 'finance.correction_effects':Contract('finance.InvoiceJob','invoice__case',('finance.read',),('intent.policies.{component}', 'intent.authority.{component}', 'intent.snapshot.policy.{component}')),
 'baas.events':Contract('baas.SupportEvent','case',('support.read',),('snapshot.{component}',)),
 'baas.reports':Contract('baas.SupportReport','case',('support.read',),('snapshot.intake_policy','snapshot.metric_policy')),
 'baas.response_effects':Contract('baas.SupportResponseJob','packet__case',('support.read','support.private.read','support.response.read'),('packet__snapshot.policy','decision__snapshot.authority.{component}')),
}
UNCOVERED = ['other direct/JSON policy consumers','document drafts/audiences beyond reserved publication policy pins','private inputs, snapshots and reports beyond declared Finance metadata contracts','other effect receipt variants beyond declared invoice/correction/response jobs','indirect dependencies outside these declared contracts']
ROUTES = {'documents.publication_effects':'documents','finance.ledger_projections':'ledger_agents','finance.ledger_drafts':'ledger_agents','finance.hr_disclosures':'hrfinance','finance.payroll_work':'payroll','finance.bu_work':'bu','pmo.decisions':'case','pmo.actions':'meetings','pmo.schedules':'meetings',
    'finance.runs':'finance_analysis','finance.billing':'finance_billing','finance.invoice_effects':'finance_settlement','finance.correction_effects':'finance_corrections',
    'baas.events':'support_flow','baas.reports':'support_flow','baas.response_effects':'support_responses'}


def authorize(actor, case, key):
    if key not in REGISTRY:
        raise ValidationError('Unknown policy impact adapter')
    for grant in REGISTRY[key].grants:
        require(actor, case, grant)
    if key == 'baas.response_effects':
        from apps.baas.support_release import access
        access(actor, case)


PRIVATE_KEYS={'documents.publication_effects','finance.ledger_projections','finance.ledger_drafts','finance.hr_disclosures','finance.payroll_work','finance.bu_work'}


def authorize_row(actor,case,key,row):
    if key in PRIVATE_KEYS:
        from .policy_private_impact import authorize as private_authorize
        private_authorize(actor,case,key,row)


def lock_row(row,key):
    if key=='documents.publication_effects':
        from apps.documents.models import PublicationJob
        from django.db import transaction,DatabaseError
        try:
            with transaction.atomic():
                list(PublicationJob.objects.select_for_update(of=('self',),nowait=True).filter(publication=row))
        except DatabaseError:
            raise ValidationError('Publication work is being reconciled; refresh the impact observation') from None


def query(config, key):
    contract=REGISTRY[key];model=apps.get_model(contract.model)
    clauses=Q(pk__in=[])
    for path in contract.pins:
        clauses |= Q(**{path.replace('.', '__').replace('{component}',config.component):config.pk})
    if key == 'baas.reports':
        events=query(config,'baas.events').annotate(json_id=Func(F('pk'),function='to_jsonb',output_field=JSONField())).values('json_id')
        clauses |= Q(snapshot__head__in=events)
    if key == 'finance.correction_effects':
        if config.component=='D08.duplicate_correction_rules':
            clauses |= Q(intent__snapshot__method=config.pk)
        # A note delivery inherits the exact correction application's policy lineage.
        # JSON transforms preserve numeric IDs without string-coerced matches.
        applied=model.objects.filter(invoice__case=config.case,kind='adjust').filter(clauses).values('intent__correction')
        clauses |= Q(intent__correction__in=applied)
    result=model.objects.filter(**{contract.case_path:config.case}).filter(clauses)
    if key == 'finance.invoice_effects':result=result.filter(kind__in=['issue','deliver'])
    if key == 'finance.correction_effects':result=result.filter(kind__in=['adjust','adjust_deliver'])
    return result.order_by('pk')


def effect(status, receipt):
    if receipt:
        return 'committed_effect' if status == 'confirmed' else 'committed_receipt_requires_reconciliation'
    if status in ['unknown','leased']:
        return 'uncertain_effect'
    if status in ['pending','held']:
        return 'pending_effect'
    return 'inconsistent_or_unknown_effect_state'


def project(row, key):
    if key in PRIVATE_KEYS:
        from .policy_private_impact import project as private_project
        return private_project(row,key)
    value={'id':row.pk, 'kind':key, 'domain_route':ROUTES[key]}
    if key == 'pmo.decisions':
        from apps.pmo.models import Baseline,Decision
        b=Baseline.objects.filter(case_id=row.case_id).first()
        value.update(state='historical_decision' if b and b.signed_id else 'decision_requires_current_authority',
            subject=row.evidence_id, decision_head=Decision.objects.filter(case_id=row.case_id,evidence_id=row.evidence_id,role=row.role).order_by('-pk').values_list('pk',flat=True).first(),
            baseline=[b.plan_id,b.costing_id,b.sow_id,b.signed_id] if b else None)
    elif key == 'pmo.actions':
        value.update(state='historical_action_state' if row.item.current_id != row.pk else ('closed_action' if row.status in ['completed','cancelled'] else 'pending_action'),
            subject=row.item_id, head=row.item.current_id, status=row.status, due_at=row.due_at.isoformat() if row.due_at else None)
    elif key == 'pmo.schedules':
        value.update(state='scheduled_work',status=row.status,next_due_at=row.next_due_at.isoformat() if row.next_due_at else None,
            period_start=row.next_start_at.isoformat() if row.next_start_at else None,period_end=row.next_end_at.isoformat() if row.next_end_at else None,
            actor=row.actor_id,template=row.template_id,error_present=bool(row.error))
    elif key == 'finance.runs':
        from apps.finance.models import FinanceRun,FinanceReview
        latest=FinanceRun.objects.filter(source=row.source,kind=row.kind).order_by('-pk').first()
        review=FinanceReview.objects.filter(run=row).order_by('-pk').first()
        value.update(state='latest_preview_requires_revalidation' if latest.pk==row.pk else 'historical_preview',
            source=row.source_id, head=latest.pk, review=review.pk if review else None, verdict=review.verdict if review else None)
    elif key == 'finance.billing':
        from apps.finance.models import BillingPreparation,Invoice
        latest=BillingPreparation.objects.filter(coverage=row.coverage,kind=row.kind).order_by('-pk').first()
        value.update(state='billing_snapshot_requires_revalidation',head=latest.pk,
            coverage=row.coverage_id, coverage_head=row.coverage.__class__.objects.filter(case=row.case,reference=row.coverage.reference).order_by('-version').values_list('pk',flat=True).first(),
            invoice_head=Invoice.objects.filter(preparation=row).order_by('-pk').values_list('pk',flat=True).first())
    elif key == 'finance.invoice_effects':
        from apps.finance.models import InvoiceIssue,InvoiceDelivery
        receipt=(InvoiceIssue if row.kind=='issue' else InvoiceDelivery).objects.filter(job=row).first() if row.kind in ['issue','deliver'] else None
        value.update(state=effect(row.status,receipt),status=row.status,fence=row.fence,attempts=row.attempts,
            lease_until=row.lease_until.isoformat() if row.lease_until else None, receipt=receipt.pk if receipt else None, invoice=row.invoice_id,
            receipt_coverage='local issue/delivery receipts only; correction receipts require their own adapter')
    elif key == 'finance.correction_effects':
        from apps.finance.models import InvoiceJob,InvoiceCorrection,InvoiceCorrectionAcceptance,InvoiceCorrectionDelivery,FinancialCorrectionReview
        correction=InvoiceCorrection.objects.filter(pk=row.intent.get('correction'),case=row.invoice.case,issue__invoice=row.invoice).first()
        receipt_model=InvoiceCorrectionAcceptance if row.kind=='adjust' else InvoiceCorrectionDelivery
        receipt=receipt_model.objects.filter(job=row,correction=correction).first() if correction else None
        acceptance=InvoiceCorrectionAcceptance.objects.filter(correction=correction).first() if correction else None
        review=FinancialCorrectionReview.objects.filter(correction=correction).order_by('-pk').first() if correction else None
        head=InvoiceCorrection.objects.filter(case=correction.case,reference=correction.reference).order_by('-version').first() if correction else None
        generation=InvoiceJob.objects.filter(invoice=row.invoice,kind=row.kind,intent__correction=row.intent.get('correction')).order_by('-generation').first()
        state=effect(row.status,receipt)
        if not receipt and row.status in ['cancelled','replaced']:state='retired_reservation'
        if not correction:state='invalid_correction_identity'
        value.update(state=state,status=row.status,fence=row.fence,attempts=row.attempts,
            lease_until=row.lease_until.isoformat() if row.lease_until else None,receipt=receipt.pk if receipt else None,
            receipt_sha256=receipt.sha256 if receipt else None,receipt_kind=row.kind,invoice=row.invoice_id,
            correction=correction.pk if correction else None,correction_head=head.pk if head else None,
            reservation_head=generation.pk if generation else None,review_head=review.pk if review else None,
            review_verdict=review.verdict if review else None,acceptance=acceptance.pk if acceptance else None,
            receipt_coverage='local canonical correction application or internal note delivery; not incumbent/customer-channel acceptance')
    elif key == 'baas.events':
        from apps.baas.models import SupportEvent
        head=SupportEvent.objects.filter(case=row.case).order_by('-version').first()
        value.update(state='current_flow_event' if head.pk==row.pk else 'historical_flow_event',head=head.pk,flow_state=row.state,version=row.version)
    elif key == 'baas.reports':
        from apps.baas.models import SupportEvent,SupportReview,SupportReport
        head=SupportEvent.objects.filter(case=row.case).order_by('-version').first()
        review=SupportReview.objects.filter(report=row,purpose='summary').order_by('-pk').first()
        value.update(state='report_snapshot_requires_revalidation',head=head.pk if head else None,
            report_head=SupportReport.objects.filter(case=row.case).order_by('-pk').values_list('pk',flat=True).first(),
            recorded_head=row.snapshot.get('head'), review=review.pk if review else None,verdict=review.verdict if review else None)
    else:
        from apps.baas.support_release_models import SupportResponseReceipt
        receipt=SupportResponseReceipt.objects.filter(job=row).first()
        value.update(state=effect(row.status,receipt),status=row.status,fence=row.fence,attempts=row.attempts,
            lease_until=row.lease_until.isoformat() if row.lease_until else None,receipt=receipt.pk if receipt else None,
            packet=row.packet_id,decision=row.decision_id,receipt_coverage='local persisted response receipt; not customer-channel clock attestation')
    return value
