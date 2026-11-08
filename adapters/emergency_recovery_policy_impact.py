"""Emergency-outcome request snapshot metadata only, never recovered authority."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.pmo.models import AuthorityRecoveryRequest
from apps.policy.services import PolicyHold

KEY='pmo.emergency_recovery_requests'
POLICY='D05.revision_invalidation_rules'
AUTHORITY=('D05.role_principal_assignments','D05.delegation_rules','D05.decision_action_matrix')

def readable(actor,case):
    if actor is None or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current authority metadata observer required')
    require(actor,case,'case.read');require(actor,case,'authority.read')

def query(actor,config):
    readable(actor,config.case)
    rows=AuthorityRecoveryRequest.objects.filter(case=config.case,adoption__isnull=True,outcome__isnull=False)
    if config.component==POLICY:return rows.filter(snapshot__recovery_policy_id=config.pk).order_by('pk')
    if config.component in AUTHORITY:
        return rows.filter(**{'snapshot__authority_policies__'+config.component+'__1':config.pk}).order_by('pk')
    return rows.none()

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.case_id!=case.pk or row.adoption_id is not None or row.outcome_id is None:
        raise PermissionDenied('Select this case emergency request metadata')

def project(row):
    from apps.pmo.recoveries import current_request
    from apps.documents.contracts import digest
    try:current_request(row.case,row);current=True
    except (PermissionDenied,ValidationError,PolicyHold):current=False
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'authority_recovery',
        'outcome':row.outcome_id,'snapshot_sha256':digest(row.snapshot),
        'request_snapshot_current':current,'state':'historical_request_not_recovered_authority',
        'authority_recovered':False,'approval_granted':False,'effects_performed':False}
