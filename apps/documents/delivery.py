from datetime import timedelta
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.core.models import Case
from apps.core.services import event, lock_case, bump
from apps.identity.models import Grant
from .models import PublicationJob, PublicationReceipt
from .controlled import current_version, validate_review, publication_requirements


@transaction.atomic
def claim_publication(case_id=None,job_id=None):
    now=timezone.now()
    query=PublicationJob.objects.select_for_update(skip_locked=True).filter(
        Q(status__in=['pending','unknown'])|Q(status='leased',lease_until__lte=now))
    if case_id is not None:query=query.filter(publication__version__document__case_id=case_id)
    if job_id is not None:query=query.filter(pk=job_id)
    job=query.order_by('pk').first()
    if not job:
        return None
    job.status='leased';job.fence+=1;job.attempts+=1;job.lease_until=now+timedelta(seconds=30)
    job.save(update_fields=['status','fence','attempts','lease_until'])
    return job.pk,job.fence


def check_fence(job,fence):
    if job.fence!=fence or job.status!='leased' or job.lease_until<=timezone.now():
        raise ValidationError('Expired publication worker fence')


@transaction.atomic
def finish_publication(job_id,fence,status,error=''):
    initial=PublicationJob.objects.select_related('publication__version__document').get(pk=job_id)
    Case.objects.select_for_update().get(pk=initial.publication.version.document.case_id)
    job=PublicationJob.objects.select_for_update().select_related('publication__version__document').get(pk=job_id)
    check_fence(job,fence)
    job.status=status;job.error=error[:400];job.save(update_fields=['status','error'])
    p=job.publication
    prefix='agent.data.finance_metadata_delivery_' if p.version.template.definition['document_type']=='accepted_finance_metadata' else 'document.delivery_'
    event(p.actor,p.version.document.case,prefix+status,publication=p.pk,fence=fence,error=job.error)


@transaction.atomic
def deliver_internal(job_id,fence):
    # The implemented adapter is local: current grants, snapshot checks and receipt creation share a transaction.
    # External network adapters must use a separate reserved-effect protocol, not this transaction boundary.
    job=PublicationJob.objects.select_related('publication__version__document').get(pk=job_id)
    p=job.publication
    if p.version.template.definition['document_type']=='accepted_finance_metadata':
        from apps.finance.accepted_documents import deliver
        return deliver(job_id,fence)
    if p.factory_work_id:
        from apps.workflows.models import FactoryWork
        FactoryWork.objects.select_for_update().get(pk=p.factory_work_id)
    case=Case.objects.select_for_update().get(pk=p.version.document.case_id)
    job=PublicationJob.objects.select_for_update().get(pk=job_id)
    check_fence(job,fence)
    # Lock actual grant rows so a concurrent revocation cannot overtake this local effect.
    from apps.workflows.readiness import gate
    list(Grant.objects.select_for_update().filter(case=case).order_by('pk'))
    gate(case,'publication')
    from apps.pmo.models import EscalationDocumentBinding
    source_actor_ids=list(EscalationDocumentBinding.objects.filter(version=p.version_id,decision__isnull=False).values_list('decision__actor_id',flat=True))
    from apps.pmo.models import EmergencyDocumentBinding
    emergency_binding=EmergencyDocumentBinding.objects.filter(version=p.version_id).first()
    if emergency_binding:
        source_actor_ids += [g[0] for g in emergency_binding.manifest['authority_grants']]
    from apps.pmo.models import ChangeDocumentBinding, StandardBinding, StandardPreapproval, ChangeDecision
    change_binding=ChangeDocumentBinding.objects.filter(version=p.version_id).select_related('authorization').first()
    if change_binding:
        auth=change_binding.authorization
        source_actor_ids+=list(ChangeDecision.objects.filter(pk__in=auth.decision_ids).values_list('actor_id',flat=True))
        snapshot=auth.preapproval_snapshot
        source_actor_ids+=list(StandardBinding.objects.filter(pk=snapshot.get('binding_id')).values_list('actor_id',flat=True))
        source_actor_ids+=list(StandardPreapproval.objects.filter(pk__in=snapshot.get('preapproval_ids',[])).values_list('actor_id',flat=True))
        from apps.pmo.models import AuthorityRecoveryRequest,AuthorityRecoveryDecision,AuthorityRecoveryRecord
        recovery_requests=AuthorityRecoveryRequest.objects.filter(adoption__revision_id=auth.commercial_id) if auth.commercial_id else AuthorityRecoveryRequest.objects.none()
        source_actor_ids+=list(recovery_requests.values_list('actor_id',flat=True))
        source_actor_ids+=list(AuthorityRecoveryDecision.objects.filter(request__in=recovery_requests).values_list('actor_id',flat=True))
        source_actor_ids+=list(AuthorityRecoveryRecord.objects.filter(request__in=recovery_requests).values_list('actor_id',flat=True))
    from apps.pmo.models import DeliveryDocumentBinding,RFPDocumentBinding
    from apps.finance.models import FinanceDocumentBinding,FinancePerformanceBinding,ForecastBinding
    if FinanceDocumentBinding.objects.filter(version=p.version_id).exists() or FinancePerformanceBinding.objects.filter(version=p.version_id).exists() or ForecastBinding.objects.filter(version=p.version_id).exists():source_actor_ids+=list(Grant.objects.filter(case=case).values_list('user_id',flat=True))
    if DeliveryDocumentBinding.objects.filter(version=p.version_id).exists() or RFPDocumentBinding.objects.filter(version=p.version_id).exists():
        source_actor_ids+=list(Grant.objects.filter(case=case).values_list('user_id',flat=True))
    list(Grant.objects.select_for_update().filter(case=case,user_id__in=[p.actor_id]+([p.review.actor_id] if p.review_id else [])+p.recipient_ids+source_actor_ids))
    from apps.identity.services import require
    require(p.actor,case,'document.publish')
    if p.factory_work_id:
        from apps.workflows.factory_publications import publication_scope
        scope=publication_scope(p.actor,case,p.version,p.factory_work_id)
        if scope['factory_policy_id']!=p.factory_policy_id or scope['factory_source_id']!=p.factory_source_id:raise ValidationError('Factory profile or commercial source changed before publication')
    version=current_version(case,p.version_id)
    from apps.pmo.rfp_documents import sender,dispatch_requirements
    sender(p.actor,version)
    dispatch_requirements(version)
    from apps.finance.documents import sender as finance_sender
    finance_sender(p.actor,version)
    review=validate_review(case,version)
    policies,recipients,retention=publication_requirements(case,version)
    if policies!=p.policies or recipients!=p.recipient_ids or (review.pk if review else None)!=p.review_id:
        raise ValidationError('Publication policy/review snapshot changed; cancel and prepare a new reviewed revision')
    for recipient in recipients:
        receipt,created=PublicationReceipt.objects.get_or_create(publication=p,recipient_id=recipient,defaults={
            'operation_key':f'{p.operation_key}:user:{recipient}','payload':version.payload,'payload_sha256':version.payload_sha256})
        if receipt.payload_sha256!=version.payload_sha256 or receipt.payload!=version.payload:
            raise ValidationError('Existing publication receipt payload does not match')
    return str(p.pk)


