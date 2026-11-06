"""Proposed closed metadata projections. Reuses existing domain metadata rights; never payload access."""
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from apps.identity.services import require


def authorize(actor,case,key,row):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current metadata reader required')
    require(actor,case,'case.read')
    if key in ['finance.ledger_projections','finance.ledger_drafts']:
        from apps.finance.ledger_agents import projection_access
        projection_access(actor,row.projection if key.endswith('projections') else row.source.projection)
    elif key=='documents.publication_effects':
        from apps.finance.accepted_documents import binding,access
        value=binding(row.version)
        if value:access(actor,value)
        from apps.finance.documents import binding_for
        if binding_for(row.version):require(actor,case,'finance.read')
    # Payroll/HR/BU read grants expose the same ID/hash/status headers in their native workbenches.
    # Restricted payloads still require their separate nomination, freshness and retention controls.


def project(row,key):
    value={'id':row.pk,'kind':key,'metadata_only':True}
    if key=='finance.ledger_projections':
        from apps.finance.ledger_agent_models import LedgerProjection
        head=LedgerProjection.objects.filter(case=row.case,lineage=row.lineage).order_by('-pk').first()
        value.update(state='private_projection_requires_revalidation',lineage=row.lineage_id,head=head.pk,
            sha256=row.projection.sha256,domain_route='ledger_agents')
    elif key=='finance.ledger_drafts':
        from apps.finance.ledger_agent_models import LedgerAgentDraft,LedgerAgentDraftReview
        head=LedgerAgentDraft.objects.filter(case=row.case,reference=row.reference).order_by('-version').first()
        review=LedgerAgentDraftReview.objects.filter(draft=row).order_by('-pk').first()
        value.update(state='private_draft_requires_revalidation',source=row.source_id,head=head.pk,sha256=row.sha256,
            review=review.pk if review else None,verdict=review.verdict if review else None,domain_route='ledger_agents')
    elif key=='finance.hr_disclosures':
        from apps.finance.hrfinance_models import HRDisclosure,HRHandoffRecord
        head=HRDisclosure.objects.filter(need=row.need).order_by('-pk').first()
        decision=HRHandoffRecord.objects.filter(contract=row,kind__in=['approve','return','revoke']).order_by('-pk').first()
        value.update(state='hr_disclosure_requires_revalidation',need=row.need_id,head=head.pk,sha256=row.sha256,
            decision=decision.pk if decision else None,verdict=decision.kind if decision else None,domain_route='hrfinance')
    elif key=='finance.payroll_work':
        from apps.finance.payroll_models import PayrollRun,PayrollReview
        head=PayrollRun.objects.filter(request=row.request,kind=row.kind).order_by('-pk').first()
        review=PayrollReview.objects.filter(run=row).order_by('-pk').first()
        value.update(state='restricted_working_version_requires_revalidation',request=row.request_id,head=head.pk,sha256=row.sha256,
            review=review.pk if review else None,verdict=review.verdict if review else None,domain_route='payroll')
    elif key=='finance.bu_work':
        from apps.finance.bu_models import BUWork,BUReview
        head=BUWork.objects.filter(case=row.case,reference=row.reference,kind=row.kind).order_by('-version').first()
        review=BUReview.objects.filter(work=row).order_by('-pk').first()
        value.update(state='restricted_bu_version_requires_revalidation',head=head.pk,sha256=row.sha256,
            review=review.pk if review else None,verdict=review.verdict if review else None,domain_route='bu')
    else:
        from apps.documents.models import PublicationJob,PublicationReceipt,ControlledReview
        from adapters.policy_impact import effect
        from adapters.publications import InternalPublicationAdapter
        from django.core.exceptions import ValidationError
        job=PublicationJob.objects.filter(publication=row).first()
        receipt=list(PublicationReceipt.objects.filter(publication=row).order_by('pk').values_list('pk','payload_sha256'))
        review=ControlledReview.objects.filter(version=row.version).order_by('-pk').first()
        try:
            verified=InternalPublicationAdapter().lookup(row)
            state=effect(job.status,verified) if job else 'missing_publication_reservation'
        except ValidationError:
            state='receipt_conflict_requires_reconciliation'
        value.update(state=state,job=job.pk if job else None,
            status=job.status if job else None,fence=job.fence if job else None,attempts=job.attempts if job else None,
            document=row.version.document_id,head=row.version.document.current_id,version=row.version_id,
            payload_sha256=row.version.payload_sha256,receipts=receipt,review=review.pk if review else None,
            verdict=review.verdict if review else None,domain_route='documents')
    return value
