"""Read existing native archive/isolated recovery proofs; never run recovery."""
from django.core.exceptions import ValidationError,PermissionDenied
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.identity.services import require
from apps.documents.contracts import digest

FAMILIES=('application','cold')


@transaction.atomic
def read(actor,case,family,pk):
    if not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():raise PermissionDenied('Current recovery reader required')
    require(actor,case,'case.read')
    if type(pk) is not int or pk<1 or family not in FAMILIES:raise ValidationError('Exact native recovery job required')
    if family=='application':
        from apps.workflows import application_recovery as d
        d.access(actor,case,'read',locked=False)
        d.access(actor,case,'read',locked=True)
    else:
        from apps.workflows import cold_recovery as d
        d.access(actor,case,'read',locked=False)
        d.access(actor,case,'read')
    j=d.Job.objects.select_related('plan').filter(pk=pk,plan__case=case).first()
    if not j:raise ValidationError('Exact same-case native recovery job required')
    r=d.report(actor,case.pk,j.plan_id)
    observed=next((v for v in r['jobs'] if v['id']==j.pk),{}) if family=='application' else r
    valid=observed.get('physical_receipt_current',False)
    evidence={'kind':j.kind if family=='application' else 'restore','plan':j.plan_id,'plan_sha256':j.plan.sha256,
        'physical_receipt_current':valid,'authorization_current':r['authorization_current'],
        'human_recovery_review_current':r.get('human_recovery_review_current',r.get('human_recovered_review_current',False)),
        'native_restore_verified':valid and (family=='cold' or j.kind=='restore'),
        'scope':'native_database_managed_attachments_isolated_only','production_activation':False,'live_authority_restored':False,
        'retention_scope':'Source adapter checks current archive validity; retention cleanup and monitoring/SLO evidence remain separate'}
    return {'family':family,'id':j.pk,'status':j.status,'fence':j.fence,'attempts':j.attempts,
        'lease_until':j.lease_until.isoformat() if j.lease_until else None,'receipt_verified':valid,
        'local_receipt_sha256':digest(j.receipt) if j.receipt else None,'replay_permitted':False,'recovery_evidence':evidence,
        'follow_up':'Use current source-owned review and receipt-first recovery; preflight has no restore or retry tools'}