def run_publication_once(adapter=None,case_id=None,job_id=None,lookup_only=False):
    from adapters.publications import InternalPublicationAdapter
    adapter=adapter or InternalPublicationAdapter()
    lease=claim_publication(case_id,job_id)
    if not lease:
        return False
    job_id,fence=lease
    job=PublicationJob.objects.select_related('publication__version__document').get(pk=job_id)
    if type(adapter) is not InternalPublicationAdapter and not job.publication.version.document.case.synthetic:
        finish_publication(job_id,fence,'held','Fault/test adapters are restricted to synthetic cases')
        return True
    try:
        # Reconcile persisted effects before checking whether new delivery is still permitted.
        receipt=adapter.lookup(job.publication)
        if receipt:
            finish_publication(job_id,fence,'confirmed')
            return True
        if lookup_only:
            raise TimeoutError('Receipt-only reconciliation found no verified receipt; no delivery authorised')
        if job.attempts>5:
            finish_publication(job_id,fence,'held','Attempt budget exhausted; operator reconciliation required')
            return True
        adapter.deliver(job_id,fence)
    except (TimeoutError,ConnectionError):
        finish_publication(job_id,fence,'unknown','Outcome unknown; receipt lookup required before retry')
    except (ValidationError,PermissionDenied,ValueError) as exc:
        finish_publication(job_id,fence,'held',str(exc))
    else:
        finish_publication(job_id,fence,'confirmed')
    return True


@transaction.atomic
def operate_publication(actor,case_id,job_id,action,reason,expected):
    initial=PublicationJob.objects.select_related('publication__version__template').filter(pk=job_id,publication__version__document__case_id=case_id).first()
    native=initial is not None and initial.publication.version.template.definition['document_type']=='accepted_finance_metadata'
    if native:
        from apps.finance.accepted_documents import operate
        return operate(actor,case_id,job_id,action,reason,expected)
    case=lock_case(actor,case_id,'document.operate',expected)
    job=PublicationJob.objects.select_for_update().select_related('publication__version__document').filter(
        pk=job_id,publication__version__document__case=case).first()
    if not job or action not in ['cancel','retry'] or not reason.strip() or len(reason)>4000:
        raise ValidationError('Choose a case job, recovery action and concise reason')
    from adapters.publications import InternalPublicationAdapter
    if job.status in ['confirmed','cancelled'] or job.status=='leased' and job.lease_until>timezone.now():
        raise ValidationError('Confirmed, cancelled or actively leased publication cannot be changed')
    if InternalPublicationAdapter().lookup(job.publication):
        raise ValidationError('Delivery already has receipts; reconcile it instead of cancelling or retrying')
    if action=='retry':
        if job.status!='held':
            raise ValidationError('Only held jobs need operator retry; unknown jobs reconcile through the worker')
        p=job.publication
        version=current_version(case,p.version_id)
        from apps.pmo.rfp_documents import dispatch_requirements
        dispatch_requirements(version)
        validate_review(case,version)
        policies,recipients,_=publication_requirements(case,version)
        if policies!=p.policies or recipients!=p.recipient_ids:
            raise ValidationError('Policy changed; create a new reviewed document version')
        if p.factory_work_id:
            from apps.workflows.factory_publications import publication_scope
            scope=publication_scope(p.actor,case,version,p.factory_work_id)
            if scope['factory_policy_id']!=p.factory_policy_id or scope['factory_source_id']!=p.factory_source_id:raise ValidationError('Factory scope changed; cancel and prepare a new exact reviewed document version')
        job.status='pending';job.attempts=0
    else:
        job.status='cancelled'
    job.error=reason[:400];job.save(update_fields=['status','attempts','error'])
    event(actor,case,'document.operator_'+action,job=job.pk,publication=job.publication_id,reason=reason)
    bump(case)
