"""Selected unsigned exemption validity, not latest assurance or new authority."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied,ValidationError
from apps.identity.services import require
from apps.pmo.models import BaselineSignatureExemption
from apps.policy.signature_validators import COMPONENT

KEY='pmo.baseline_signature_exemptions'
AUTHORITY='D05.role_principal_assignments'

def readable(actor,case):
    if actor is None or not get_user_model().objects.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Current commercial metadata observer required')
    require(actor,case,'case.read');require(actor,case,'commercial.read')

def query(actor,config):
    readable(actor,config.case)
    rows=BaselineSignatureExemption.objects.filter(case=config.case)
    if config.component==COMPONENT:return rows.filter(policy_id=config.pk).order_by('pk')
    if config.component==AUTHORITY:return rows.filter(authority_id=config.pk).order_by('pk')
    return rows.none()

def authorize_row(actor,case,row):
    readable(actor,case)
    if row.case_id!=case.pk:raise PermissionDenied('Select this case exemption metadata')

def project(row):
    from apps.pmo.signature_exemptions import validate_exemption
    from apps.documents.contracts import digest
    from apps.policy.services import PolicyHold
    try:validate_exemption(row);valid=True
    except (PermissionDenied,ValidationError,PolicyHold):valid=False
    return {'id':row.pk,'kind':KEY,'metadata_only':True,'domain_route':'commercial',
        'policy':row.policy_id,'authority':row.authority_id,
        'exemption_sha256':digest({'sources':row.sources,'approval_refs':row.approval_refs,
            'scope':row.scope_evidence_id,'policy':row.policy_id,'authority':row.authority_id}),
        'selected_exemption_valid_now':valid,'state':'historical_unsigned_exemption_observation',
        'signature_created':False,'signing_authorized':False,'baseline_assurance_granted':False,'effects_performed':False}
